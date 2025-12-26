import React, { useState, useMemo } from 'react';
import {
    Database, Upload, Link, Sun, Moon,
    ChevronRight, ChevronDown, Check, Pencil, Trash2,
    CheckSquare, Square, MinusSquare, X, ArrowLeft, FolderKanban, History
} from 'lucide-react';
import './Sidebar.css';

const Sidebar = ({
    tables,
    selectedTables,
    onUpload,
    onConnect,
    onBrowse,
    onChatHistory,
    onToggleTable,
    onEditTable,
    onDeleteTable,
    onToggleGroup,
    toggleTheme,
    theme,
    isOpen,
    onClose,
    projectName,
    onBack,
    userRole
}) => {
    const [expandedGroups, setExpandedGroups] = useState({ csv: true });
    const [expandedSchemas, setExpandedSchemas] = useState({});

    const toggleGroup = (groupKey) => {
        setExpandedGroups(prev => ({
            ...prev,
            [groupKey]: !prev[groupKey]
        }));
    };

    const toggleSchema = (schemaKey) => {
        setExpandedSchemas(prev => ({
            ...prev,
            [schemaKey]: !prev[schemaKey]
        }));
    };

    // Helper function to get database icon
    const getDbIcon = (dbType) => {
        const iconMap = {
            postgresql: '/postgresql.svg',
            db2: '/ibm-db2.svg',
            mysql: '/mysql.svg',
            oracle: '/oracle.svg'
        };
        return iconMap[dbType] || '/data-analytics.svg';
    };

    // Check if user has write access
    const canWrite = userRole === 'write' || userRole === 'admin';

    // Group tables by source with schema hierarchy for external databases
    const groupedTables = useMemo(() => {
        const groups = {
            csv: { name: 'Uploaded CSV Files', icon: '📄', isEmoji: true, tables: [] },
        };

        tables.forEach(table => {
            if (table.source_type === 'csv' || !table.source_type) {
                groups.csv.tables.push(table);
            } else {
                // External database table - group by connection, then by schema
                const connKey = `ext_${table.connection_id}`;
                if (!groups[connKey]) {
                    groups[connKey] = {
                        name: table.source_name || 'External Database',
                        icon: getDbIcon(table.db_type),
                        isEmoji: false,
                        connection_id: table.connection_id,
                        schemas: {}
                    };
                }

                // Group tables by schema within the connection
                const schemaName = table.schema_name || 'default';
                if (!groups[connKey].schemas[schemaName]) {
                    groups[connKey].schemas[schemaName] = {
                        name: schemaName,
                        tables: []
                    };
                }
                groups[connKey].schemas[schemaName].tables.push(table);
            }
        });

        // Remove empty groups and convert schemas object to array
        return Object.entries(groups)
            .filter(([key, group]) => {
                if (key === 'csv') return group.tables.length > 0;
                return Object.keys(group.schemas).length > 0;
            })
            .map(([key, group]) => {
                if (key === 'csv') return [key, group];
                // Convert schemas object to array for external connections
                return [key, {
                    ...group,
                    schemas: Object.entries(group.schemas).map(([schemaName, schema]) => ({
                        key: `${key}_${schemaName}`,
                        ...schema
                    }))
                }];
            });
    }, [tables]);

    return (
        <aside className={`sidebar ${isOpen ? 'mobile-open' : ''}`}>
            <div className="brand">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    {onBack && (
                        <button
                            className="icon-btn back-btn"
                            onClick={onBack}
                            title="Back to Projects"
                        >
                            <ArrowLeft size={18} />
                        </button>
                    )}
                    {projectName ? (
                        <>
                            <FolderKanban size={20} color="var(--accent-primary)" />
                            <span className="brand-text project-name">{projectName}</span>
                        </>
                    ) : (
                        <>
                            <Database size={24} color="var(--accent-primary)" />
                            <span className="brand-text">DataTalk</span>
                        </>
                    )}
                </div>
                {/* Mobile Close Button */}
                <button className="icon-btn mobile-close-btn" onClick={onClose}>
                    <X size={20} />
                </button>
            </div>

            {/* Only show action buttons if user has write access */}
            {canWrite && onUpload && (
                <label className="upload-label">
                    <Upload size={16} />
                    <span>Import CSV</span>
                    <input type="file" hidden accept=".csv" onChange={onUpload} />
                </label>
            )}

            {canWrite && onConnect && (
                <button
                    className="secondary-button"
                    onClick={onConnect}
                    style={{ marginTop: '0.5rem' }}
                >
                    <Link size={16} />
                    <span>Connections</span>
                </button>
            )}

            {canWrite && onBrowse && (
                <button
                    className="secondary-button"
                    onClick={onBrowse}
                    style={{ marginTop: '0.5rem' }}
                >
                    <Database size={16} />
                    <span>Browse Tables</span>
                </button>
            )}

            {onChatHistory && (
                <button
                    className="secondary-button"
                    onClick={onChatHistory}
                    style={{ marginTop: '0.5rem' }}
                >
                    <History size={16} />
                    <span>Chat History</span>
                </button>
            )}

            <div className="section-label">Datasets</div>
            <div className="table-list">
                {tables.length === 0 && (
                    <div style={{ padding: '0 0.5rem', color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
                        No data loaded yet.
                    </div>
                )}

                {groupedTables.map(([groupKey, group]) => (
                    <div key={groupKey} className="table-group">
                        {/* Connection Level */}
                        <div
                            className="table-group-header"
                            onClick={() => toggleGroup(groupKey)}
                        >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', width: '100%' }}>
                                {expandedGroups[groupKey] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}

                                <div
                                    className="table-checkbox"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        // Collect all tables in this group (including all schemas for external)
                                        let allTables = [];
                                        if (groupKey === 'csv') {
                                            allTables = group.tables;
                                        } else {
                                            group.schemas.forEach(schema => {
                                                allTables.push(...schema.tables);
                                            });
                                        }
                                        onToggleGroup(allTables);
                                    }}
                                    title="Select All"
                                >
                                    {/* Determine selection state */}
                                    {(() => {
                                        let allTables = [];
                                        if (groupKey === 'csv') {
                                            allTables = group.tables;
                                        } else {
                                            group.schemas.forEach(schema => {
                                                allTables.push(...schema.tables);
                                            });
                                        }

                                        const allSelected = allTables.length > 0 && allTables.every(table =>
                                            selectedTables.some(t =>
                                                t.table_name === table.table_name &&
                                                (t.source_type || 'csv') === (table.source_type || 'csv') &&
                                                t.connection_id === table.connection_id &&
                                                t.schema_name === table.schema_name
                                            )
                                        );

                                        const someSelected = !allSelected && allTables.some(table =>
                                            selectedTables.some(t =>
                                                t.table_name === table.table_name &&
                                                (t.source_type || 'csv') === (table.source_type || 'csv') &&
                                                t.connection_id === table.connection_id &&
                                                t.schema_name === table.schema_name
                                            )
                                        );

                                        if (allSelected) {
                                            return <CheckSquare size={18} color="var(--accent-primary)" />;
                                        } else if (someSelected) {
                                            return <MinusSquare size={18} color="var(--accent-primary)" />;
                                        } else {
                                            return <Square size={18} color="var(--text-tertiary)" />;
                                        }
                                    })()}
                                </div>

                                {group.isEmoji ? (
                                    <span style={{ fontSize: '1.2rem' }}>{group.icon}</span>
                                ) : (
                                    <img src={group.icon} alt={group.name} style={{ width: '20px', height: '20px' }} />
                                )}
                                <span style={{ fontWeight: 600, fontSize: '0.9rem', flex: 1 }}>{group.name}</span>
                                <span style={{
                                    fontSize: '0.75rem',
                                    color: 'var(--text-tertiary)',
                                    marginLeft: '0.25rem'
                                }}>
                                    {groupKey === 'csv' ? `(${group.tables.length})` : `(${group.schemas.length} schemas)`}
                                </span>
                            </div>
                        </div>

                        {expandedGroups[groupKey] && (
                            <>
                                {/* CSV Files - Direct table list */}
                                {groupKey === 'csv' && group.tables.map(table => (
                                    <div
                                        key={table.id || table.table_name}
                                        className={`nav-item ${selectedTables.some(t => t.table_name === table.table_name && t.source_type === (table.source_type || 'csv')) ? 'active' : ''}`}
                                        onClick={() => onToggleTable(table)}
                                        style={{ marginLeft: '1rem' }}
                                    >
                                        <div className="nav-item-icon">
                                            {selectedTables.some(t => t.table_name === table.table_name && t.source_type === (table.source_type || 'csv')) ? <Check size={16} /> : <Database size={16} />}
                                        </div>
                                        <div className="nav-item-info">
                                            <div className="nav-item-title">{table.table_name}</div>
                                            <div className="nav-item-sub">{table.description || "No description"}</div>
                                        </div>
                                        {canWrite && onEditTable && onDeleteTable && (
                                            <div className="nav-item-actions" style={{ marginLeft: 'auto', display: 'flex', gap: '0.25rem' }}>
                                                <button
                                                    className="icon-btn edit-btn"
                                                    onClick={(e) => onEditTable(e, table)}
                                                    title="Edit Metadata"
                                                >
                                                    <Pencil size={14} />
                                                </button>
                                                <button
                                                    className="icon-btn delete-btn"
                                                    onClick={(e) => onDeleteTable(e, table)}
                                                    title="Delete Table"
                                                >
                                                    <Trash2 size={14} />
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                ))}

                                {/* External Databases - Schema → Tables hierarchy */}
                                {groupKey !== 'csv' && group.schemas.map(schema => (
                                    <div key={schema.key} style={{ marginLeft: '1rem' }}>
                                        {/* Schema Level */}
                                        <div
                                            className="table-group-header"
                                            onClick={() => toggleSchema(schema.key)}
                                            style={{ padding: '0.5rem 0.75rem' }}
                                        >
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                {expandedSchemas[schema.key] ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                                                <span style={{ fontWeight: 500, fontSize: '0.85rem' }}>{schema.name}</span>
                                                <span style={{
                                                    fontSize: '0.7rem',
                                                    color: 'var(--text-tertiary)',
                                                    marginLeft: '0.25rem'
                                                }}>
                                                    ({schema.tables.length})
                                                </span>
                                            </div>
                                        </div>

                                        {/* Tables in Schema */}
                                        {expandedSchemas[schema.key] && schema.tables.map(table => (
                                            <div
                                                key={table.id || table.table_name}
                                                className={`nav-item ${selectedTables.some(t => t.table_name === table.table_name && t.connection_id === table.connection_id && t.schema_name === table.schema_name) ? 'active' : ''}`}
                                                onClick={() => onToggleTable(table)}
                                                style={{ marginLeft: '1rem' }}
                                            >
                                                <div className="nav-item-icon">
                                                    {selectedTables.some(t => t.table_name === table.table_name && t.connection_id === table.connection_id && t.schema_name === table.schema_name) ? <Check size={16} /> : <Database size={16} />}
                                                </div>
                                                <div className="nav-item-info">
                                                    <div className="nav-item-title">{table.table_name}</div>
                                                    <div className="nav-item-sub">{table.description || "No description"}</div>
                                                </div>
                                                {canWrite && onEditTable && onDeleteTable && (
                                                    <div className="nav-item-actions" style={{ marginLeft: 'auto', display: 'flex', gap: '0.25rem' }}>
                                                        <button
                                                            className="icon-btn edit-btn"
                                                            onClick={(e) => onEditTable(e, table)}
                                                            title="Edit Metadata"
                                                        >
                                                            <Pencil size={14} />
                                                        </button>
                                                        <button
                                                            className="icon-btn delete-btn"
                                                            onClick={(e) => onDeleteTable(e, table)}
                                                            title="Delete Table"
                                                        >
                                                            <Trash2 size={14} />
                                                        </button>
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                ))}
                            </>
                        )}
                    </div>
                ))}
            </div>

            <div className="sidebar-footer">
                <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
                    v2.0.0
                </div>
                <button className="icon-btn" onClick={toggleTheme} title="Toggle Theme">
                    {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
                </button>
            </div>
        </aside>
    );
};

export default Sidebar;
