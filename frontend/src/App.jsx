import React, { useState, useEffect, useRef } from 'react';
import './index.css';

// Components
import ConnectionManager from './components/ConnectionManager';
import TableBrowser from './components/TableBrowser';
import MetadataEditor from './components/MetadataEditor';
import Sidebar from './components/layout/Sidebar';
import ChatInterface from './components/chat/ChatInterface';
import AnalyzingOverlay from './components/common/AnalyzingOverlay';
import ConfirmationModal from './components/common/ConfirmationModal';
import EmptyState from './components/common/EmptyState';

const API_BASE_URL = 'http://localhost:8000';

function App() {
    // --- State ---
    const [theme, setTheme] = useState('dark');
    const [view, setView] = useState('empty'); // 'empty', 'edit-metadata', 'chat'

    const [tables, setTables] = useState([]);

    // Changed from selectedTableIds (strings) to selectedTables (objects)
    const [selectedTables, setSelectedTables] = useState([]);

    const [stagingMetadata, setStagingMetadata] = useState(null);
    const [isUploading, setIsUploading] = useState(false);

    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);

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
                source_type: 'csv',
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

    const handleSaveMetadata = async (tablesToSaveInput) => {
        const tablesToSave = Array.isArray(tablesToSaveInput) ? tablesToSaveInput : [tablesToSaveInput];
        if (tablesToSave.length === 0) return;

        try {
            const updatedTables = [];
            const registeredTables = [];

            for (const table of tablesToSave) {
                // Check if it's an external table (has source_type='external' or schema_name)
                const isExternalTable = table.source_type !== 'csv';

                if (table.isEditing || isExternalTable) {
                    // Update existing table OR newly synced external table (both use PUT)
                    let queryParams = '';

                    if (isExternalTable) {
                        queryParams = `?source_type=external&connection_id=${table.connection_id}`;
                        if (table.schema_name) {
                            queryParams += `&schema=${table.schema_name}`;
                        }
                    } else {
                        queryParams = '?source_type=csv';
                    }

                    const res = await fetch(`${API_BASE_URL}/tables/${table.table_name}${queryParams}`, {
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
                        const newSelection = {
                            table_name: table.table_name,
                            source_type: 'external',
                            connection_id: table.connection_id,
                            schema_name: table.schema_name
                        };
                        // Add if not exists
                        setSelectedTables(prev => {
                            const exists = prev.some(t =>
                                t.table_name === newSelection.table_name &&
                                t.connection_id === newSelection.connection_id &&
                                t.schema_name === newSelection.schema_name
                            );
                            return exists ? prev : [...prev, newSelection];
                        });
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

                    const newSelection = {
                        table_name: result.table_name,
                        source_type: 'csv'
                    };
                    setSelectedTables(prev => [...prev, newSelection]);
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

    const handleDeleteTable = (e, table) => {
        e.stopPropagation();

        // table should be the full object passed from Sidebar
        let tableObj = table;
        if (typeof table === 'string') {
            // Fallback lookup if for some reason a string is passed
            tableObj = tables.find(t => t.table_name === table);
        }

        setDeleteConfirm({
            isOpen: true,
            tableName: tableObj.table_name,
            source_type: tableObj.source_type,
            connection_id: tableObj.connection_id,
            schema_name: tableObj.schema_name
        });
    };

    const proceedWithDelete = async () => {
        const tableName = deleteConfirm.tableName;
        if (!tableName) return;

        let targetTable = null;
        if (Object.keys(deleteConfirm).length > 2) {
            targetTable = deleteConfirm; // Use stored details
        } else {
            targetTable = tables.find(t => t.table_name === tableName);
        }

        try {
            let queryParams = '';
            if (targetTable) {
                const isExternal = targetTable.source_type !== 'csv';
                if (isExternal) {
                    queryParams = `?source_type=external&connection_id=${targetTable.connection_id}`;
                    if (targetTable.schema_name) {
                        queryParams += `&schema=${targetTable.schema_name}`;
                    }
                } else {
                    queryParams = '?source_type=csv';
                }
            }

            const res = await fetch(`${API_BASE_URL}/tables/${tableName}${queryParams}`, {
                method: 'DELETE'
            });
            if (!res.ok) throw new Error("Failed to delete table");

            await fetchTables();
            // Remove from selection if deleted
            setSelectedTables(prev => prev.filter(t => t.table_name !== tableName));
            // Note: This filter by only table_name might be loose if multiple tables have same name.
            // But usually user deletes one specific table. 
            // Correct approach: filter by composite key.
            setSelectedTables(prev => prev.filter(t => {
                if (targetTable.source_type === 'csv') {
                    return !(t.table_name === tableName && t.source_type === 'csv');
                } else {
                    return !(t.table_name === tableName && t.connection_id === targetTable.connection_id && t.schema_name === targetTable.schema_name);
                }
            }));

            if (selectedTables.length === 1 && selectedTables[0].table_name === tableName) {
                setView('empty');
            }

            setDeleteConfirm({ isOpen: false, tableName: '' });

        } catch (err) {
            alert(err.message);
            setDeleteConfirm({ isOpen: false, tableName: '' });
        }
    };

    const handleTableToggle = (table) => {
        // If passed a string (legacy/fallback), look it up
        let tableObj = table;
        if (typeof table === 'string') {
            // Trying to find it in 'tables' - might be ambiguous but fallback behavior
            tableObj = tables.find(t => t.table_name === table);
            if (!tableObj) return;
        }

        const newSourceType = tableObj.source_type || 'csv';
        const newConnId = tableObj.connection_id;
        const newSchema = tableObj.schema_name;

        setSelectedTables(prev => {
            // Check if already selected
            const existingIndex = prev.findIndex(t =>
                t.table_name === tableObj.table_name &&
                (t.source_type || 'csv') === newSourceType &&
                t.connection_id === newConnId &&
                t.schema_name === newSchema
            );

            if (existingIndex >= 0) {
                // Remove
                const newSel = [...prev];
                newSel.splice(existingIndex, 1);
                return newSel;
            } else {
                // Add
                // Check constraint: Single source only
                if (prev.length > 0) {
                    const first = prev[0];
                    const firstSource = (first.source_type || 'csv') === 'csv' ? 'csv' : first.connection_id;
                    const currentSource = newSourceType === 'csv' ? 'csv' : newConnId;

                    if (firstSource !== currentSource) {
                        alert('You can only select tables from a single database at a time. Please deselect other tables first.');
                        return prev;
                    }
                }

                // Add structured object
                return [...prev, {
                    table_name: tableObj.table_name,
                    source_type: newSourceType,
                    connection_id: newConnId,
                    schema_name: newSchema,
                    // Keep helpful metadata if needed
                    db_type: tableObj.db_type
                }];
            }
        });

        if (view === 'empty') setView('chat');
    };

    const handleSendMessage = async (e) => {
        e.preventDefault();
        if (!input.trim() || loading) return;

        if (selectedTables.length === 0) {
            alert("Please select at least one table.");
            return;
        }

        const userMessage = input;
        setInput('');
        setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
        setLoading(true);

        try {
            setMessages(prev => [...prev, { role: 'ai', content: '', steps: [] }]);

            // Format selected tables for backend
            // Backend expects: { table_name, source_type, connection_id, schema }
            const formattedTables = selectedTables.map(t => ({
                table_name: t.table_name,
                source_type: t.source_type || 'csv',
                connection_id: t.connection_id,
                schema: t.schema_name
            }));

            const response = await fetch(`${API_BASE_URL}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: userMessage,
                    selected_tables: formattedTables, // Send full objects
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
            <Sidebar
                tables={tables}
                selectedTables={selectedTables} // Passed as selectedTables (objects)
                onUpload={handleFileUpload}
                onConnect={() => setShowConnectionManager(true)}
                onBrowse={() => setShowTableBrowser(true)}
                onToggleTable={handleTableToggle}
                onEditTable={handleEditTable}
                onDeleteTable={handleDeleteTable}
                toggleTheme={toggleTheme}
                theme={theme}
            />

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
                    <ChatInterface
                        messages={messages}
                        input={input}
                        setInput={setInput}
                        handleSendMessage={handleSendMessage}
                        loading={loading}
                        selectedTables={selectedTables} // Passed as selectedTables
                        onClearChat={() => setIsClearingChat(true)}
                    />
                )}

                {/* VIEW: Empty */}
                {view === 'empty' && (
                    <EmptyState />
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
