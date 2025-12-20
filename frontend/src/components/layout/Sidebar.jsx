import React, { useState, useMemo } from 'react';
import {
    Database, Upload, Link, Sun, Moon,
    ChevronRight, ChevronDown, Check, Pencil, Trash2
} from 'lucide-react';
import './Sidebar.css';

const Sidebar = ({
    tables,
    selectedTables,
    onUpload,
    onConnect,
    onBrowse,
    onToggleTable,
    onEditTable,
    onDeleteTable,
    toggleTheme,
    theme
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

    // Group tables by source with schema hierarchy for external databases
    const groupedTables = useMemo(() => {
        const groups = {
            csv: { name: 'Local CSV Files', icon: '📄', isEmoji: true, tables: [] },
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
        <aside className="sidebar">
            <div className="brand">
                <Database size={24} color="var(--accent-primary)" />
                <span className="brand-text">DataTalk</span>
            </div>

            <label className="upload-label">
                <Upload size={16} />
                <span>Import CSV</span>
                <input type="file" hidden accept=".csv" onChange={onUpload} />
            </label>

            <button
                className="secondary-button"
                onClick={onConnect}
                style={{ marginTop: '0.5rem' }}
            >
                <Link size={16} />
                <span>Connections</span>
            </button>

            <button
                className="secondary-button"
                onClick={onBrowse}
                style={{ marginTop: '0.5rem' }}
            >
                <Database size={16} />
                <span>Browse Tables</span>
            </button>

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
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                {expandedGroups[groupKey] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                                {group.isEmoji ? (
                                    <span style={{ fontSize: '1.2rem' }}>{group.icon}</span>
                                ) : (
                                    <img src={group.icon} alt={group.name} style={{ width: '20px', height: '20px' }} />
                                )}
                                <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{group.name}</span>
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
                    v1.0.0
                </div>
                <button className="icon-btn" onClick={toggleTheme} title="Toggle Theme">
                    {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
                </button>
            </div>
        </aside>
    );
};

export default Sidebar;
