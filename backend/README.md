# DataTalk Backend

The backend engine for DataTalk, built with FastAPI and LangChain. It handles data ingestion, database management, user authentication, and AI agent orchestration for NL-to-SQL tasks.

## 🧠 Core Components

### 1. API Server (`main.py`)
*   **Authentication**: `/auth/*` - Register, login, email verification, password management
*   **Projects**: `/projects/*` - CRUD operations with member management and role-based access
*   **Tables**: `/projects/{id}/tables/*` - CSV upload, metadata editing, table management
*   **Connections**: `/projects/{id}/connections/*` - External database connection management
*   **Chat**: `/projects/{id}/chat` - Streaming NL-to-SQL responses with tool execution
*   **Sessions**: Chat history with AI-generated titles
*   **Token Usage**: LLM token consumption tracking per session/project

### 2. AI Agent (`agent.py`)
*   Uses **LangGraph** to create a ReAct-style agent with checkpointing
*   **LLM**: Integrates with Groq API (`openai/gpt-oss-120b`)
*   **Tools**:
    *   `execute_query`: Runs SQL SELECT queries against selected tables
    *   `generate_chart_frontend`: Creates interactive Vega-Lite chart specs
    *   `generate_custom_chart_frontend`: Complex multi-series Vega-Lite visualizations
    *   `generate_chart` / `generate_custom_chart`: Legacy Matplotlib charts (fallback)

### 3. Database Layer
*   **`database_config.py`**: Async PostgreSQL connection pool (asyncpg)
*   **`db.py`**: CSV table management and metadata storage
*   **`query_router.py`**: Federated query routing (CSV + external databases)
*   **`connection_manager.py`**: External database connection CRUD with encrypted credentials

### 4. Authentication (`auth.py`)
*   JWT token-based authentication
*   Password hashing with Argon2/bcrypt
*   Email verification flow

## 🚀 Setup & Run

1.  **Install Dependencies** (requires [uv](https://docs.astral.sh/uv/))
    ```bash
    uv sync
    source .venv/bin/activate
    ```

2.  **Environment Variables** - Create `.env`:
    ```env
    # PostgreSQL Connection
    PGHOST=localhost
    PGPORT=5432
    PGDATABASE=nl_to_sql
    PGUSER=postgres
    PGPASSWORD=your_password
    
    # Groq API
    GROQ_API_KEY=gsk_...
    
    # Security Keys (generate with Fernet.generate_key())
    JWT_SECRET_KEY=your_secret
    CREDENTIAL_ENCRYPTION_KEY=your_fernet_key
    DB_ENCRYPTION_KEY=your_fernet_key
    
    # Email
    GMAIL_APP_PASSWORD=your_gmail_app_password
    GMAIL_EMAIL_ID=your_gmail_email_id
    FRONTEND_URL=the_url_of_your_frontend(http://localhost:5173)
    ```

3.  **Start Server**
    ```bash
    uvicorn main:app --reload --env-file .env
    ```

## 📊 Visualization

The backend supports two chart generation modes:

1. **Frontend Charts (Preferred)**: Returns Vega-Lite JSON specs that render interactively in the browser with tooltips, zoom/pan, and export functionality.

2. **Legacy Charts**: Generates Matplotlib PNG images saved to `backend/charts/` for fallback scenarios.
