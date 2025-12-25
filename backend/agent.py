from langchain_ibm import ChatWatsonx
from langchain.tools import tool, ToolRuntime
from langchain.agents import AgentState, create_agent
from langchain.messages import ToolMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from langchain_core.output_parsers import JsonOutputParser
import os
import db
import query_router
import user_credentials
from dotenv import load_dotenv
import matplotlib

matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import pandas as pd
import uuid
import json

load_dotenv()


class CustomState(AgentState):
    selected_tables: list[dict]
    base_url: str  # Base URL for generating chart image URLs
    charts: list[dict]  # List of Vega-Lite chart specifications


# ============================================
# LLM Caching System
# ============================================

# In-memory cache: {user_id: {"llm": ChatWatsonx, "credentials_hash": str}}
# "default" key for default credentials from .env
_llm_cache = {}


def invalidate_llm_cache(user_id: int):
    """Call when user credentials are updated or deleted."""
    if user_id in _llm_cache:
        del _llm_cache[user_id]


def get_llm_for_user(user_id: int = None) -> ChatWatsonx:
    """
    Returns a cached ChatWatsonx instance with appropriate credentials.
    Uses user credentials if available, otherwise falls back to default.
    """
    if user_id:
        creds = user_credentials.get_credentials(user_id)
        if creds:
            creds_hash = user_credentials.get_credentials_hash(user_id)
            cached = _llm_cache.get(user_id)

            # Return cached if credentials haven't changed
            if cached and cached.get("credentials_hash") == creds_hash:
                return cached["llm"]

            # Create new and cache
            llm = ChatWatsonx(
                model_id="openai/gpt-oss-120b",
                url=creds["watsonx_url"],
                project_id=creds["watsonx_project_id"],
                apikey=creds["watsonx_api_key"],
                params={"temperature": 0, "max_tokens": 4000},
            )
            _llm_cache[user_id] = {"llm": llm, "credentials_hash": creds_hash}
            return llm

    # Fall back to default (also cached)
    if "default" in _llm_cache:
        return _llm_cache["default"]["llm"]

    default_llm = ChatWatsonx(
        model_id="openai/gpt-oss-120b",
        url=os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com"),
        project_id=os.getenv("WATSONX_PROJECT_ID"),
        params={"temperature": 0, "max_tokens": 4000},
    )
    _llm_cache["default"] = {"llm": default_llm, "credentials_hash": "default"}
    return default_llm


# Default LLM for backwards compatibility (tools still reference 'llm')
llm = get_llm_for_user()


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
def generate_chart(
    query: str,
    chart_type: str,
    x_col: str,
    y_col: str,
    runtime: ToolRuntime,
    title: str = "",
) -> str:
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
        if chart_type == "bar":
            plt.bar(df[x_col], df[y_col])
        elif chart_type == "line":
            plt.plot(df[x_col], df[y_col], marker="o")
        elif chart_type == "scatter":
            plt.scatter(df[x_col], df[y_col])
        elif chart_type == "pie":
            plt.pie(df[y_col], labels=df[x_col], autopct="%1.1f%%")
        else:
            return f"Error: Unsupported chart type '{chart_type}'."

        if title:
            plt.title(title)

        if chart_type != "pie":
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

        # Get base URL from runtime state
        base_url = runtime.state.get("base_url", "http://localhost:8000")

        # Return Markdown Image
        return f"![{title}]({base_url}/charts/{filename})"

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
            "selected_tables": selected_tables,  # Pass selected tables to the code
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
            plt.close("all")  # Close all figures to clean up

            # Get base URL from runtime state
            base_url = runtime.state.get("base_url", "http://localhost:8000")

            return f"![Custom Chart]({base_url}/charts/{filename})"
        else:
            return "Error: No chart was created. Did you forget to call plt.plot()?"

    except Exception as e:
        plt.close("all")
        return f"Error executing custom chart code: {e}"


