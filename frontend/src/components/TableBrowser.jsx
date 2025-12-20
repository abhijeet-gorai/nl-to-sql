import React, { useState, useEffect, useRef } from 'react';
import { X, Search, Loader, Database, Eye, CheckSquare, Square, Check } from 'lucide-react';
import CustomSelect from './CustomSelect';
import './TableBrowser.css';

const API_BASE_URL = 'http://localhost:8000';

const TableBrowser = ({ onClose, onTablesSynced }) => {
  const [connections, setConnections] = useState([]);
  const [selectedConnection, setSelectedConnection] = useState(null);
  const [schemas, setSchemas] = useState([]);
  const [selectedSchema, setSelectedSchema] = useState('');
  const [tables, setTables] = useState([]);
  const [syncedTables, setSyncedTables] = useState(new Set());
  const [selectedTables, setSelectedTables] = useState(new Set());
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [previewTable, setPreviewTable] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const initialLoadRef = useRef(false);

  useEffect(() => {
    // Prevent double-invocation in development
    if (initialLoadRef.current) return;
    initialLoadRef.current = true;

    fetchConnections();
  }, []);

  const fetchConnections = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/connections`);
      if (res.ok) {
        const data = await res.json();
        setConnections(data);
      }
    } catch (e) {
      console.error('Failed to fetch connections', e);
    }
  };

  const fetchSyncedTables = async (connectionId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/external-tables?connection_id=${connectionId}`);
      if (res.ok) {
        const data = await res.json();
        const syncedNames = new Set(data.map(t => t.table_name));
        setSyncedTables(syncedNames);
      }
    } catch (e) {
      console.error('Failed to fetch synced tables', e);
    }
  };

  const handleConnectionSelect = async (connectionId) => {
    const connection = connections.find(c => c.id === connectionId);
    if (!connection) return;

    setSelectedConnection(connection);
    setSelectedSchema('');
    setTables([]);
    setSelectedTables(new Set());
    setSyncedTables(new Set());
    setLoading(true);
    setLoadingMessage('Loading schemas...');

    try {
      const [schemasRes] = await Promise.all([
        fetch(`${API_BASE_URL}/connections/${connection.id}/schemas`),
        fetchSyncedTables(connection.id)
      ]);

      if (schemasRes.ok) {
        const data = await schemasRes.json();
        setSchemas(data.schemas || []);
      }
    } catch (e) {
      console.error('Failed to fetch schemas', e);
    } finally {
      setLoading(false);
      setLoadingMessage('');
    }
  };

  const handleSchemaSelect = async (schema) => {
    if (!selectedConnection) return;

    setSelectedSchema(schema);
    setTables([]);
    setSelectedTables(new Set());
    setLoading(true);
    setLoadingMessage('Loading tables...');

    try {
      const res = await fetch(`${API_BASE_URL}/connections/${selectedConnection.id}/tables?schema=${schema}`);
      if (res.ok) {
        const data = await res.json();
        setTables(data.tables || []);
      }
    } catch (e) {
      console.error('Failed to fetch tables', e);
    } finally {
      setLoading(false);
      setLoadingMessage('');
    }
  };

  const handleTableToggle = (tableName) => {
    setSelectedTables(prev => {
      const newSet = new Set(prev);
      if (newSet.has(tableName)) {
        newSet.delete(tableName);
      } else {
        newSet.add(tableName);
      }
      return newSet;
    });
  };

  const handleSelectAll = () => {
    if (selectedTables.size === filteredTables.length) {
      setSelectedTables(new Set());
    } else {
      setSelectedTables(new Set(filteredTables.map(t => t.table_name)));
    }
  };

  const handlePreview = async (table) => {
    setPreviewTable(table);
    setPreviewData(null);

    try {
      const res = await fetch(
        `${API_BASE_URL}/connections/${selectedConnection.id}/tables/${table.table_name}/preview?schema=${selectedSchema}&limit=10`
      );
      if (res.ok) {
        const data = await res.json();
        setPreviewData(data);
      }
    } catch (e) {
      console.error('Failed to preview table', e);
    }
  };

  const handleSync = async () => {
    if (selectedTables.size === 0) {
      return;
    }

    setSyncing(true);

    try {
      const tablesToSync = Array.from(selectedTables).map(tableName => ({
        schema: selectedSchema,
        table_name: tableName,
        display_name: tableName
      }));

      const res = await fetch(`${API_BASE_URL}/connections/${selectedConnection.id}/tables/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tables: tablesToSync })
      });

      if (res.ok) {
        const result = await res.json();
        // Close browser and pass synced tables to parent for metadata editing
        if (onTablesSynced) {
          onTablesSynced(result.tables);
        }
        onClose();
      } else {
        const error = await res.json();
        console.error('Failed to sync tables:', error.detail);
      }
    } catch (e) {
      console.error('Error syncing tables:', e.message);
    } finally {
      setSyncing(false);
    }
  };

  const filteredTables = tables.filter(table =>
    table.table_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (connections.length === 0) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-content" onClick={e => e.stopPropagation()}>
          <div className="modal-header">
            <div className="modal-title">Browse Tables</div>
            <button className="icon-btn" onClick={onClose}>
              <X size={20} />
            </button>
          </div>
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)' }}>
            <Database size={48} style={{ opacity: 0.3, marginBottom: '1rem' }} />
            <p>No database connections available.</p>
            <p style={{ fontSize: '0.85rem' }}>Please create a connection first.</p>
          </div>
          <div className="modal-actions">
            <button className="btn btn-ghost" onClick={onClose}>Close</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content table-browser-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header" style={{ position: 'relative' }}>
          <div className="modal-title">Browse External Tables</div>
          <button
            className="icon-btn"
            onClick={onClose}
            style={{ position: 'absolute', right: '1rem', top: '1rem' }}
          >
            <X size={20} />
          </button>
        </div>

        <div className="browser-controls">
          <div className="field-group">
            <CustomSelect
              label="Connection"
              options={connections.map(conn => ({
                value: conn.id,
                label: `${conn.connection_name} (${conn.db_type})`
              }))}
              value={selectedConnection?.id}
              onChange={handleConnectionSelect}
              placeholder="Select a connection..."
            />
          </div>

          <div className="field-group">
            <CustomSelect
              label="Schema"
              options={schemas.map(schema => ({
                value: schema,
                label: schema
              }))}
              value={selectedSchema}
              onChange={handleSchemaSelect}
              placeholder={loading && loadingMessage === 'Loading schemas...' ? 'Loading...' : 'Select a schema...'}
              disabled={!selectedConnection || schemas.length === 0}
            />
          </div>

          <div className="field-group" style={{ flex: 1 }}>
            <label className="field-label">Search Tables</label>
            <div style={{ position: 'relative' }}>
              <Search size={16} style={{
                position: 'absolute',
                left: '0.75rem',
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--text-tertiary)'
              }} />
              <input
                type="text"
                className="input-text"
                placeholder="Filter tables..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{ paddingLeft: '2.5rem' }}
              />
            </div>
          </div>
        </div>

        <div className="browser-header">
          <label className="table-checkbox">
            <input
              type="checkbox"
              checked={selectedTables.size === filteredTables.length && filteredTables.length > 0}
              onChange={handleSelectAll}
              disabled={filteredTables.length === 0}
            />
            {selectedTables.size === filteredTables.length && filteredTables.length > 0 ? (
              <CheckSquare size={18} color="var(--accent-primary)" />
            ) : (
              <Square size={18} color="var(--text-tertiary)" />
            )}
            <span style={{ marginLeft: '8px' }}>
              {selectedTables.size > 0
                ? `${selectedTables.size} selected`
                : `Select All (${filteredTables.length})`
              }
            </span>
          </label>
        </div>

        <div className="tables-list">
          {loading ? (
            <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-tertiary)' }}>
              <Loader size={32} className="spinning" />
              <p style={{ marginTop: '1rem' }}>{loadingMessage || 'Loading...'}</p>
            </div>
          ) : filteredTables.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-tertiary)' }}>
              <Database size={32} style={{ opacity: 0.3 }} />
              <p style={{ marginTop: '1rem' }}>
                {searchTerm ? 'No tables match your search' : 'No tables found in this schema'}
              </p>
            </div>
          ) : (
            filteredTables.map(table => (
              <div
                key={table.table_name}
                className={`table-item ${selectedTables.has(table.table_name) ? 'selected' : ''}`}
              >
                <label className="table-checkbox">
                  <input
                    type="checkbox"
                    checked={selectedTables.has(table.table_name)}
                    onChange={() => handleTableToggle(table.table_name)}
                  />
                  {selectedTables.has(table.table_name) ? (
                    <CheckSquare size={18} color="var(--accent-primary)" />
                  ) : (
                    <Square size={18} color="var(--text-tertiary)" />
                  )}
                </label>
                <div className="table-info" onClick={() => handleTableToggle(table.table_name)}>
                  <div className="table-name">
                    {table.table_name}
                    {syncedTables.has(table.table_name) && (
                      <span style={{
                        marginLeft: '0.5rem',
                        padding: '0.125rem 0.5rem',
                        background: 'rgba(34, 197, 94, 0.1)',
                        color: '#22c55e',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.25rem'
                      }}>
                        <Check size={12} />
                        Synced
                      </span>
                    )}
                  </div>
                  <div className="table-meta">
                    {table.column_count} columns
                  </div>
                </div>
                <button
                  className="btn btn-sm"
                  onClick={() => handlePreview(table)}
                  title="Preview Data"
                >
                  <Eye size={14} />
                  Preview
                </button>
              </div>
            ))
          )}
        </div>

        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={onClose} disabled={syncing}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={handleSync}
            disabled={selectedTables.size === 0 || syncing}
          >
            {syncing ? (
              <>
                <Loader size={16} className="spinning" />
                Syncing {selectedTables.size} table(s)...
              </>
            ) : (
              `Sync ${selectedTables.size} Table(s)`
            )}
          </button>
        </div>

        {previewTable && (
          <div className="modal-overlay" onClick={() => setPreviewTable(null)}>
            <div className="modal-content preview-modal" onClick={e => e.stopPropagation()}>
              <div className="modal-header" style={{ position: 'relative' }}>
                <div className="modal-title">Preview: {previewTable.table_name}</div>
                <button
                  className="icon-btn"
                  onClick={() => setPreviewTable(null)}
                  style={{ position: 'absolute', right: '1rem', top: '1rem' }}
                >
                  <X size={20} />
                </button>
              </div>
              <div className="preview-content">
                {!previewData ? (
                  <div style={{ textAlign: 'center', padding: '2rem' }}>
                    <Loader size={32} className="spinning" />
                    <p style={{ marginTop: '1rem', color: 'var(--text-tertiary)' }}>Loading preview...</p>
                  </div>
                ) : (
                  <div className="preview-table-wrapper">
                    <table className="preview-table">
                      <thead>
                        <tr>
                          {previewData.columns.map(col => (
                            <th key={col}>{col}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {previewData.data.map((row, idx) => (
                          <tr key={idx}>
                            {previewData.columns.map(col => (
                              <td key={col}>{String(row[col] || '')}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <div style={{ padding: '1rem', fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
                      Showing {previewData.row_count} of first 10 rows
                    </div>
                  </div>
                )}
              </div>
              <div className="modal-actions">
                <button className="btn btn-ghost" onClick={() => setPreviewTable(null)}>
                  Close
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
};

export default TableBrowser;
