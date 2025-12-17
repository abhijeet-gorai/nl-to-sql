from langchain_ibm import ChatWatsonx
from langchain.tools import tool, ToolRuntime
from langchain.agents import AgentState, create_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.output_parsers import JsonOutputParser
import os
import db
import query_router
from dotenv import load_dotenv

load_dotenv()

class CustomState(AgentState):
    selected_tables: list[str]

# Initialize Watsonx Chat Model
# Ideally these are set in environment variables:
# WATSONX_APIKEY, WATSONX_PROJECT_ID, WATSONX_URL
llm = ChatWatsonx(
    model_id="openai/gpt-oss-120b",
    url=os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com"),
    project_id=os.getenv("WATSONX_PROJECT_ID"),
    params={
        "decoding_method": "greedy",
        "max_new_tokens": 1000,
        "min_new_tokens": 1
    }
)

import matplotlib
matplotlib.use('Agg') # Non-interactive backend
import matplotlib.pyplot as plt
import pandas as pd
import uuid

@tool
def execute_query(query: str, runtime: ToolRuntime) -> str:
    """Executes a SQL SELECT query against the database and returns the results.
    Supports both local CSV tables and external database tables."""
    try:
        selected_tables = runtime.state["selected_tables"]
        df = query_router.execute_federated_query(query, selected_tables)
        if df is None or df.empty:
            return "Query returned no results."
        return df.to_markdown(index=False)
    except Exception as e:
        return f"Error executing query: {str(e)}"

@tool
def generate_chart(query: str, chart_type: str, x_col: str, y_col: str, runtime: ToolRuntime, title: str = "") -> str:
    """
    Generates a STANDARD chart (bar, line, pie, scatter) from a SQL query.
    Use this for simple, single-series visualizations.
    Supports both local CSV tables and external database tables.
    args:
        query: The SQL query to fetch data.
        chart_type: 'bar', 'line', 'pie', or 'scatter'.
        x_col: Column name for X axis.
        y_col: Column name for Y axis.
        title: Chart title.
    """
    # Use federated query router with selected tables
    selected_tables = runtime.state["selected_tables"]
    df = query_router.execute_federated_query(query, selected_tables)
    if df is None or df.empty:
        return "Error: Query returned no data."
    
    if x_col not in df.columns or y_col not in df.columns:
        return f"Error: Columns {x_col} or {y_col} not found in results: {list(df.columns)}"

    plt.figure(figsize=(10, 6))
    
    try:
        if chart_type == 'bar':
            plt.bar(df[x_col], df[y_col])
        elif chart_type == 'line':
            plt.plot(df[x_col], df[y_col], marker='o')
        elif chart_type == 'scatter':
            plt.scatter(df[x_col], df[y_col])
        elif chart_type == 'pie':
            plt.pie(df[y_col], labels=df[x_col], autopct='%1.1f%%')
        else:
            return f"Error: Unsupported chart type '{chart_type}'."
            
        if title:
            plt.title(title)
        
        if chart_type != 'pie':
            plt.xlabel(x_col)
            plt.ylabel(y_col)
            plt.xticks(rotation=45)
            
        plt.tight_layout()
        
        # Save file
        filename = f"chart_{uuid.uuid4()}.png"
        charts_dir = os.path.join(os.path.dirname(__file__), "charts")
        os.makedirs(charts_dir, exist_ok=True)
        filepath = os.path.join(charts_dir, filename)
        
        plt.savefig(filepath)
        plt.close()
        
        # Return Markdown Image
        return f"![{title}](http://localhost:8000/charts/{filename})"
        
    except Exception as e:
        plt.close()
        return f"Error generating chart: {e}"

@tool
def generate_custom_chart(python_code: str, runtime: ToolRuntime) -> str:
    """
    Generates a CUSTOM or COMPLEX chart by executing Python code.
    Use this when 'generate_chart' is insufficient (e.g., dual-axis, subplots, heatmaps, or advanced formatting).
    
    The code has access to:
    - 'pd' (pandas)
    - 'plt' (matplotlib.pyplot)
    - 'query_router' (federated query router module)
    - 'selected_tables' (list of currently selected table names)

    Instructions for code:
    1. Fetch data using: df = query_router.execute_federated_query(your_sql_query, selected_tables)
    2. Create a figure using plt.figure().
    3. Plot data using matplotlib.
    4. Data MUST be fetched inside the code using the query_router.
    5. DO NOT show() or save() the plot. The system handles saving.
    
    Example:
    ```python
    # Fetch data from selected tables
    df = query_router.execute_federated_query("SELECT * FROM customers LIMIT 100", selected_tables)
    
    # Create chart
    plt.figure(figsize=(10, 6))
    plt.bar(df['category'], df['count'])
    plt.title('My Chart')
    ```
    """
    try:
        selected_tables = runtime.state["selected_tables"]
        # Define secure-ish locals with federated query support
        local_scope = {
            "pd": pd,
            "plt": plt,
            "query_router": query_router,
            "selected_tables": selected_tables  # Pass selected tables to the code
        }
        
        # Execute the code
        exec(python_code, globals(), local_scope)
        
        # Check if figure exists
        if plt.get_fignums():
             # Save file
            filename = f"custom_chart_{uuid.uuid4()}.png"
            charts_dir = os.path.join(os.path.dirname(__file__), "charts")
            os.makedirs(charts_dir, exist_ok=True)
            filepath = os.path.join(charts_dir, filename)
            
            plt.savefig(filepath)
            plt.close('all') # Close all figures to clean up
            
            return f"![Custom Chart](http://localhost:8000/charts/{filename})"
        else:
             return "Error: No chart was created. Did you forget to call plt.plot()?"

    except Exception as e:
        plt.close('all')
        return f"Error executing custom chart code: {e}"