@tool
def generate_chart_frontend(
    query: str,
    chart_type: str,
    x_col: str,
    y_col: str,
    runtime: ToolRuntime,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
) -> Command:
    """
    Generates a Vega-Lite chart specification for STANDARD charts (bar, line, area, point/scatter).
    This returns a JSON specification that will be rendered in the frontend.
    Use this for simple, single-series visualizations.

    Args:
        query: The SQL query to fetch data.
        chart_type: 'bar', 'line', 'area', or 'point' (for scatter).
        x_col: Column name for X axis.
        y_col: Column name for Y axis.
        title: Chart title (optional).
        x_label: X axis label (optional, defaults to x_col).
        y_label: Y axis label (optional, defaults to y_col).

    Returns:
        Command to update state with chart specification.
    """
    try:
        # Execute query to get data
        selected_tables = runtime.state["selected_tables"]
        df = query_router.execute_federated_query(query, selected_tables)

        if df is None or df.empty:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content="Error: Query returned no data.",
                            tool_call_id=runtime.tool_call_id,
                            name="generate_chart_frontend",
                        )
                    ]
                }
            )

        if x_col not in df.columns or y_col not in df.columns:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=f"Error: Columns {x_col} or {y_col} not found in results: {list(df.columns)}",
                            tool_call_id=runtime.tool_call_id,
                            name="generate_chart_frontend",
                        )
                    ]
                }
            )

        # Convert DataFrame to list of records for Vega-Lite
        data_values = df[[x_col, y_col]].to_dict(orient="records")

        # Map chart types to Vega-Lite mark types
        mark_type_map = {
            "bar": "bar",
            "line": "line",
            "area": "area",
            "point": "point",
            "scatter": "point",
        }

        mark_type = mark_type_map.get(chart_type.lower())
        if not mark_type:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=f"Error: Unsupported chart type '{chart_type}'. Use: bar, line, area, point, or scatter.",
                            tool_call_id=runtime.tool_call_id,
                            name="generate_chart_frontend",
                        )
                    ]
                }
            )

        # Build Vega-Lite specification
        vega_spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
            "description": title or f"{chart_type.capitalize()} chart",
            "title": title if title else None,
            "data": {"values": data_values},
            "mark": {"type": mark_type, "tooltip": True},
            "encoding": {
                "x": {
                    "field": x_col,
                    "type": "nominal"
                    if df[x_col].dtype == "object"
                    else "quantitative",
                    "title": x_label or x_col,
                },
                "y": {
                    "field": y_col,
                    "type": "quantitative",
                    "title": y_label or y_col,
                },
            },
            "width": 600,
            "height": 400,
        }

        # Remove None title if not provided
        if not vega_spec["title"]:
            del vega_spec["title"]

        # Get current charts and append new one
        current_charts = runtime.state.get("charts", [])
        chart_number = len(current_charts)
        updated_charts = current_charts + [vega_spec]

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"[CHART:{chart_number}] - Chart specification created successfully. Chart will be displayed after response completes.",
                        tool_call_id=runtime.tool_call_id,
                        name="generate_chart_frontend",
                    )
                ],
                "charts": updated_charts,
            }
        )

    except Exception as e:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Error generating chart specification: {str(e)}",
                        tool_call_id=runtime.tool_call_id,
                        name="generate_chart_frontend",
                    )
                ]
            }
        )


