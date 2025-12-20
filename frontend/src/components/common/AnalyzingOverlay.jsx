import React from 'react';
import './AnalyzingOverlay.css';

const AnalyzingOverlay = () => (
    <div className="overlay">
        <div className="loader-box">
            <div className="spinner"></div>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Analyzing Dataset</div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Extracting schema and metadata...</div>
        </div>
    </div>
);

export default AnalyzingOverlay;
