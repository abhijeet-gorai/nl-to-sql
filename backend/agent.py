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
def list_tables() -> str:
    """Lists all tables in the database."""
    return db.get_db_schema()

@tool
def get_schema(table_name: str) -> str:
    """Get the schema and column details for a specific table."""
    # In our simple implementation, get_db_schema returns everything,
    # but we can return it all again or filter if we improved db.py.
    # For now, just return the full schema as it's small.
    return db.get_db_schema()

@tool
def execute_query(query: str) -> str:
    """Executes a SQL SELECT query against the database and returns the results."""
    return str(db.execute_sql(query))

tools = [list_tables, get_schema, execute_query]

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

# ... (keep existing imports)

async def stream_question(user_question: str, thread_id: str = "1"):
    """
    Streams events (tool usage, response tokens) from the agent.
    """
    config = {"configurable": {"thread_id": thread_id}}
    
    # Use astream_events to get granular updates including tokens
    async for event in agent_executor.astream_events(
        {"messages": [("user", user_question)]},
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
                output = str(event["data"].get("output"))
                yield json.dumps({
                    "type": "tool_end", 
                    "tool": event["name"],
                    "output": output
                }) + "\n"
