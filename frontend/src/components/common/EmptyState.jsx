import React from 'react';
import { Database } from 'lucide-react';
import './EmptyState.css';

const EmptyState = () => {
    return (
        <div className="empty-state">
            <div className="empty-icon"><Database size={32} /></div>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '1rem' }}>Welcome to DataTalk</h2>
            <p style={{ maxWidth: 500, lineHeight: 1.6 }}>
                Upload a CSV file using the button in the sidebar to get started.
                <br />
                Once uploaded, you can select it to begin a conversation.
            </p>
        </div>
    );
};

export default EmptyState;
