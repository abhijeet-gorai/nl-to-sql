import React, { useState } from 'react';
import './Tooltip.css';

const Tooltip = ({ children, content, position = 'bottom' }) => {
    const [isVisible, setIsVisible] = useState(false);

    return (
        <div
            className="tooltip-wrapper"
            onMouseEnter={() => setIsVisible(true)}
            onMouseLeave={() => setIsVisible(false)}
        >
            {children}
            <div className={`tooltip-content tooltip-${position} ${isVisible ? 'visible' : ''}`}>
                {content}
            </div>
        </div>
    );
};

export default Tooltip;
