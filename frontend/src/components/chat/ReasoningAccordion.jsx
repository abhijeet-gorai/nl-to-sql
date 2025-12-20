import React, { useState } from 'react';
import { ChevronRight, ChevronDown, Terminal } from 'lucide-react';
import './ReasoningAccordion.css';

// Individual Step Item with internal state
const StepItem = ({ step }) => {
    const [isExpanded, setIsExpanded] = useState(false);

    const toggleStep = () => setIsExpanded(!isExpanded);

    return (
        <div className="step-item">
            <div className="step-header" onClick={toggleStep}>
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

// Main Accordion with internal state
const ReasoningAccordion = ({ steps }) => {
    const [isOpen, setIsOpen] = useState(false);

    const toggleReasoning = () => setIsOpen(!isOpen);

    return (
        <div className="reasoning-block">
            <div className="reasoning-header" onClick={toggleReasoning}>
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

export default ReasoningAccordion;
