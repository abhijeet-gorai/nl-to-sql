# DataTalk Frontend

The user interface for DataTalk, built with React and Vite. It features a modern, responsive design optimized for data exploration and chat interactions.

## 🎨 UI Features

*   **Glassmorphism Design**: sleek, translucent panels with a dynamic background.
*   **Theme Engine**: Built-in Dark Mode and Light Mode, toggled via CSS variables.
*   **Sidebar Navigation**: fast access to uploads and uploaded datasets.
*   **Markdown Support**: Renders tables, code blocks, and images (charts) directly in the chat.
*   **Reasoning Accordion**: Collapsible "View Reasoning" blocks to see the AI's internal thought process (SQL queries, code execution) without cluttering the chat.

## 🏗 Component Structure

*   **`App.jsx`**: The main controller. Handles:
    *   State management (tables, messages, view modes).
    *   API calls to the backend.
    *   Streaming response parsing (Server-Sent Events / NDJSON).
    *   View switching (Empty State, Metadata Editor, Chat).
*   **`ConfirmationModal`**: Reusable modal for critical actions (Delete Table, Clear Chat).
*   **`ReasoningAccordion`**: specialized component to display the agent's step-by-step logic.
*   **`index.css`**: Contains all styling tokens (`:root` variables) and utility classes.

## 🚀 Setup & Run

1.  **Install Dependencies**
    ```bash
    npm install
    ```

2.  **Development Server**
    ```bash
    npm run dev
    ```
    By default, it proxies requests or expects the backend at `http://localhost:8000`.

## 📦 Key Libraries

*   `lucide-react`: Iconography.
*   `react-markdown`: Rendering AI responses.
*   `remark-gfm`: GitHub Flavored Markdown support (tables, strikethrough).
