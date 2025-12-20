import React, { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { Send, Sparkles, RotateCcw, User, Cpu, Database } from 'lucide-react';

import ReasoningAccordion from './ReasoningAccordion';
import '../common/EmptyState.css'; // Reuse empty state styles
import './ChatInterface.css';

const ChatInterface = ({
    messages,
    input,
    setInput,
    handleSendMessage,
    loading,
    selectedTables,
    onClearChat
}) => {
    const messagesEndRef = useRef(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, loading]);

    return (
        <div className="chat-wrapper">
            <div className="chat-header">
                <div className="chat-title">
                    <Sparkles size={18} color="var(--accent-primary)" />
                    <span>Data Assistant</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <div className="chat-badge">
                        {selectedTables.length} Contexts Active
                    </div>
                    <button
                        className="icon-btn"
                        onClick={onClearChat}
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
                                            <ReactMarkdown
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
                                                {msg.content}
                                            </ReactMarkdown>
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
    );
};

export default ChatInterface;
