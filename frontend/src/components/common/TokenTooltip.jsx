import React from 'react';
import Tooltip from './Tooltip';
import './TokenTooltip.css';

/**
 * Token usage tooltip content component
 */
const TokenTooltipContent = ({ data, type = 'session' }) => {
    if (!data) return null;

    if (type === 'project') {
        return (
            <div className="token-tooltip-content">
                <div className="tooltip-row">
                    <span className="tooltip-label">Prompt Tokens</span>
                    <span className="tooltip-value">{data.prompt_tokens?.toLocaleString() || 0}</span>
                </div>
                <div className="tooltip-row">
                    <span className="tooltip-label">Completion Tokens</span>
                    <span className="tooltip-value">{data.completion_tokens?.toLocaleString() || 0}</span>
                </div>
                <div className="tooltip-divider" />
                <div className="tooltip-row">
                    <span className="tooltip-label">Total Tokens</span>
                    <span className="tooltip-value highlight">{data.total_tokens?.toLocaleString() || 0}</span>
                </div>
                <div className="tooltip-divider" />
                <div className="tooltip-row">
                    <span className="tooltip-label">Messages</span>
                    <span className="tooltip-value">{data.message_count || 0}</span>
                </div>
                <div className="tooltip-row">
                    <span className="tooltip-label">Sessions</span>
                    <span className="tooltip-value">{data.session_count || 0}</span>
                </div>
            </div>
        );
    }

    // Session type
    return (
        <div className="token-tooltip-content">
            <div className="tooltip-row">
                <span className="tooltip-label">Prompt Tokens</span>
                <span className="tooltip-value">{data.prompt_tokens?.toLocaleString() || 0}</span>
            </div>
            <div className="tooltip-row">
                <span className="tooltip-label">Completion Tokens</span>
                <span className="tooltip-value">{data.completion_tokens?.toLocaleString() || 0}</span>
            </div>
            <div className="tooltip-divider" />
            <div className="tooltip-row">
                <span className="tooltip-label">Total Consumed</span>
                <span className="tooltip-value">{data.total_tokens?.toLocaleString() || 0}</span>
            </div>
            <div className="tooltip-row">
                <span className="tooltip-label">Current Context</span>
                <span className="tooltip-value highlight">{data.current_session_tokens?.toLocaleString() || 0}</span>
            </div>
        </div>
    );
};

/**
 * Token display badge with tooltip
 */
const TokenBadge = ({ data, type = 'session', children, position = 'bottom' }) => {
    if (!data) return null;

    return (
        <Tooltip
            content={<TokenTooltipContent data={data} type={type} />}
            position={position}
        >
            <div className="token-badge-display">
                {children}
            </div>
        </Tooltip>
    );
};

export { TokenBadge, TokenTooltipContent };
export default TokenBadge;
