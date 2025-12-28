import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Menu, Upload } from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { useProject } from '../context/ProjectContext';
import * as tablesApi from '../api/tables';
import { sendChatMessage } from '../api/chat';
import { getSessionTokenUsage, listChatSessions, getChatSession, deleteChatSession } from '../api/projects';

// Components
import ConnectionManager from '../components/ConnectionManager';
import TableBrowser from '../components/TableBrowser';
import MetadataEditor from '../components/MetadataEditor';
import Sidebar from '../components/layout/Sidebar';
import ChatInterface from '../components/chat/ChatInterface';
import AnalyzingOverlay from '../components/common/AnalyzingOverlay';
import ConfirmationModal from '../components/common/ConfirmationModal';
import MembersPanel from '../components/MembersPanel';
import ChangePasswordModal from '../components/common/ChangePasswordModal';
import CredentialsModal from '../components/common/CredentialsModal';
import ChatHistoryModal from '../components/common/ChatHistoryModal';

import '../App.css';

const WorkspacePage = () => {
    const navigate = useNavigate();
    const { projectId } = useParams();
    const { user } = useAuth();
    const {
        currentProject,
        selectProject,
        userRole,
        canWrite,
        isAdmin
    } = useProject();

    // --- State ---
    const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');
    const [view, setView] = useState('empty'); // 'empty', 'edit-metadata', 'chat'

    const [tables, setTables] = useState([]);

    const [selectedTables, setSelectedTables] = useState([]);

    const [stagingMetadata, setStagingMetadata] = useState(null);
    const [isUploading, setIsUploading] = useState(false);

    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [projectLoading, setProjectLoading] = useState(true);

    const [threadId, setThreadId] = useState("default");
    const [sessionTokens, setSessionTokens] = useState(null);

    // Modal State
    const [deleteConfirm, setDeleteConfirm] = useState({ isOpen: false, tableName: '' });
    const [isClearingChat, setIsClearingChat] = useState(false);
    const [showConnectionManager, setShowConnectionManager] = useState(false);
    const [showTableBrowser, setShowTableBrowser] = useState(false);
    const [showMembersPanel, setShowMembersPanel] = useState(false);

    const [successModal, setSuccessModal] = useState({ isOpen: false, message: '' });

    // Mobile Responsive State
    const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
    const [showChangePassword, setShowChangePassword] = useState(false);
    const [showCredentials, setShowCredentials] = useState(false);

    // Chat History State
    const [showChatHistory, setShowChatHistory] = useState(false);
    const [chatSessions, setChatSessions] = useState([]);
    const [sessionsLoading, setSessionsLoading] = useState(false);

    // Drag and Drop State
    const [isDragging, setIsDragging] = useState(false);
    const dragCounter = useRef(0);

    // Token limit exceeded modal
    const [showTokenLimitModal, setShowTokenLimitModal] = useState(false);

    const initialLoadRef = useRef(false);

    // --- Effects ---
    useEffect(() => {
        setThreadId(Math.random().toString(36).substring(7));
    }, [projectId]);

    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
    }, [theme]);

    // Load project on mount
    useEffect(() => {
        const loadProject = async () => {
            if (!projectId) {
                navigate('/projects');
                return;
            }

            setProjectLoading(true);
            try {
                await selectProject(parseInt(projectId, 10));
            } catch (error) {
                console.error('Failed to load project:', error);
                navigate('/projects');
            } finally {
                setProjectLoading(false);
            }
        };

        loadProject();
    }, [projectId, selectProject, navigate]);

    // Fetch tables when project is loaded
    useEffect(() => {
        if (currentProject && !projectLoading) {
            fetchTables();
        }
    }, [currentProject, projectLoading]);

    // Fetch session token usage 1 second after streaming completes
    useEffect(() => {
        // Only fetch when loading just finished (went from true to false)
        if (loading || !currentProject || !threadId || messages.length === 0) {
            return;
        }

        const timer = setTimeout(async () => {
            try {
                const usage = await getSessionTokenUsage(currentProject.id, threadId);
                setSessionTokens(usage);
            } catch (err) {
                console.error('Failed to fetch session tokens:', err);
            }
        }, 1000);

        return () => clearTimeout(timer);
    }, [loading, currentProject, threadId]);


    // --- Actions ---
    const toggleTheme = () => setTheme(prev => prev === 'dark' ? 'light' : 'dark');

    const fetchTables = async () => {
        if (!currentProject) return;

        try {
            const data = await tablesApi.getTables(currentProject.id);
            setTables(data);
        } catch (e) {
            console.error("Failed to fetch tables", e);
        }
    };

    const handleFileUpload = async (e) => {
        const file = e.target.files[0];
        if (!file || !currentProject) return;

        setIsUploading(true);

        try {
            const [data] = await Promise.all([
                tablesApi.analyzeFile(currentProject.id, file),
                new Promise(resolve => setTimeout(resolve, 800))
            ]);

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
            if (e.target) e.target.value = null;
        }
    };

    // Drag and Drop Handlers
    const handleDragEnter = useCallback((e) => {
        e.preventDefault();
        e.stopPropagation();
        dragCounter.current++;
        if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
            setIsDragging(true);
        }
    }, []);

    const handleDragLeave = useCallback((e) => {
        e.preventDefault();
        e.stopPropagation();
        dragCounter.current--;
        if (dragCounter.current === 0) {
            setIsDragging(false);
        }
    }, []);

    const handleDragOver = useCallback((e) => {
        e.preventDefault();
        e.stopPropagation();
    }, []);

    const handleDrop = useCallback(async (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
        dragCounter.current = 0;

        if (!canWrite) {
            alert('You do not have permission to upload files.');
            return;
        }

        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            // Check for multiple files
            if (files.length > 1) {
                alert('Please drop only one CSV file at a time.');
                return;
            }

            const file = files[0];
            if (!file.name.toLowerCase().endsWith('.csv')) {
                alert('Please drop a CSV file.');
                return;
            }

            if (!currentProject) return;

            setIsUploading(true);

            try {
                const [data] = await Promise.all([
                    tablesApi.analyzeFile(currentProject.id, file),
                    new Promise(resolve => setTimeout(resolve, 800))
                ]);

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
            }
        }
    }, [currentProject, canWrite]);

    const handleEditTable = (e, table) => {
        e.stopPropagation();
        setStagingMetadata([{
            ...table,
            isEditing: true
        }]);
        setView('edit-metadata');
    };

    const handleTablesSynced = (syncedTables) => {
        setShowTableBrowser(false);
        setStagingMetadata(syncedTables);
        setView('edit-metadata');
    };

    const handleSaveMetadata = async (tablesToSaveInput) => {
        if (!currentProject) return;

        const tablesToSave = Array.isArray(tablesToSaveInput) ? tablesToSaveInput : [tablesToSaveInput];
        if (tablesToSave.length === 0) return;

        try {
            const updatedTables = [];
            const registeredTables = [];

            for (const table of tablesToSave) {
                const isExternalTable = table.source_type !== 'csv';

                if (table.isEditing || isExternalTable) {
                    const options = {};
                    if (isExternalTable) {
                        options.sourceType = 'external';
                        options.connectionId = table.connection_id;
                        if (table.schema_name) {
                            options.schema = table.schema_name;
                        }
                    } else {
                        options.sourceType = 'csv';
                    }

                    await tablesApi.updateTable(currentProject.id, table.table_name, {
                        description: table.description,
                        columns: table.columns
                    }, options);

                    updatedTables.push(table.table_name);

                    if (isExternalTable && !table.isEditing) {
                        const newSelection = {
                            table_name: table.table_name,
                            source_type: 'external',
                            connection_id: table.connection_id,
                            schema_name: table.schema_name
                        };
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
                    const result = await tablesApi.registerTable(currentProject.id, {
                        file_path: table.file_path,
                        metadata: {
                            table_name: table.table_name,
                            original_filename: table.original_filename,
                            description: table.description,
                            columns: table.columns
                        }
                    });

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

            let message = '';
            if (updatedTables.length > 0) {
                message = `Metadata updated successfully for: ${updatedTables.join(', ')}`;
            } else if (registeredTables.length > 0) {
                message = `Tables registered successfully: ${registeredTables.join(', ')}`;
            }
            setSuccessModal({ isOpen: true, message });
        } catch (err) {
            alert(err.response?.data?.detail || err.message);
        }
    };

    const handleDeleteTable = (e, table) => {
        e.stopPropagation();

        let tableObj = table;
        if (typeof table === 'string') {
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
        if (!currentProject) return;

        const tableName = deleteConfirm.tableName;
        if (!tableName) return;

        let targetTable = null;
        if (Object.keys(deleteConfirm).length > 2) {
            targetTable = deleteConfirm;
        } else {
            targetTable = tables.find(t => t.table_name === tableName);
        }

        try {
            const options = {};
            if (targetTable) {
                const isExternal = targetTable.source_type !== 'csv';
                if (isExternal) {
                    options.sourceType = 'external';
                    options.connectionId = targetTable.connection_id;
                    if (targetTable.schema_name) {
                        options.schema = targetTable.schema_name;
                    }
                } else {
                    options.sourceType = 'csv';
                }
            }

            await tablesApi.deleteTable(currentProject.id, tableName, options);

            await fetchTables();
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
            alert(err.response?.data?.detail || err.message);
            setDeleteConfirm({ isOpen: false, tableName: '' });
        }
    };

    const handleTableToggle = (table) => {
        let tableObj = table;
        if (typeof table === 'string') {
            tableObj = tables.find(t => t.table_name === table);
            if (!tableObj) return;
        }

        const newSourceType = tableObj.source_type || 'csv';
        const newConnId = tableObj.connection_id;
        const newSchema = tableObj.schema_name;

        setSelectedTables(prev => {
            const existingIndex = prev.findIndex(t =>
                t.table_name === tableObj.table_name &&
                (t.source_type || 'csv') === newSourceType &&
                t.connection_id === newConnId &&
                t.schema_name === newSchema
            );

            if (existingIndex >= 0) {
                const newSel = [...prev];
                newSel.splice(existingIndex, 1);
                return newSel;
            } else {
                if (prev.length > 0) {
                    const first = prev[0];
                    const firstSource = (first.source_type || 'csv') === 'csv' ? 'csv' : first.connection_id;
                    const currentSource = newSourceType === 'csv' ? 'csv' : newConnId;

                    if (firstSource !== currentSource) {
                        alert('You can only select tables from a single database at a time. Please deselect other tables first.');
                        return prev;
                    }
                }

                return [...prev, {
                    table_name: tableObj.table_name,
                    source_type: newSourceType,
                    connection_id: newConnId,
                    schema_name: newSchema,
                    db_type: tableObj.db_type
                }];
            }
        });

        if (view === 'empty') setView('chat');
    };

    const handleGroupToggle = (groupTables) => {
        if (!groupTables || groupTables.length === 0) return;

        const targetSourceType = groupTables[0].source_type || 'csv';
        const targetConnId = groupTables[0].connection_id;

        const allSelected = groupTables.every(table =>
            selectedTables.some(t =>
                t.table_name === table.table_name &&
                (t.source_type || 'csv') === (table.source_type || 'csv') &&
                t.connection_id === table.connection_id &&
                t.schema_name === table.schema_name
            )
        );

        setSelectedTables(prev => {
            if (allSelected) {
                return prev.filter(t => !groupTables.some(gt =>
                    gt.table_name === t.table_name &&
                    (gt.source_type || 'csv') === (t.source_type || 'csv') &&
                    gt.connection_id === t.connection_id &&
                    gt.schema_name === t.schema_name
                ));
            } else {
                if (prev.length > 0) {
                    const first = prev[0];
                    const firstSource = (first.source_type || 'csv') === 'csv' ? 'csv' : first.connection_id;
                    const currentSource = targetSourceType === 'csv' ? 'csv' : targetConnId;

                    if (firstSource !== currentSource) {
                        alert('You can only select tables from a single database at a time. Please deselect other tables first.');
                        return prev;
                    }
                }

                const newSelection = [...prev];
                groupTables.forEach(table => {
                    const exists = newSelection.some(t =>
                        t.table_name === table.table_name &&
                        (t.source_type || 'csv') === (table.source_type || 'csv') &&
                        t.connection_id === table.connection_id &&
                        t.schema_name === table.schema_name
                    );

                    if (!exists) {
                        newSelection.push({
                            table_name: table.table_name,
                            source_type: table.source_type || 'csv',
                            connection_id: table.connection_id,
                            schema_name: table.schema_name,
                            db_type: table.db_type
                        });
                    }
                });
                return newSelection;
            }
        });

        if (view === 'empty') setView('chat');
    };

    const handleSendMessage = async (e) => {
        e.preventDefault();
        if (!input.trim() || loading || !currentProject) return;

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

            const response = await sendChatMessage(
                currentProject.id,
                userMessage,
                selectedTables,
                threadId
            );

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
                            } else if (data.type === 'charts') {
                                // Store chart specifications in the message
                                lastMsg.charts = data.charts;
                            } else if (data.type === 'error') {
                                // Handle streaming error from agent
                                lastMsg.content = (lastMsg.content || '') + `\n\n⚠️ **Error:** ${data.error}`;
                                lastMsg.hasError = true;
                            }
                            newMessages[lastMsgIndex] = lastMsg;
                            return newMessages;
                        });
                    } catch (e) { console.error(e); }
                }
                buffer = lines[lines.length - 1];
            }
        } catch (err) {
            // Handle specific error responses
            if (err.response || err.status) {
                const status = err.status || err.response?.status;
                if (status === 429) {
                    // Token limit exceeded - show modal instead of chat error
                    // Remove the empty AI message we added
                    setMessages(prev => prev.slice(0, -1));
                    setShowTokenLimitModal(true);
                    return;
                }
            }

            setMessages(prev => [...prev, { role: 'error', content: 'Sorry, I encountered an error processing your request.' }]);
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const confirmClearChat = () => {
        setMessages([]);
        setThreadId(Math.random().toString(36).substring(7));
        setSessionTokens(null);
        setIsClearingChat(false);
    };

    // --- Chat History Handlers ---
    const fetchChatSessions = async () => {
        if (!currentProject?.id) return;
        setSessionsLoading(true);
        try {
            const data = await listChatSessions(currentProject.id);
            setChatSessions(data);
        } catch (err) {
            console.error('Failed to fetch chat sessions:', err);
        } finally {
            setSessionsLoading(false);
        }
    };

    const handleOpenChatHistory = () => {
        fetchChatSessions();
        setShowChatHistory(true);
    };

    const handleSelectSession = async (session) => {
        try {
            const data = await getChatSession(currentProject.id, session.thread_id);
            setMessages(data.messages || []);
            setThreadId(session.thread_id);
            setSessionTokens(null);
            setShowChatHistory(false);
            setView('chat');
        } catch (err) {
            console.error('Failed to load session:', err);
            alert('Failed to load conversation');
        }
    };

    const handleDeleteSession = async (session) => {
        try {
            await deleteChatSession(currentProject.id, session.thread_id);
            fetchChatSessions();
        } catch (err) {
            console.error('Failed to delete session:', err);
        }
    };

    const goBack = () => {
        navigate('/projects');
    };

    // --- Loading State ---
    if (projectLoading) {
        return (
            <div className="app-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
                    <div className="loading-spinner" style={{ marginBottom: '1rem' }}></div>
                    <p>Loading project...</p>
                </div>
            </div>
        );
    }

    // --- Render ---
    return (
        <div
            className="app-container"
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
        >
            {/* Drag and Drop Overlay */}
            {isDragging && canWrite && (
                <div className="drop-overlay">
                    <div className="drop-content">
                        <Upload size={48} />
                        <h3>Drop CSV file here</h3>
                        <p>Release to start analyzing</p>
                    </div>
                </div>
            )}

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
            {isMobileSidebarOpen && (
                <div
                    className="mobile-sidebar-overlay"
                    onClick={() => setIsMobileSidebarOpen(false)}
                />
            )}

            <Sidebar
                tables={tables}
                selectedTables={selectedTables}
                onUpload={canWrite ? handleFileUpload : null}
                onConnect={canWrite ? () => setShowConnectionManager(true) : null}
                onBrowse={canWrite ? () => setShowTableBrowser(true) : null}
                onChatHistory={handleOpenChatHistory}
                onToggleTable={handleTableToggle}
                onToggleGroup={handleGroupToggle}
                onEditTable={canWrite ? handleEditTable : null}
                onDeleteTable={canWrite ? handleDeleteTable : null}
                toggleTheme={toggleTheme}
                theme={theme}
                isOpen={isMobileSidebarOpen}
                onClose={() => setIsMobileSidebarOpen(false)}
                projectName={currentProject?.name}
                onBack={goBack}
                userRole={userRole}
            />

            {/* Main Content */}
            <main className="main-content">
                {/* Mobile Header with Menu Button */}
                <div className="mobile-header">
                    <button
                        className="icon-btn"
                        onClick={() => setIsMobileSidebarOpen(true)}
                    >
                        <Menu size={24} />
                    </button>
                    <span className="brand-text-mobile">{currentProject?.name || 'DataTalk'}</span>
                    <div style={{ width: 24 }} /> {/* Spacer for balance */}
                </div>

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

                {/* VIEW: Chat or Empty - Always show ChatInterface */}
                {(view === 'chat' || view === 'empty') && (
                    <ChatInterface
                        messages={messages}
                        input={input}
                        setInput={setInput}
                        handleSendMessage={handleSendMessage}
                        loading={loading}
                        selectedTables={selectedTables}
                        onClearChat={() => setIsClearingChat(true)}
                        onShowMembers={() => setShowMembersPanel(true)}
                        onChangePassword={() => setShowChangePassword(true)}
                        onCredentials={() => setShowCredentials(true)}
                        hasTablesAvailable={tables.length > 0}
                        sessionTokens={sessionTokens}
                    />
                )}

            </main>

            {/* Connection Manager Modal */}
            {showConnectionManager && (
                <ConnectionManager
                    projectId={currentProject?.id}
                    onClose={() => setShowConnectionManager(false)}
                    onConnectionsChange={() => {
                        fetchTables();
                    }}
                />
            )}

            {/* Table Browser Modal */}
            {showTableBrowser && (
                <TableBrowser
                    projectId={currentProject?.id}
                    onClose={() => setShowTableBrowser(false)}
                    onTablesSynced={handleTablesSynced}
                />
            )}

            {/* Members Panel */}
            {showMembersPanel && (
                <MembersPanel
                    onClose={() => setShowMembersPanel(false)}
                />
            )}

            {/* Change Password Modal */}
            {showChangePassword && (
                <ChangePasswordModal
                    onClose={() => setShowChangePassword(false)}
                />
            )}

            {/* Credentials Modal */}
            {showCredentials && (
                <CredentialsModal
                    onClose={() => setShowCredentials(false)}
                />
            )}

            {/* Chat History Modal */}
            {showChatHistory && (
                <ChatHistoryModal
                    sessions={chatSessions}
                    onSelect={handleSelectSession}
                    onDelete={handleDeleteSession}
                    onClose={() => setShowChatHistory(false)}
                    loading={sessionsLoading}
                />
            )}

            {/* Token Limit Exceeded Modal */}
            <ConfirmationModal
                isOpen={showTokenLimitModal}
                title="Daily Token Limit Reached"
                message="You have exceeded the daily token limit of 50,000 tokens for the free tier. To continue using the chat, please add your own Groq API key."
                confirmText="Add API Key"
                onConfirm={() => {
                    setShowTokenLimitModal(false);
                    setShowCredentials(true);
                }}
                onCancel={() => setShowTokenLimitModal(false)}
            />
        </div>
    );
};

export default WorkspacePage;
