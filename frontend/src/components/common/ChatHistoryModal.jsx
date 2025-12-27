import React, { useState } from 'react';
import { X, MessageSquare, Trash2, Clock, Loader } from 'lucide-react';
import './ChatHistoryModal.css';

const formatDate = (dateString) => {
    if (!dateString) return 'Unknown';
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
        return 'Today ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (diffDays === 1) {
        return 'Yesterday';
    } else if (diffDays < 7) {
        return `${diffDays} days ago`;
    } else {
        return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }
};

const ChatHistoryModal = ({ sessions, onSelect, onDelete, onClose, loading }) => {
    const [deletingId, setDeletingId] = useState(null);
    const [selectingId, setSelectingId] = useState(null);

    const handleSelect = async (session) => {
        setSelectingId(session.thread_id);
        try {
            await onSelect(session);
        } finally {
            setSelectingId(null);
        }
    };

    const handleDelete = async (e, session) => {
        e.stopPropagation();
        if (!window.confirm('Are you sure you want to delete this conversation?')) {
            return;
        }
        setDeletingId(session.thread_id);
        try {
            await onDelete(session);
        } finally {
            setDeletingId(null);
        }
    };

    return (
        <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
            <div className="chat-history-modal">
                <div className="modal-header">
                    <div className="modal-title">
                        <MessageSquare size={20} />
                        <span>Chat History</span>
                    </div>
                    <button className="close-btn" onClick={onClose}>
                        <X size={20} />
                    </button>
                </div>

                <div className="modal-body">
                    {loading ? (
                        <div className="loading-state">
                            <Loader className="spin" size={24} />
                            <span>Loading conversations...</span>
                        </div>
                    ) : sessions.length === 0 ? (
                        <div className="empty-state">
                            <MessageSquare size={48} />
                            <h3>No conversations yet</h3>
                            <p>Your chat history will appear here</p>
                        </div>
                    ) : (
                        <div className="sessions-list">
                            {sessions.map((session) => (
                                <div
                                    key={session.thread_id}
                                    className={`session-item ${selectingId === session.thread_id ? 'loading' : ''}`}
                                    onClick={() => !selectingId && handleSelect(session)}
                                    style={{ pointerEvents: selectingId ? 'none' : 'auto' }}
                                >
                                    <div className="session-content">
                                        <div className="session-title">
                                            {selectingId === session.thread_id ? (
                                                <><Loader className="spin" size={14} /> Loading...</>
                                            ) : (
                                                session.title || 'New Chat'
                                            )}
                                        </div>
                                        <div className="session-meta">
                                            <Clock size={12} />
                                            <span>{formatDate(session.updated_at)}</span>
                                        </div>
                                    </div>
                                    <button
                                        className="delete-btn"
                                        onClick={(e) => handleDelete(e, session)}
                                        disabled={deletingId === session.thread_id}
                                        title="Delete conversation"
                                    >
                                        {deletingId === session.thread_id ? (
                                            <Loader className="spin" size={16} />
                                        ) : (
                                            <Trash2 size={16} />
                                        )}
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ChatHistoryModal;
