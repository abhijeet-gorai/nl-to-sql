import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Upload, FileText, Send, Database, Loader2, AlertCircle, X } from 'lucide-react';
import './index.css';

const API_BASE_URL = 'http://localhost:8000';

function App() {
  const [file, setFile] = useState(null);
  const [schema, setSchema] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const droppedFile = e.dataTransfer.files[0];
    validateAndSetFile(droppedFile);
  };

  const handleFileSelect = (e) => {
    const selectedFile = e.target.files[0];
    validateAndSetFile(selectedFile);
  };

  const validateAndSetFile = (selectedFile) => {
    if (selectedFile && selectedFile.type === 'text/csv') {
      setFile(selectedFile);
      setError(null);
      handleUpload(selectedFile);
    } else {
      setError('Please upload a valid CSV file.');
    }
  };

  const handleUpload = async (fileToUpload) => {
    setUploading(true);
    const formData = new FormData();
    formData.append('file', fileToUpload);

    try {
      const response = await axios.post(`${API_BASE_URL}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setSchema(response.data.schema);
      setMessages([{ role: 'system', content: `File "${fileToUpload.name}" uploaded successfully. You can now ask questions about your data.` }]);
    } catch (err) {
      setError('Failed to upload file. Please try again.');
      console.error(err);
      setFile(null);
    } finally {
      setUploading(false);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = input;
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);

    try {
      const response = await axios.post(`${API_BASE_URL}/chat`, {
        message: userMessage,
      });
      setMessages((prev) => [...prev, { role: 'ai', content: response.data.response, steps: response.data.steps }]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'error', content: 'An error occurred while processing your request.' }]);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      <div className="background-shapes">
        <div className="shape shape-1"></div>
        <div className="shape shape-2"></div>
      </div>

      <main className="main-content">
        <header className="header">
          <h1 className="logo">
            <Database className="logo-icon" />
            DataTalk <span className="logo-highlight">AI</span>
          </h1>
          <p className="subtitle">Transform your CSV data into insights with natural language.</p>
        </header>

        <div className="grid-layout">
          {/* Left Panel: Upload & Schema */}
          <div className="panel left-panel">
            <div
              className={`upload-zone ${file ? 'active' : ''}`}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onClick={() => document.getElementById('fileInput').click()}
            >
              <input
                type="file"
                id="fileInput"
                accept=".csv"
                hidden
                onChange={handleFileSelect}
              />
              {uploading ? (
                <div className="upload-status">
                  <Loader2 className="animate-spin" size={48} />
                  <p>Processing data...</p>
                </div>
              ) : file ? (
                <div className="file-info">
                  <FileText size={48} className="file-icon" />
                  <div className="file-details">
                    <p className="filename">{file.name}</p>
                    <p className="filesize">{(file.size / 1024).toFixed(1)} KB</p>
                  </div>
                  <button
                    className="remove-file"
                    onClick={(e) => { e.stopPropagation(); setFile(null); setSchema(null); }}
                  >
                    <X size={20} />
                  </button>
                </div>
              ) : (
                <div className="upload-prompt">
                  <Upload size={48} className="upload-icon" />
                  <p className="upload-text">Drag & drop your CSV here</p>
                  <p className="upload-subtext">or click to browse</p>
                </div>
              )}
            </div>

            {error && (
              <div className="error-message">
                <AlertCircle size={20} />
                <span>{error}</span>
              </div>
            )}

            {schema && (
              <div className="schema-viewer glass-card">
                <h3><Database size={18} /> Data Schema</h3>
                <div className="schema-scroll">
                  <h4>Columns ({schema.columns.length})</h4>
                  <div className="tags">
                    {schema.columns.map((col) => (
                      <span key={col} className="tag">{col}</span>
                    ))}
                  </div>
                  <div className="row-count">
                    Total Rows: <strong>{schema.row_count}</strong>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Panel: Chat Interface */}
          <div className="panel right-panel glass-card">
            <div className="chat-history">
              {messages.length === 0 ? (
                <div className="empty-state">
                  <h3>Start the conversation</h3>
                  <p>Upload a CSV file and ask questions like:</p>
                  <ul>
                    <li>"Show me the top 5 distinct values in column X"</li>
                    <li>"What is the average of column Y?"</li>
                    <li>"List all rows where Z is greater than 100"</li>
                  </ul>
                </div>
              ) : (
                messages.map((msg, index) => (
                  <div key={index} className={`message ${msg.role}`}>
                    <div className="message-content">
                      {msg.role === 'ai' && <div className="message-header">AI Response</div>}
                      <div className="message-text">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                      </div>
                      {msg.steps && msg.steps.length > 0 && (
                        <div className="reasoning-accordion">
                          <details>
                            <summary>View Reasoning Steps</summary>
                            <div className="steps-list">
                              {msg.steps.map((step, i) => (
                                <div key={i} className="step-item">
                                  <div className="step-tool">Tools: <code>{step.tool}</code></div>
                                  <div className="step-input">Input: <code>{JSON.stringify(step.input)}</code></div>
                                  <div className="step-output">Output: <pre>{step.output}</pre></div>
                                </div>
                              ))}
                            </div>
                          </details>
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
              {loading && (
                <div className="message ai loading">
                  <div className="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <form className="chat-input-area" onSubmit={handleSendMessage}>
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={file ? "Ask a question about your data..." : "Please upload a file first..."}
                disabled={!file || loading}
                className="chat-input"
              />
              <button
                type="submit"
                className="send-button"
                disabled={!file || loading || !input.trim()}
              >
                <Send size={20} />
              </button>
            </form>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
