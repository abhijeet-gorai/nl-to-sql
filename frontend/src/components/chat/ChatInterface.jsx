import React, { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { Send, Sparkles, RotateCcw, User, Cpu, Database, Users, Upload, Link, Table, Coins } from 'lucide-react';

import ReasoningAccordion from './ReasoningAccordion';
import VegaChartRenderer from './VegaChartRenderer';
import ProfileMenu from '../common/ProfileMenu';
import TokenBadge from '../common/TokenTooltip';
import '../common/EmptyState.css'; // Reuse empty state styles

// Helper function to render content with inline charts
const renderContentWithCharts = (content, charts) => {
    if (!charts || charts.length === 0) {
        return <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]} components={{
            table: ({ ...props }) => (
                <div className="table-wrapper">
                    <table {...props} />
                </div>
            )
        }}>{content}</ReactMarkdown>;
    }

    // Track which charts have been referenced
    const referencedCharts = new Set();

    // Split content by [CHART:n] markers
    const parts = [];
    let lastIndex = 0;
    const chartRegex = /\[CHART:(\d+)\]/g;
    let match;

    while ((match = chartRegex.exec(content)) !== null) {
        const chartIndex = parseInt(match[1], 10);

        // Add text before the marker
        if (match.index > lastIndex) {
            parts.push({
                type: 'text',
                content: content.substring(lastIndex, match.index)
            });
        }

        // Add chart if it exists
        if (chartIndex < charts.length) {
            parts.push({
                type: 'chart',
                index: chartIndex,
                spec: charts[chartIndex]
            });
            referencedCharts.add(chartIndex);
        }

        lastIndex = match.index + match[0].length;
    }

    // Add remaining text
    if (lastIndex < content.length) {
        parts.push({
            type: 'text',
            content: content.substring(lastIndex)
        });
    }

    // Find unreferenced charts
    const unreferencedCharts = charts
        .map((spec, idx) => ({ spec, idx }))
        .filter(({ idx }) => !referencedCharts.has(idx));

    return (
        <>
            {parts.map((part, idx) => {
                if (part.type === 'text') {
                    return (
                        <ReactMarkdown
                            key={idx}
                            remarkPlugins={[remarkGfm]}
                            rehypePlugins={[rehypeRaw]}
                            components={{
                                table: ({ ...props }) => (
                                    <div className="table-wrapper">
                                        <table {...props} />
                                    </div>
                                )
                            }}
                        >
                            {part.content}
                        </ReactMarkdown>
                    );
                } else {
                    return <VegaChartRenderer key={`chart-${idx}`} spec={part.spec} />;
                }
            })}
            {unreferencedCharts.length > 0 && (
                <div className="charts-container">
                    {unreferencedCharts.map(({ spec, idx }) => (
                        <VegaChartRenderer key={`unreferenced-${idx}`} spec={spec} />
                    ))}
                </div>
            )}
        </>
    );
};
import './ChatInterface.css';

const ChatInterface = ({
    messages,
    input,
    setInput,
    handleSendMessage,
    loading,
    selectedTables,
    onClearChat,
    onShowMembers,
    onChangePassword,
    onCredentials,
    hasTablesAvailable,
    sessionTokens
}) => {
    const messagesEndRef = useRef(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, loading]);

    const hasSelection = selectedTables.length > 0;

    return (
        <div className="chat-wrapper">
            <div className="chat-header">
                <div className="chat-title">
                    <Sparkles size={18} color="var(--accent-primary)" />
                    <span>Data Assistant</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    {sessionTokens && (
                        <TokenBadge data={sessionTokens} type="session" position="bottom">
                            <Coins size={14} />
                            <span>{sessionTokens.current_session_tokens?.toLocaleString() || 0}</span>
                        </TokenBadge>
                    )}
                    <div className="chat-badge">
                        {selectedTables.length} Contexts Active
                    </div>
                    {onShowMembers && (
                        <button
                            className="icon-btn"
                            onClick={onShowMembers}
                            title="Project Members"
                        >
                            <Users size={18} />
                        </button>
                    )}
                    <button
                        className="icon-btn"
                        onClick={onClearChat}
                        title="Clear Chat"
                        disabled={messages.length === 0}
                        style={{ opacity: messages.length === 0 ? 0.5 : 1 }}
                    >
                        <RotateCcw size={18} />
                    </button>
                    <ProfileMenu onChangePassword={onChangePassword} onCredentials={onCredentials} />
                </div>
            </div>

            <div className="chat-area">
                {messages.length === 0 && (
                    <div className="empty-state">
                        <div className="empty-icon">
                            {hasSelection ? <Sparkles size={32} /> : <Database size={32} />}
                        </div>
                        {hasSelection ? (
                            <>
                                <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                                    Ready to Analyze
                                </h3>
                                <p style={{ maxWidth: 400 }}>
                                    Ask questions about your selected datasets. I can run SQL queries and visualize data for you.
                                </p>
                            </>
                        ) : (
                            <>
                                <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                                    Welcome to DataTalk
                                </h3>
                                <p style={{ maxWidth: 400, marginBottom: '1.5rem' }}>
                                    Get started by adding your data sources to begin analyzing and querying your data.
                                </p>
                                <div className="empty-actions">
                                    <div className="empty-action-item">
                                        <Upload size={16} />
                                        <span>Upload a CSV file</span>
                                    </div>
                                    <div className="empty-action-item">
                                        <Link size={16} />
                                        <span>Add a database connection</span>
                                    </div>
                                    <div className="empty-action-item">
                                        <Table size={16} />
                                        <span>Browse & sync external tables</span>
                                    </div>
                                    {hasTablesAvailable && (
                                        <div className="empty-action-item highlight">
                                            <Database size={16} />
                                            <span>Select existing tables from sidebar</span>
                                        </div>
                                    )}
                                </div>
                            </>
                        )}
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
                                            {renderContentWithCharts(msg.content, msg.charts)}
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
                        placeholder={hasSelection ? "Ask a question about your data..." : "Select tables from the sidebar to start..."}
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        disabled={loading || !hasSelection}
                    />
                    <button className="send-button" disabled={loading || !input.trim() || !hasSelection}>
                        <Send size={18} />
                    </button>
                </form>
            </div>
        </div>
    );
};

export default ChatInterface;
