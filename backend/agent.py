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

def process_question(user_question: str, thread_id: str = "1"):
    """
    Process a user question using the agent and return response + reasoning steps.
    """
    config = {"configurable": {"thread_id": thread_id}}
    
    events = agent_executor.stream(
        {"messages": [("user", user_question)]},
        config,
        stream_mode="values"
    )

    final_response = ""
    messages = []
    
    # Iterate through stream to get the final state
    for event in events:
        if "messages" in event:
            messages = event["messages"]
            final_response = messages[-1].content
    
    # Extract steps from messages
    steps = []
    for i, msg in enumerate(messages):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tool_call in msg.tool_calls:
                step = {
                    "type": "tool_call",
                    "tool": tool_call["name"],
                    "input": tool_call["args"],
                    "output": "Pending..."
                }
                # Look ahead for the corresponding ToolMessage
                # (Simple heuristic: usually the next message(s) are tool outputs)
                for next_msg in messages[i+1:]:
                    if isinstance(next_msg, ToolMessage) and next_msg.tool_call_id == tool_call["id"]:
                        step["output"] = next_msg.content
                        break
                steps.append(step)

    return {
        "response": final_response,
        "steps": steps
    }
