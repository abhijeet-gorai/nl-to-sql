# DataTalk Backend

The backend engine for DataTalk, built with FastAPI and LangChain. It handles data ingestion, database management, and the AI agent orchestration for NL-to-SQL tasks.

## 🧠 Core Components

### 1. API Server (`main.py`)
*   **`/analyze`**: Uploads CSV, infers schema, and uses AI to suggest metadata (table name, descriptions).
*   **`/register`**: Finalizes data import, creating the SQLite table and storing metadata.
*   **`/chat`**: Streaming endpoint that accepts user messages and returns AI thoughts (tokens) and final answers.
*   **`/tables`**: CRUD operations for managing dataset metadata.
*   **Static Serving**: Serves generated charts from the `/charts` directory.

### 2. AI Agent (`agent.py`)
*   Uses **LangGraph** to create a ReAct-style agent.
*   **LLM**: Integrates with IBM Watsonx.ai (e.g., `openai/gpt-oss-120b`).
*   **Tools**:
    *   `execute_query`: Runs read-only SQL SELECT queries.
    *   `generate_chart`: Creates standard charts (Bar, Line, Pie, Scatter).
    *   `generate_custom_chart`: Executes sandboxed Python code for complex Matplotlib visualizations.

### 3. Database Manager (`db.py`)
*   Manages the internal **SQLite** database (`database.db`).
*   Maintains a special `app_metadata` table to store rich context about user tables.
*   Handles CSV parsing and raw data retrieval for the visualization tools.

## 🚀 Setup & Run

1.  **Install Dependencies**
    Note: You must have **uv** installed (`pip install uv` or see [astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation)).
    ```bash
    uv sync
    # Activate venv
    # Windows: .venv\Scripts\activate
    # Linux/Mac: source .venv/bin/activate
    ```

2.  **Environment Variables**
    Create a `.env` file:
    ```env
    WATSONX_APIKEY=...
    WATSONX_PROJECT_ID=...
    WATSONX_URL=...
    ```

3.  **Start Server**
    ```bash
    uvicorn main:app --reload --env-file .env
    ```

## 📊 Visualization

The backend includes a specialized logic to handle charts. When an agent generates a chart, it saves the image to `backend/charts/` and returns a Markdown link (e.g., `![Chart](/charts/uuid.png)`). The frontend renders this directly.
