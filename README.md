# DataTalk: Natural Language to SQL & Visualization

DataTalk is a modern, full-stack application that empowers users to interact with their data using natural language. Upload CSV files or connect to external databases, let the AI analyze and structure them, and then simply ask questions to get answers, SQL queries, and beautiful interactive visualizations.

## 🚀 Key Features

*   **Smart Data Import**: Upload CSVs with automatic schema inference. The AI proactively scans the file to suggest table names, descriptions, and column metadata.
*   **External Database Connections**: Connect to PostgreSQL, MySQL, IBM Db2, and Oracle databases. Browse schemas and sync table metadata.
*   **Multi-Project Workspaces**: Create isolated projects with their own tables, connections, and chat history. Invite team members with role-based access (Owner, Editor, Viewer).
*   **Metadata Editor**: Review and refine the AI's suggestions before committing your data. Edit table names, descriptions, and column details at any time.
*   **Context-Aware Chat**: Select tables from multiple sources (CSV or external databases) to query simultaneously.
*   **NL-to-SQL Engine**: Powered by Groq LLM, converting complex English questions into precise SQL queries.
*   **Rich Visualizations**:
    *   **Interactive Vega-Lite Charts**: Bar, Line, Area, Scatter plots with tooltips, zoom, pan, and export.
    *   **Custom Python Charts**: The AI can write and execute Matplotlib code for complex visualizations.
*   **User Authentication**: Secure login with email verification, password management, and per-user API credentials.
*   **Chat History**: Persistent chat sessions with AI-generated titles for easy navigation.
*   **Token Usage Tracking**: Monitor LLM token consumption per project, session, and message.
*   **Interactive UI**: A premium, glassmorphism-inspired interface with Dark/Light mode support.

## 🛠 Tech Stack

### Backend
*   **Framework**: FastAPI (async)
*   **Database**: PostgreSQL (asyncpg)
*   **AI/LLM**: LangChain, LangGraph, Groq API
*   **Data Processing**: Pandas, Matplotlib, SQLAlchemy
*   **Auth**: JWT tokens, Argon2/bcrypt password hashing

### Frontend
*   **Framework**: React (Vite)
*   **Styling**: Vanilla CSS (Variables, Glassmorphism)
*   **Charts**: Vega-Lite (react-vega)
*   **Icons**: Lucide React
*   **Markdown**: React Markdown with syntax highlighting

## 🏁 Getting Started

### Prerequisites
*   Node.js (v18+)
*   Python (v3.12+)
*   PostgreSQL database
*   **uv** (Python package manager):
    ```bash
    # macOS / Linux
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Windows (PowerShell)
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```
*   Groq API Key (get from [console.groq.com/keys](https://console.groq.com/keys))

### Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/abhijeet-gorai/nl-to-sql.git
    cd nl-to-sql
    ```

2.  **Backend Setup**
    ```bash
    cd backend
    uv sync
    source .venv/bin/activate  # or .venv\Scripts\activate on Windows
    ```
    
    Create a `.env` file in `backend/`:
    ```env
    # PostgreSQL
    PGHOST=localhost
    PGPORT=5432
    PGDATABASE=nl_to_sql
    PGUSER=postgres
    PGPASSWORD=your_password
    
    # Groq LLM
    GROQ_API_KEY=gsk_your_api_key
    
    # Security
    JWT_SECRET_KEY=your_jwt_secret
    CREDENTIAL_ENCRYPTION_KEY=your_fernet_key
    DB_ENCRYPTION_KEY=your_fernet_key
    
    # Email
    GMAIL_APP_PASSWORD=your_gmail_app_password
    GMAIL_EMAIL_ID=your_gmail_email_id
    FRONTEND_URL=the_url_of_your_frontend(http://localhost:5173)
    ```

3.  **Frontend Setup**
    ```bash
    cd ../frontend
    npm install
    ```

### Running the Application

1.  **Start Backend** (from `backend/`)
    ```bash
    uvicorn main:app --reload --env-file .env
    ```
    Server starts at `http://localhost:8000`

2.  **Start Frontend** (from `frontend/`)
    ```bash
    npm run dev
    ```
    Client starts at `http://localhost:5173`

## 📂 Project Structure

```
nl-to-sql/
├── backend/
│   ├── agent.py              # LangGraph agent & tools
│   ├── db.py                 # CSV table management
│   ├── main.py               # API endpoints
│   ├── auth.py               # User authentication
│   ├── projects.py           # Project & member management
│   ├── connection_manager.py # External DB connections
│   ├── metadata_extractor.py # External table sync
│   ├── query_router.py       # Federated query routing
│   ├── database_config.py    # PostgreSQL async pool
│   └── charts/               # Generated visualizations
├── frontend/
│   └── src/
│       ├── pages/            # Page components
│       ├── components/       # UI components
│       ├── api/              # API client
│       └── context/          # React context providers
└── sample_data/              # Sample CSVs for testing
```
