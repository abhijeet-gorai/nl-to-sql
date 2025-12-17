# DataTalk: Natural Language to SQL & Visualization

DataTalk is a modern, full-stack application that empowers users to interact with their data using natural language. Upload CSV files, let the AI analyze and structure them into a database, and then simply ask questions to get answers, SQL queries, and beautiful visualizations.

## 🚀 Key Features

*   **Smart Data Import**: Upload CSVs with automatic schema inference. The AI proactively scans the file to suggest table names, descriptions, and column metadata.
*   **Metadata Editor**: Review and refine the AI's suggestions before committing your data. Edit table names, descriptions, and column details at any time.
*   **Context-Aware Chat**: Select multiple tables to query simultaneously. The AI understands the relationships between your data.
*   **NL-to-SQL Engine**: Powered by Watsonx (Granite/GPT models), converting complex English questions into precise SQLite queries.
*   **Rich Visualizations**:
    *   **Standard Charts**: Automatically generates Bar, Line, Pie, and Scatter plots.
    *   **Custom Python Charts**: The AI can write and execute custom Python (Matplotlib) code for complex visualizations on the fly.
*   **Interactive UI**: A premium, glassmorphism-inspired interface with Dark/Light mode support.
*   **Session Management**: Reset chat history or delete tables with secure confirmation modals.

## 🛠 Tech Stack

### Backend
*   **Framework**: FastAPI
*   **Database**: SQLite
*   **AI/LLM**: LangChain, LangGraph, IBM Watsonx.ai
*   **Data Processing**: Pandas, Matplotlib

### Frontend
*   **Framework**: React (Vite)
*   **Styling**: Vanilla CSS (Variables, Glassmorphism)
*   **Icons**: Lucide React
*   **Markdown**: React Markdown, Remark GFM

## 🏁 Getting Started

### Prerequisites
*   Node.js (v16+)
*   Python (v3.9+)
*   **uv** (Python package manager). If not installed:
    ```bash
    # Windows (PowerShell)
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    # macOS / Linux
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
*   IBM Watsonx Credentials (`WATSONX_APIKEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`)

### Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/abhijeet-gorai/nl-to-sql.git
    cd nl-to-sql
    ```

2.  **Backend Setup**
    ```bash
    cd backend
    # This creates the virtual environment and installs dependencies
    uv sync
    
    # Activate the virtual environment
    # Windows:
    .venv\Scripts\activate
    # Mac/Linux:
    source .venv/bin/activate
    ```
    *Create a `.env` file in `backend/` with your credentials:*
    ```env
    WATSONX_APIKEY=your_api_key
    WATSONX_PROJECT_ID=your_project_id
    WATSONX_URL=your_url
    ```

3.  **Frontend Setup**
    ```bash
    cd ../frontend
    npm install
    ```

### Running the Application

1.  **Start Backend** (from `backend/` dir)
    ```bash
    # Ensure venv is active
    uvicorn main:app --reload --env-file .env
    ```
    Server will start at `http://localhost:8000`

2.  **Start Frontend** (from `frontend/` dir)
    ```bash
    npm run dev
    ```
    Client will start at `http://localhost:5173`

## 📂 Project Structure

```
nl-to-sql/
├── backend/            # FastAPI server & AI logic
│   ├── agent.py        # LangChain agent & tools
│   ├── db.py           # Database & CSV handling
│   ├── main.py         # API Endpoints
│   └── charts/         # Generated visualizations
├── frontend/           # React application
│   ├── src/
│   │   ├── App.jsx     # Main UI Logic
│   │   └── index.css   # Global Styles
└── sample_data/        # Sample CSVs for testing
```