@tool
def generate_custom_chart_frontend(
    query: str,
    vega_lite_spec: dict,
    runtime: ToolRuntime,
) -> Command:
    """
    Generates a CUSTOM Vega-Lite chart specification for complex visualizations.
    Use this when 'generate_chart_frontend' is insufficient (e.g., multi-series, dual-axis,
    heatmaps, layered charts, or advanced formatting).

    Args:
        query: The SQL query to fetch data.
        vega_lite_spec: A partial or complete Vega-Lite specification (dict).
                       The data will be fetched and injected automatically.
                       You can provide encoding, mark, transform, etc.

    Example vega_lite_spec for a grouped bar chart:
    {
        "mark": "bar",
        "encoding": {
            "x": {"field": "category", "type": "nominal"},
            "y": {"field": "value", "type": "quantitative"},
            "color": {"field": "group", "type": "nominal"}
        }
    }

    Returns:
        Command to update state with custom chart specification.
    """
    try:
        # Execute query to get data
        selected_tables = runtime.state["selected_tables"]
        df = query_router.execute_federated_query(query, selected_tables)

        if df is None or df.empty:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content="Error: Query returned no data.",
                            tool_call_id=runtime.tool_call_id,
                            name="generate_custom_chart_frontend",
                        )
                    ]
                }
            )
        # Validate that spec has required visualization properties
        required_props = [
            "mark",
            "layer",
            "facet",
            "hconcat",
            "vconcat",
            "concat",
            "repeat",
        ]
        has_valid_prop = False

        for prop in required_props:
            if prop in vega_lite_spec and vega_lite_spec[prop]:
                has_valid_prop = True
                break

        if not has_valid_prop:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=f"Error: Vega-Lite specification must include at least one of: {', '.join(required_props)}. The property must not be empty.",
                            tool_call_id=runtime.tool_call_id,
                            name="generate_custom_chart_frontend",
                        )
                    ]
                }
            )

        # Convert DataFrame to list of records
        data_values = df.to_dict(orient="records")

        # Build complete Vega-Lite specification
        complete_spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
            "data": {"values": data_values},
            "width": 600,
            "height": 400,
        }

        # Merge with provided spec
        complete_spec.update(vega_lite_spec)

        # Ensure data is set correctly (don't let user override)
        complete_spec["data"] = {"values": data_values}

        # Get current charts and append new one
        current_charts = runtime.state.get("charts", [])
        chart_number = len(current_charts)
        updated_charts = current_charts + [complete_spec]

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"[CHART:{chart_number}] - Custom chart specification created successfully. Chart will be displayed after response completes.",
                        tool_call_id=runtime.tool_call_id,
                        name="generate_custom_chart_frontend",
                    )
                ],
                "charts": updated_charts,
            }
        )

    except Exception as e:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Error generating custom chart specification: {str(e)}",
                        tool_call_id=runtime.tool_call_id,
                        name="generate_custom_chart_frontend",
                    )
                ]
            }
        )


tools = [
    execute_query,
    generate_chart,
    generate_custom_chart,
    generate_chart_frontend,
    generate_custom_chart_frontend,
]


# Validate that we have the necessary credentials
def validate_creds():
    if not os.getenv("WATSONX_APIKEY") or not os.getenv("WATSONX_PROJECT_ID"):
        print("WARNING: Watsonx credentials not found in environment variables.")


