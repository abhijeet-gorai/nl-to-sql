import React, { useEffect, useState } from 'react';
import { VegaEmbed } from 'react-vega';
import './VegaChartRenderer.css';

const VegaChartRenderer = ({ spec }) => {
    const [theme, setTheme] = useState('dark');

    // Detect theme changes
    useEffect(() => {
        const updateTheme = () => {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
            setTheme(currentTheme);
        };

        // Initial theme
        updateTheme();

        // Watch for theme changes
        const observer = new MutationObserver(updateTheme);
        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['data-theme']
        });

        return () => observer.disconnect();
    }, []);

    // Vega-Lite config for dark/light mode
    const getThemeConfig = () => {
        if (theme === 'dark') {
            return {
                background: 'transparent',
                title: { color: '#e5e7eb' },
                style: {
                    'guide-label': { fill: '#9ca3af' },
                    'guide-title': { fill: '#e5e7eb' },
                },
                axis: {
                    domainColor: '#4b5563',
                    gridColor: '#374151',
                    tickColor: '#4b5563',
                    labelColor: '#9ca3af',
                    titleColor: '#e5e7eb',
                },
                legend: {
                    labelColor: '#9ca3af',
                    titleColor: '#e5e7eb',
                },
                mark: { color: '#3b82f6' },
                range: {
                    category: ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#06b6d4'],
                },
            };
        } else {
            return {
                background: 'transparent',
                title: { color: '#1f2937' },
                style: {
                    'guide-label': { fill: '#6b7280' },
                    'guide-title': { fill: '#1f2937' },
                },
                axis: {
                    domainColor: '#d1d5db',
                    gridColor: '#e5e7eb',
                    tickColor: '#d1d5db',
                    labelColor: '#6b7280',
                    titleColor: '#1f2937',
                },
                legend: {
                    labelColor: '#6b7280',
                    titleColor: '#1f2937',
                },
                mark: { color: '#2563eb' },
                range: {
                    category: ['#2563eb', '#7c3aed', '#db2777', '#d97706', '#059669', '#0891b2'],
                },
            };
        }
    };

    // Merge theme config with spec
    const themedSpec = {
        ...spec,
        config: {
            ...getThemeConfig(),
            ...(spec.config || {}),
        },
    };

    // Add actions config to enable download and other interactions
    const actions = {
        export: { svg: true, png: true },
        source: false,
        compiled: false,
        editor: false
    };

    return (
        <div className="vega-chart-container">
            <VegaEmbed 
                spec={themedSpec} 
                options={{ actions }}
            />
        </div>
    );
};

export default VegaChartRenderer;
