from langchain_ibm import ChatWatsonx
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
import os
import db

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

@tool
def execute_query(query: str) -> str:
    """Executes a SQL SELECT query against the database and returns the results."""
    return str(db.execute_query(query))

tools = [execute_query]

# Validate that we have the necessary credentials
def validate_creds():
    if not os.getenv("WATSONX_APIKEY") or not os.getenv("WATSONX_PROJECT_ID"):
        print("WARNING: Watsonx credentials not found in environment variables.")

validate_creds()

# Create the agent
# We use a memory saver to persist state across turns if needed (though REST API is stateless usually,
# we can pass thread_id to resume).
memory = MemorySaver()
agent_executor = create_react_agent(llm, tools, checkpointer=memory)

from langchain_core.messages import AIMessage, ToolMessage

# ... imports ...

import json
import re

def generate_table_metadata(preview_data: dict, filename: str) -> dict:
    """
    Generates metadata (table name, description, column descriptions) using LLM.
    """
    # Create prompt
    preview_str = json.dumps(preview_data['preview'], indent=2)
    min_preview = preview_str[:2000] # Truncate if too long
    
    prompt = f"""
    Analyze the following dataset preview from file '{filename}':
    {min_preview}
    
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
        
        # Cleanup markdown code blocks if present
        if content.startswith("```"):
            content = content.strip("`")
            if content.startswith("json"):
                content = content[4:]
        
        metadata = json.loads(content)
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
    """
    config = {"configurable": {"thread_id": thread_id}}
    
    # Fetch context for selected tables
    context = db.get_table_context(selected_tables)
    
    # Construct augmented prompt
    augmented_question = f"""
    You have access to the following tables:
    {context}
    
    User Question: {user_question}
    
    Instructions:
    1. ARTIFACTS: When answering, if the result is a table, simple return the markdown.
    2. PRIVACY: Do not query tables that are not listed above.
    """
    
    # Use astream_events to get granular updates including tokens
    async for event in agent_executor.astream_events(
        {"messages": [("user", augmented_question)]},
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