validate_creds()
# System prompt for the agent
SYSTEM_PROMPT = """You are a Data Analysis Assistant with expertise in SQL and data visualization.

## Your Role
You help users analyze their data by:
1. Writing and executing SQL queries against their databases
2. Creating interactive visualizations to present insights
3. Answering questions about their data clearly and concisely

## Available Data Sources
Users can connect multiple types of data sources:
- Local CSV files
- External databases (PostgreSQL, MySQL, IBM Db2, Oracle)
You will be provided with table schemas and metadata to help you write accurate queries.

## Chart Generation - IMPORTANT
When creating visualizations, you have TWO sets of tools:

### Frontend Chart Tools (PREFERRED - Use These First):
- `generate_chart_frontend`: For standard charts (bar, line, area, scatter)
- `generate_custom_chart_frontend`: For complex visualizations (multi-series, layered, faceted)

**Key Points:**
- These tools generate Vega-Lite specifications that render interactively in the UI
- Charts are AUTOMATICALLY displayed after your response completes
- You do NOT need to mention the chart will be displayed - it happens automatically
- Charts support dark/light mode, tooltips, zoom, pan, and export
- ALWAYS prefer these tools unless they fail or user explicitly requests otherwise

### Legacy Chart Tools (Fallback Only):
- `generate_chart`: Server-side matplotlib charts (use only if frontend tools fail)
- `generate_custom_chart`: Server-side custom charts (use only if frontend tools fail)

## Behavior Guidelines

### Query Execution:
1. Always use `execute_query` to fetch data before creating charts
2. Write efficient SQL queries with appropriate LIMIT clauses for large datasets
3. Use proper JOIN syntax when querying multiple tables
4. Handle NULL values appropriately in your queries

### Chart Creation:
1. **ALWAYS use frontend chart tools first** (`generate_chart_frontend` or `generate_custom_chart_frontend`)
2. Choose the appropriate chart type based on the data:
   - Bar charts: Comparing categories
   - Line charts: Trends over time
   - Scatter plots: Relationships between variables
   - Area charts: Cumulative values over time
3. For complex visualizations (multi-series, dual-axis, heatmaps), use `generate_custom_chart_frontend`
4. Provide clear, descriptive titles and axis labels
5. **IMPORTANT**: After calling a chart tool, reference it in your response using `[CHART:n]` where n is the chart index (0, 1, 2, etc.)
   - First chart created: `[CHART:0]`
   - Second chart created: `[CHART:1]`
   - Place the marker where you want the chart to appear in your response
   - Example: "Here are the sales by category: [CHART:0]. As you can see, Electronics leads with..."
6. Only fall back to legacy tools if frontend tools consistently fail

### Communication:
1. Be concise and direct in your responses
2. Explain your analysis clearly
3. When charts are generated, focus on insights - don't mention "the chart will be displayed"
4. Whenever you are displaying charts, also give your analysis of the data present in the chart.
5. If queries return no data, explain why and suggest alternatives
6. If you encounter errors, explain them clearly and suggest solutions
7. Even when you are generating charts, you must answer the user query in text.

### Data Privacy:
- Only query tables that are explicitly provided in the context
- Never attempt to access tables outside the user's selected scope
- Respect schema boundaries for external databases

## Example Interactions

**User:** "Show me sales by category"
**You:** 
1. Execute query to get sales data
2. Use `generate_chart_frontend` with chart_type="bar"
3. Provide insights: "The data shows that Electronics has the highest sales at $X, followed by..."

**User:** "Compare revenue and expenses over time"
**You:**
1. Execute query to get both metrics
2. Use `generate_custom_chart_frontend` with multi-series line chart spec
3. Provide insights: "Revenue has been growing steadily while expenses remain relatively flat..."

Remember: Frontend chart tools are your primary choice. They provide better user experience with interactive, theme-aware visualizations.
"""


def generate_table_metadata(
    preview_data: dict,
    filename: str,
    existing_tables: list[str] = None,
    user_id: int = None,
) -> tuple[dict, dict | None]:
    """
    Generates metadata (table name, description, column descriptions) using LLM.

    Args:
        preview_data: Preview data of the dataset
        filename: Original filename
        existing_tables: List of existing table names to avoid conflicts
        user_id: User ID to get appropriate LLM credentials

    Returns:
        Tuple of (metadata_dict, usage_metadata) where usage_metadata may be None
    """
    # Get LLM for this user (uses cached instance if available)
    user_llm = get_llm_for_user(user_id)

    # Create prompt
    preview_str = json.dumps(preview_data["preview"], indent=2)
    min_preview = preview_str[:2000]  # Truncate if too long

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
        response = user_llm.invoke(prompt)
        content = response.content.strip()

        # Extract usage metadata
        usage_metadata = None
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage_metadata = dict(response.usage_metadata)

        metadata = JsonOutputParser().parse(content)
        print("Metadata generation succeeded", metadata)
        return metadata, usage_metadata
    except Exception as e:
        print(f"Metadata generation failed: {e}")
        # Fallback to defaults
        return {
            "table_name": db.generate_table_name(filename),
            "description": f"Dataset imported from {filename}",
            "columns": [],
        }, None


