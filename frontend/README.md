# DataTalk Frontend

The user interface for DataTalk, built with React and Vite. It features a modern, responsive design optimized for data exploration, project management, and AI-powered chat interactions.

## 🎨 UI Features

*   **Glassmorphism Design**: Sleek, translucent panels with dynamic backgrounds
*   **Theme Engine**: Dark Mode and Light Mode, toggled via CSS variables
*   **Multi-Project Support**: Create and switch between isolated workspaces
*   **Sidebar Navigation**: Browse uploaded CSVs and external database tables
*   **Interactive Charts**: Vega-Lite visualizations with tooltips, zoom/pan, and export
*   **Chat History**: Persistent sessions with AI-generated titles
*   **Markdown Rendering**: Tables, code blocks, and embedded charts in responses
*   **Reasoning Accordion**: Collapsible blocks showing AI's internal thought process

## 🏗 Component Structure

### Pages
*   **`LoginPage`**: Authentication with email verification flow
*   **`ProjectsPage`**: Project listing, creation, and management
*   **`WorkspacePage`**: Main data exploration interface

### Key Components
*   **`Sidebar`**: Table selection with grouped sources (CSV, external DBs)
*   **`ChatInterface`**: Streaming message display with tool execution steps
*   **`VegaChartRenderer`**: Interactive Vega-Lite chart component
*   **`MetadataEditor`**: Table/column metadata editing
*   **`ConnectionManager`**: External database connection UI
*   **`MembersPanel`**: Project member and role management
*   **`CredentialsModal`**: Groq API key configuration
*   **`ChatHistoryModal`**: Browse and restore past sessions

### Context
*   **`AuthContext`**: User authentication state and JWT management
*   **`ProjectContext`**: Current project, tables, and connections state

## 🚀 Setup & Run

1.  **Install Dependencies**
    ```bash
    npm install
    ```

2.  **Development Server**
    ```bash
    npm run dev
    ```
    Expects backend at `http://localhost:8000`

3.  **Production Build**
    ```bash
    npm run build
    ```

## 📦 Key Libraries

*   `lucide-react`: Iconography
*   `react-markdown`: Rendering AI responses
*   `remark-gfm`: GitHub Flavored Markdown support
*   `react-syntax-highlighter`: Code block highlighting
*   `react-vega`: Vega-Lite chart rendering
*   `axios`: HTTP client