tools = [execute_query, generate_chart, generate_custom_chart]

# Validate that we have the necessary credentials
def validate_creds():
    if not os.getenv("WATSONX_APIKEY") or not os.getenv("WATSONX_PROJECT_ID"):
        print("WARNING: Watsonx credentials not found in environment variables.")

validate_creds()

# Create the agent
# We use a memory saver to persist state across turns if needed (though REST API is stateless usually,
# we can pass thread_id to resume).
memory = MemorySaver()
agent_executor = create_agent(llm, tools, checkpointer=memory, state_schema=CustomState)

# ... imports ...

import json

def generate_table_metadata(preview_data: dict, filename: str, existing_tables: list[str] = None) -> dict:
    """
    Generates metadata (table name, description, column descriptions) using LLM.
    """
    # Create prompt
    preview_str = json.dumps(preview_data['preview'], indent=2)
    min_preview = preview_str[:2000] # Truncate if too long
    
    existing_tables_str = ", ".join(existing_tables) if existing_tables else "None"

    prompt = f"""
    Analyze the following dataset preview from file '{filename}':
    {min_preview}
    
    The following table names ALREADY EXIST in the database: [{existing_tables_str}].
    You MUST choose a unique table_name that is NOT in the list above. 
    If the suggested name conflicts, append a suffix or change the name entirely to be unique but descriptive.

    Generate metadata in STRICT JSON format with the following structure:
    {{
        "table_name": "suggested_snake_case_name",
        "description": "A brief description of the dataset",
        "columns": [
            {{ "name": "col_name_from_data", "description": "Description of this column" }}
        ]
    }}
    
    The table_name should be short, descriptive, and in snake_case.
    Ensure "columns" list matches the columns in the preview.
    Return ONLY VALID JSON. Do not include markdown formatting like ```json.
    """
    
    try:
        response = llm.invoke(prompt)
        content = response.content.strip()
        
        metadata = JsonOutputParser().parse(content)
        print("Metadata generation succeeded", metadata)
        return metadata
    except Exception as e:
        print(f"Metadata generation failed: {e}")
        # Fallback to defaults
        return {
            "table_name": db.generate_table_name(filename),
            "description": f"Dataset imported from {filename}",
            "columns": []
        }

async def stream_question(user_question: str, selected_tables: list[str], thread_id: str = "1"):
    """
    Streams events (tool usage, response tokens) from the agent.
    Supports both local CSV tables and external database tables.
    """
    
    config = {"configurable": {"thread_id": thread_id}}
    
    # Fetch context for selected tables using federated context builder
    context = query_router.build_table_context_federated(selected_tables)
    
    # Construct augmented prompt
    augmented_question = f"""
    You have access to the following tables:
    {context}
    
    User Question: {user_question}
    
    Instructions:
    1. PRIVACY: Do not query tables that are not listed above.
    2. IMPORTANT: Tables may come from different sources (local CSV or external databases).
    3. When querying external database tables, use schema_name.table_name for the table name.
    """
    print(augmented_question)
    # Use astream_events to get granular updates including tokens
    async for event in agent_executor.astream_events(
        {"messages": [("user", augmented_question)], "selected_tables": selected_tables},
        config,
        version="v1"
    ):
        kind = event["event"]
        
        # Stream Tokens
        if kind == "on_chat_model_stream":
            content = event["data"]["chunk"].content
            if content:
                yield json.dumps({"type": "token", "content": content}) + "\n"
                
        # Tool Start
        elif kind == "on_tool_start":
            # Filter out internal tools or check name if needed
            if event["name"] not in ["_Exception"]:
                yield json.dumps({
                    "type": "tool_start", 
                    "tool": event["name"], 
                    "input": event["data"].get("input")
                }) + "\n"
                
        # Tool End
        elif kind == "on_tool_end":
            if event["name"] not in ["_Exception"]:
                output = event["data"].get("output")
                yield json.dumps({
                    "type": "tool_end", 
                    "tool": event["name"],
                    "output": output.content
                }) + "\n"