async def stream_question(
    user_question: str,
    selected_tables: list[dict],
    thread_id: str = "1",
    base_url: str = "http://localhost:8000",
    token_logger: callable = None,
    user_id: int = None,
):
    """
    Streams events (tool usage, response tokens) from the agent.
    Supports both local CSV tables and external database tables.

    Args:
        user_question: The user's natural language question.
        selected_tables: List of table configurations to query.
        thread_id: Thread ID for conversation context.
        base_url: Base URL of the server (for chart image URLs).
        token_logger: Optional callback function to log token usage.
                      Signature: token_logger(message_id: str, usage_metadata: dict)
        user_id: User ID to get appropriate LLM credentials.
    """

    config = {"configurable": {"thread_id": thread_id}}

    # Get LLM for this user (uses cached instance if available)
    user_llm = get_llm_for_user(user_id)

    async with AsyncSqliteSaver.from_conn_string("checkpoint.db") as memory:
        # Create agent executor with user's LLM
        user_agent_executor = create_agent(
            user_llm,
            tools,
            checkpointer=memory,
            state_schema=CustomState,
            system_prompt=SYSTEM_PROMPT,
        )

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
        # print(augmented_question)
        # Use astream_events to get granular updates including tokens
        async for event in user_agent_executor.astream_events(
            {
                "messages": [("user", augmented_question)],
                "selected_tables": selected_tables,
                "base_url": base_url,
                "charts": [],  # Initialize empty charts list
            },
            config,
            version="v1",
        ):
            kind = event["event"]
            # Log token usage for each AI message completion
            if kind == "on_chat_model_end" and token_logger:
                try:
                    output = event.get("data", {}).get("output")
                    # Navigate to the message object in generations
                    if output and "generations" in output and output["generations"]:
                        generation = (
                            output["generations"][0][0]
                            if output["generations"][0]
                            else None
                        )
                        if generation and "message" in generation:
                            message = generation["message"]
                            if (
                                hasattr(message, "usage_metadata")
                                and message.usage_metadata
                            ):
                                # Use AIMessage's id if available, otherwise generate UUID
                                message_id = getattr(message, "id", None)
                                if not message_id:
                                    message_id = str(uuid.uuid4())
                                token_logger(message_id, dict(message.usage_metadata))
                except Exception as e:
                    print(f"Failed to log token usage: {e}")

            # Stream Tokens
            if kind == "on_chat_model_stream":
                reasoning_content = event["data"]["chunk"].additional_kwargs.get(
                    "reasoning_content", ""
                )
                if reasoning_content:
                    print(reasoning_content, end="")
                content = event["data"]["chunk"].content
                if content:
                    yield json.dumps({"type": "token", "content": content}) + "\n"

            # Tool Start
            elif kind == "on_tool_start":
                # Filter out internal tools or check name if needed
                if event["name"] not in ["_Exception"]:
                    yield (
                        json.dumps(
                            {
                                "type": "tool_start",
                                "tool": event["name"],
                                "input": event["data"].get("input"),
                            }
                        )
                        + "\n"
                    )

            # Tool End
            elif kind == "on_tool_end":
                if event["name"] not in ["_Exception"]:
                    output = event["data"].get("output")
                    if isinstance(output, Command):
                        output_content = output.update.get("messages")[-1].content
                    else:
                        output_content = (
                            output.content
                            if hasattr(output, "content")
                            else str(output)
                        )
                    yield (
                        json.dumps(
                            {
                                "type": "tool_end",
                                "tool": event["name"],
                                "output": output_content,
                            }
                        )
                        + "\n"
                    )

        # After streaming completes, get final state and yield charts if any
        try:
            final_state = await user_agent_executor.aget_state(config)
            charts = final_state.values.get("charts", [])
            if charts:
                yield json.dumps({"type": "charts", "charts": charts}) + "\n"
        except Exception as e:
            print(f"Error retrieving charts from state: {e}")
        state = await user_agent_executor.aget_state(config=config)
        print(state.values.get("messages")[-1])
