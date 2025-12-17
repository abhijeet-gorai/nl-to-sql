import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Database, Send, Upload, Sun, Moon,
  Check, ChevronRight, ChevronDown,
  Terminal, Play, Cpu, Sparkles, User, Trash2, Pencil, RotateCcw, Link
} from 'lucide-react';
import './index.css';
import ConnectionManager from './components/ConnectionManager';
import TableBrowser from './components/TableBrowser';
import MetadataEditor from './components/MetadataEditor';

const API_BASE_URL = 'http://localhost:8000';

function App() {
  // --- State ---
  const [theme, setTheme] = useState('dark');
  const [view, setView] = useState('empty'); // 'empty', 'edit-metadata', 'chat'

  const [tables, setTables] = useState([]);
  const [selectedTableIds, setSelectedTableIds] = useState([]);
  const [expandedGroups, setExpandedGroups] = useState({ csv: true }); // Track which groups are expanded

  const [stagingMetadata, setStagingMetadata] = useState(null);
  const [isUploading, setIsUploading] = useState(false);

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);


  const messagesEndRef = useRef(null);
  const [threadId, setThreadId] = useState("default");

  // Modal State
  const [deleteConfirm, setDeleteConfirm] = useState({ isOpen: false, tableName: '' });
  const [isClearingChat, setIsClearingChat] = useState(false);
  const [showConnectionManager, setShowConnectionManager] = useState(false);
  const [showTableBrowser, setShowTableBrowser] = useState(false);
  const [successModal, setSuccessModal] = useState({ isOpen: false, message: '' });
  const initialLoadRef = useRef(false);

  // --- Effects ---
  useEffect(() => {
    setThreadId(Math.random().toString(36).substring(7));
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    // Prevent double-invocation in development
    if (initialLoadRef.current) return;
    initialLoadRef.current = true;
    
    fetchTables();
  }, []);

  useEffect(() => {
    // Only scroll if we are in chat view and messages exist
    if (view === 'chat') {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, view]);

  // --- Actions ---
  const toggleTheme = () => setTheme(prev => prev === 'dark' ? 'light' : 'dark');

  const fetchTables = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/tables`);
      if (res.ok) {
        const data = await res.json();
        setTables(data);
      }
    } catch (e) {
      console.error("Failed to fetch tables", e);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      // Simulate a small delay for better UX if API is too fast
      const [res] = await Promise.all([
        fetch(`${API_BASE_URL}/analyze`, { method: 'POST', body: formData }),
        new Promise(resolve => setTimeout(resolve, 800))
      ]);

      if (!res.ok) throw new Error("Analysis failed");

      const data = await res.json();

      setStagingMetadata([{
        ...data,
        table_name: data.suggested_table_name,
        columns: data.columns
      }]);
      setView('edit-metadata');

    } catch (err) {
      console.error(err);
      alert("Failed to upload/analyze file.");
    } finally {
      setIsUploading(false);
      e.target.value = null; // Reset input
    }
  };

  const handleEditTable = (e, table) => {
    e.stopPropagation();
    setStagingMetadata([{
      ...table,
      isEditing: true
    }]);
    setView('edit-metadata');
  };

  const handleTablesSynced = (syncedTables) => {
    // Close the browser and show metadata editor
    setShowTableBrowser(false);
    setStagingMetadata(syncedTables);
    setView('edit-metadata');
  };

  const handleSaveMetadata = async (tables) => {
    const tablesToSave = Array.isArray(tables) ? tables : [tables];
    if (tablesToSave.length === 0) return;

    try {
      const updatedTables = [];
      const registeredTables = [];

      for (const table of tablesToSave) {
        // Check if it's an external table (has source_type='external' or schema_name)
        const isExternalTable = table.source_type !== 'csv';
        
        if (table.isEditing || isExternalTable) {
          // Update existing table OR newly synced external table (both use PUT)
          const res = await fetch(`${API_BASE_URL}/tables/${table.table_name}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              metadata: {
                description: table.description,
                columns: table.columns
              }
            })
          });

          if (!res.ok) {
            const errorData = await res.json().catch(() => ({}));
            throw new Error(errorData.detail || "Update failed");
          }
          updatedTables.push(table.table_name);
          
          // Add newly synced external tables to selected tables
          if (isExternalTable && !table.isEditing) {
            setSelectedTableIds(prev => [...prev, table.table_name]);
          }
        } else {
          // Register new CSV table (POST /register)
          const res = await fetch(`${API_BASE_URL}/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              file_path: table.file_path,
              metadata: {
                table_name: table.table_name,
                original_filename: table.original_filename,
                description: table.description,
                columns: table.columns
              }
            })
          });

          if (!res.ok) throw new Error("Registration failed");
          const result = await res.json();
          setSelectedTableIds(prev => [...prev, result.table_name]);
          registeredTables.push(table.table_name);
        }
      }
      
      await fetchTables();
      setView('chat');
      setStagingMetadata(null);

      // Show success modal
      let message = '';
      if (updatedTables.length > 0) {
        message = `Metadata updated successfully for: ${updatedTables.join(', ')}`;
      } else if (registeredTables.length > 0) {
        message = `Tables registered successfully: ${registeredTables.join(', ')}`;
      }
      setSuccessModal({ isOpen: true, message });
    } catch (err) {
      alert(err.message);
    }
  };

  const handleDeleteTable = (e, tableName) => {
    e.stopPropagation();
    setDeleteConfirm({ isOpen: true, tableName });
  };

  const proceedWithDelete = async () => {
    const tableName = deleteConfirm.tableName;
    if (!tableName) return;

    try {
      const res = await fetch(`${API_BASE_URL}/tables/${tableName}`, {
        method: 'DELETE'
      });
      if (!res.ok) throw new Error("Failed to delete table");

      await fetchTables();
      setSelectedTableIds(prev => prev.filter(id => id !== tableName));

      if (selectedTableIds.includes(tableName) && selectedTableIds.length === 1) {
        setView('empty');
      }
      setDeleteConfirm({ isOpen: false, tableName: '' });

    } catch (err) {
      alert(err.message);
      setDeleteConfirm({ isOpen: false, tableName: '' });
    }
  };



  const toggleGroup = (groupKey) => {
    setExpandedGroups(prev => ({
      ...prev,
      [groupKey]: !prev[groupKey]
    }));
  };

  // Helper function to get database icon
  const getDbIcon = (dbType) => {
    const iconMap = {
      postgresql: '/postgresql.svg',
      db2: '/ibm-db2.svg',
      mysql: '/mysql.svg',
      oracle: '/oracle.svg'
    };
    return iconMap[dbType] || '/data-analytics.svg';
  };

  // Group tables by source
  const groupedTables = React.useMemo(() => {
    const groups = {
      csv: { name: 'Local CSV Files', icon: '📄', isEmoji: true, tables: [] },
    };

    tables.forEach(table => {
      if (table.source_type === 'csv' || !table.source_type) {
        groups.csv.tables.push(table);
      } else {
        // External database table
        const key = `ext_${table.connection_id}`;
        if (!groups[key]) {
          groups[key] = {
            name: table.source_name || 'External Database',
            icon: getDbIcon(table.db_type),
            isEmoji: false,
            tables: [],
            connection_id: table.connection_id
          };
        }
        groups[key].tables.push(table);
      }
    });

    // Remove empty groups
    return Object.entries(groups).filter(([, group]) => group.tables.length > 0);
  }, [tables]);

  const handleTableToggle = (tableName) => {
    // Ensure the table actually exists in the current `tables` state before toggling
    const table = tables.find(t => t.table_name === tableName);
    if (!table) {
      console.warn(`Attempted to toggle non-existent table: ${tableName}`);
      return;
    }

    setSelectedTableIds(prev => {
      if (prev.includes(tableName)) {
        // Deselecting
        return prev.filter(t => t !== tableName);
      } else {
        // Selecting - check if we can add this table
        if (prev.length === 0) {
          // First selection, allow
          return [tableName];
        }
        
        // Check if new table is from same source as existing selections
        const firstSelectedTable = tables.find(t => t.table_name === prev[0]);
        const newTableSource = table.source_type === 'csv' ? 'csv' : table.connection_id;
        const existingSource = firstSelectedTable.source_type === 'csv' ? 'csv' : firstSelectedTable.connection_id;
        
        if (newTableSource !== existingSource) {
          alert('You can only select tables from a single database at a time. Please deselect other tables first.');
          return prev;
        }
        
        return [...prev, tableName];
      }
    });
    // If we are in empty view and select a table, switch to chat
    if (view === 'empty') setView('chat');
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    if (selectedTableIds.length === 0) {
      alert("Please select at least one table.");
      return;
    }

    const userMessage = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);

    try {
      setMessages(prev => [...prev, { role: 'ai', content: '', steps: [] }]);

      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage,
          selected_tables: selectedTableIds,
          thread_id: threadId
        })
      });

      if (!response.ok) throw new Error(response.statusText);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');

        for (let i = 0; i < lines.length - 1; i++) {
          const line = lines[i].trim();
          if (!line) continue;

          try {
            const data = JSON.parse(line);
            setMessages(prev => {
              const newMessages = [...prev];
              const lastMsgIndex = newMessages.length - 1;
              const lastMsg = { ...newMessages[lastMsgIndex] };

              if (data.type === 'token') {
                lastMsg.content = (lastMsg.content || '') + data.content;
              } else if (data.type === 'tool_start') {
                if (!lastMsg.steps) lastMsg.steps = [];
                lastMsg.steps = [...lastMsg.steps, {
                  tool: data.tool,
                  input: data.input,
                  output: 'Running...'
                }];
              } else if (data.type === 'tool_end') {
                if (lastMsg.steps) {
                  const steps = [...lastMsg.steps];
                  for (let j = steps.length - 1; j >= 0; j--) {
                    if (steps[j].tool === data.tool && steps[j].output === 'Running...') {
                      steps[j] = { ...steps[j], output: data.output };
                      break;
                    }
                  }
                  lastMsg.steps = steps;
                }
              }
              newMessages[lastMsgIndex] = lastMsg;
              return newMessages;
            });
          } catch (e) { console.error(e); }
        }
        buffer = lines[lines.length - 1];
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: 'error', content: 'Sorry, I encountered an error processing your request.' }]);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const confirmClearChat = () => {
    setMessages([]);
    setThreadId(Math.random().toString(36).substring(7));
    setIsClearingChat(false);
  };

  // --- Sub-components ---

  const AnalyzingOverlay = () => (
    <div className="overlay">
      <div className="loader-box">
        <div className="spinner"></div>
        <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Analyzing Dataset</div>
        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Extracting schema and metadata...</div>
      </div>
    </div>
  );

  // New: Individual Step Item
  const StepItem = ({ step }) => {
    const [isExpanded, setIsExpanded] = useState(false);

    return (
      <div className="step-item">
        <div className="step-header" onClick={() => setIsExpanded(!isExpanded)}>
          <div style={{ transition: 'transform 0.2s', transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)', display: 'flex' }}>
            <ChevronRight size={14} color="var(--text-tertiary)" />
          </div>
          <div className="step-icon">
            <Terminal size={14} />
          </div>
          <span className="step-title">{step.tool}</span>
        </div>

        {isExpanded && (
          <div className="step-details">
            <div className="step-label">Input</div>
            <div className="step-code-block">
              {typeof step.input === 'object' ? JSON.stringify(step.input, null, 2) : step.input}
            </div>

            <div className="step-label">Result</div>
            <div className="step-code-block">
              {step.output}
            </div>
          </div>
        )}
      </div>
    );
  };

  // Updated: Main Accordion
  const ReasoningAccordion = ({ steps }) => {
    const [isOpen, setIsOpen] = useState(false);

    return (
      <div className="reasoning-block">
        <div className="reasoning-header" onClick={() => setIsOpen(!isOpen)}>
          {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          <span>View Reasoning Process ({steps.length} steps)</span>
        </div>
        {isOpen && (
          <div className="reasoning-content">
            {steps.map((step, i) => (
              <StepItem key={i} step={step} />
            ))}
          </div>
        )}
      </div>
    );
  };

  // New: Confirmation Modal
  const ConfirmationModal = ({ isOpen, title, message, onConfirm, onCancel, confirmText = "Confirm", isDanger = false }) => {
    if (!isOpen) return null;
    return (
      <div className="modal-overlay" onClick={onCancel}>
        <div className="modal-content" onClick={e => e.stopPropagation()}>
          <div className="modal-header">
            <div className="modal-title">{title}</div>
            <div className="modal-desc">{message}</div>
          </div>
          <div className="modal-actions">
            <button className="btn btn-ghost" onClick={onCancel}>Cancel</button>
            <button className={`btn ${isDanger ? 'btn-danger' : 'btn-primary'}`} onClick={onConfirm}>
              {confirmText}
            </button>
          </div>
        </div>
      </div>
    );
  };

  // --- Render ---
  return (
    <div className="app-container">
      {isUploading && <AnalyzingOverlay />}

      <ConfirmationModal
        isOpen={deleteConfirm.isOpen}
        title="Delete Dataset"
        message={`Are you sure you want to permanently delete "${deleteConfirm.tableName}"? This action cannot be undone.`}
        confirmText="Delete"
        isDanger={true}
        onConfirm={proceedWithDelete}
        onCancel={() => setDeleteConfirm({ isOpen: false, tableName: '' })}
      />

      <ConfirmationModal
        isOpen={isClearingChat}
        title="Clear Chat History"
        message="Are you sure you want to clear the current conversation? This will start a new session."
        confirmText="Clear Chat"
        isDanger={true}
        onConfirm={confirmClearChat}
        onCancel={() => setIsClearingChat(false)}
      />

      <ConfirmationModal
        isOpen={successModal.isOpen}
        title="Success"
        message={successModal.message}
        confirmText="OK"
        isDanger={false}
        onConfirm={() => setSuccessModal({ isOpen: false, message: '' })}
        onCancel={() => setSuccessModal({ isOpen: false, message: '' })}
      />

      {/* Sidebar */}
      <aside className="sidebar">
        <div className="brand">
          <Database size={24} color="var(--accent-primary)" />
          <span className="brand-text">DataTalk</span>
        </div>

        <label className="upload-label">
          <Upload size={16} />
          <span>Import CSV</span>
          <input type="file" hidden accept=".csv" onChange={handleFileUpload} />
        </label>

        <button
          className="secondary-button"
          onClick={() => setShowConnectionManager(true)}
        >
          <Link size={16} />
          <span>Connections</span>
        </button>

        <button
          className="secondary-button"
          onClick={() => setShowTableBrowser(true)}
        >
          <Database size={16} />
          <span>Browse Tables</span>
        </button>

        <div className="section-label">Datasets</div>
        <div className="table-list">
          {tables.length === 0 && (
            <div style={{ padding: '0 0.5rem', color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
              No data loaded yet.
            </div>
          )}
          
          {groupedTables.map(([groupKey, group]) => (
            <div key={groupKey} className="table-group">
              <div
                className="table-group-header"
                onClick={() => toggleGroup(groupKey)}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  {expandedGroups[groupKey] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  {group.isEmoji ? (
                    <span style={{ fontSize: '1.2rem' }}>{group.icon}</span>
                  ) : (
                    <img src={group.icon} alt={group.name} style={{ width: '20px', height: '20px' }} />
                  )}
                  <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{group.name}</span>
                  <span style={{
                    fontSize: '0.75rem',
                    color: 'var(--text-tertiary)',
                    marginLeft: '0.25rem'
                  }}>
                    ({group.tables.length})
                  </span>
                </div>
              </div>
              
              {expandedGroups[groupKey] && group.tables.map(table => (
                <div
                  key={table.id}
                  className={`nav-item ${selectedTableIds.includes(table.table_name) ? 'active' : ''}`}
                  onClick={() => handleTableToggle(table.table_name)}
                  style={{ marginLeft: '1rem' }}
                >
                  <div className="nav-item-icon">
                    {selectedTableIds.includes(table.table_name) ? <Check size={16} /> : <Database size={16} />}
                  </div>
                  <div className="nav-item-info">
                    <div className="nav-item-title">{table.table_name}</div>
                    <div className="nav-item-sub">{table.description || "No description"}</div>
                  </div>
                  <div className="nav-item-actions" style={{ marginLeft: 'auto', display: 'flex', gap: '0.25rem' }}>
                    <button
                      className="icon-btn edit-btn"
                      onClick={(e) => handleEditTable(e, table)}
                      title="Edit Metadata"
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      className="icon-btn delete-btn"
                      onClick={(e) => handleDeleteTable(e, table.table_name)}
                      title="Delete Table"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>

        <div className="sidebar-footer">
          <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
            v1.0.0
          </div>
          <button className="icon-btn" onClick={toggleTheme} title="Toggle Theme">
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">

        {/* VIEW: Metadata Editor */}
        {view === 'edit-metadata' && stagingMetadata && (
          <MetadataEditor
            tables={stagingMetadata}
            onSave={handleSaveMetadata}
            onCancel={() => {
              setStagingMetadata(null);
              setView(tables.length > 0 ? 'chat' : 'empty');
            }}
            isMultiple={Array.isArray(stagingMetadata) && stagingMetadata.length > 1}
          />
        )}

        {/* VIEW: Chat */}
        {view === 'chat' && (
          <div className="chat-wrapper">
            <div className="chat-header">
              <div className="chat-title">
                <Sparkles size={18} color="var(--accent-primary)" />
                <span>Data Assistant</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <div className="chat-badge">
                  {selectedTableIds.length} Contexts Active
                </div>
                <button
                  className="icon-btn"
                  onClick={() => setIsClearingChat(true)}
                  title="Clear Chat"
                  disabled={messages.length === 0}
                  style={{ opacity: messages.length === 0 ? 0.5 : 1 }}
                >
                  <RotateCcw size={18} />
                </button>
              </div>
            </div>

            <div className="chat-area">
              {messages.length === 0 && (
                <div className="empty-state">
                  <div className="empty-icon"><Database size={32} /></div>
                  <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.5rem' }}>Ready to Analyze</h3>
                  <p style={{ maxWidth: 400 }}>Ask questions about your selected datasets. I can run SQL queries and visualize data for you.</p>
                </div>
              )}

              {messages.map((msg, idx) => {
                // Check if this is an AI message that hasn't received content yet
                const isThinking = msg.role === 'ai' && !msg.content && (!msg.steps || msg.steps.length === 0);

                return (
                  <div key={idx} className="message">
                    <div className={`avatar ${msg.role}`}>
                      {msg.role === 'user' ? <User size={20} /> : <Cpu size={20} />}
                    </div>
                    <div className="msg-body">
                      <div className="msg-role-name">{msg.role === 'user' ? 'You' : 'Assistant'}</div>

                      {isThinking ? (
                        <div className="typing-indicator">
                          <span></span><span></span><span></span>
                        </div>
                      ) : (
                        <>
                          <div className="msg-content">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                          </div>
                          {msg.steps && msg.steps.length > 0 && (
                            <ReasoningAccordion steps={msg.steps} />
                          )}
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>

            <div className="input-wrapper">
              <form className="input-container" onSubmit={handleSendMessage}>
                <input
                  className="chat-input"
                  placeholder="Ask a question about your data..."
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  disabled={loading}
                />
                <button className="send-button" disabled={loading || !input.trim()}>
                  <Send size={18} />
                </button>
              </form>
            </div>
          </div>
        )}

        {/* VIEW: Empty */}
        {view === 'empty' && (
          <div className="empty-state">
            <div className="empty-icon"><Database size={32} /></div>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '1rem' }}>Welcome to DataTalk</h2>
            <p style={{ maxWidth: 500, lineHeight: 1.6 }}>
              Upload a CSV file using the button in the sidebar to get started.
              <br />
              Once uploaded, you can select it to begin a conversation.
            </p>
          </div>
        )}

      </main>

      {/* Connection Manager Modal */}
      {showConnectionManager && (
        <ConnectionManager
          onClose={() => setShowConnectionManager(false)}
          onConnectionsChange={() => {
            // Optionally refresh tables when connections change
            fetchTables();
          }}
        />
      )}

      {/* Table Browser Modal */}
      {showTableBrowser && (
        <TableBrowser
          onClose={() => setShowTableBrowser(false)}
          onTablesSynced={handleTablesSynced}
        />
      )}
    </div>
  );
}

export default App;