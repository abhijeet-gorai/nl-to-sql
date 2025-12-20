import React, { useState, useEffect } from 'react';
import { Database, Plus, Trash2, Edit, CheckCircle, XCircle, Loader, X } from 'lucide-react';
import ConnectionForm from './ConnectionForm';
import './ConnectionManager.css';

const API_BASE_URL = 'http://localhost:8000';

const ConnectionManager = ({ onClose, onConnectionsChange }) => {
  const [connections, setConnections] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingConnection, setEditingConnection] = useState(null);
  const [testingId, setTestingId] = useState(null);
  const [testResults, setTestResults] = useState({});
  const [deleteConfirm, setDeleteConfirm] = useState({ isOpen: false, connection: null });

  useEffect(() => {
    fetchConnections();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchConnections = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/connections`);
      if (res.ok) {
        const data = await res.json();
        setConnections(data);
        if (onConnectionsChange) {
          onConnectionsChange(data);
        }
      }
    } catch (e) {
      console.error('Failed to fetch connections', e);
    }
  };

  const handleTest = async (connectionId) => {
    setTestingId(connectionId);
    setTestResults(prev => ({ ...prev, [connectionId]: null }));

    try {
      const res = await fetch(`${API_BASE_URL}/connections/${connectionId}/test`, {
        method: 'POST'
      });
      const result = await res.json();

      setTestResults(prev => ({
        ...prev,
        [connectionId]: {
          success: result.success,
          message: result.version || result.message
        }
      }));

      // Clear result after 5 seconds
      setTimeout(() => {
        setTestResults(prev => {
          const newResults = { ...prev };
          delete newResults[connectionId];
          return newResults;
        });
      }, 5000);
    } catch (e) {
      setTestResults(prev => ({
        ...prev,
        [connectionId]: {
          success: false,
          message: e.message
        }
      }));
    } finally {
      setTestingId(null);
    }
  };

  const handleDelete = (connection) => {
    setDeleteConfirm({ isOpen: true, connection });
  };

  const confirmDelete = async () => {
    const connection = deleteConfirm.connection;
    if (!connection) return;

    try {
      const res = await fetch(`${API_BASE_URL}/connections/${connection.id}`, {
        method: 'DELETE'
      });

      if (res.ok) {
        await fetchConnections();
        setDeleteConfirm({ isOpen: false, connection: null });
      } else {
        alert('Failed to delete connection');
      }
    } catch (e) {
      alert(`Error: ${e.message}`);
    }
  };

  const handleEdit = (connection) => {
    setEditingConnection(connection);
    setShowForm(true);
  };

  const handleFormClose = () => {
    setShowForm(false);
    setEditingConnection(null);
  };

  const handleFormSave = () => {
    setShowForm(false);
    setEditingConnection(null);
    fetchConnections();
  };

  const getDbTypeIcon = (dbType) => {
    const icons = {
      postgresql: '/postgresql.svg',
      db2: '/ibm-db2.svg',
      mysql: '/mysql.svg',
      oracle: '/oracle.svg'
    };
    return icons[dbType.toLowerCase()] || '/data-analytics.svg';
  };

  const getDbTypeColor = (dbType) => {
    const colors = {
      postgresql: '#336791',
      db2: '#054ADA',
      mysql: '#00758F',
      oracle: '#F80000'
    };
    return colors[dbType.toLowerCase()] || '#666';
  };

  return (
    <div className="connection-manager-overlay" onClick={onClose}>
      <div className="connection-manager-modal" onClick={e => e.stopPropagation()}>
        <div className="manager-header">
          <div>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.5rem' }}>
              Database Connections
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
              Manage connections to external databases
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <button
              className="btn btn-primary"
              onClick={() => setShowForm(true)}
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
            >
              <Plus size={18} />
              Add Connection
            </button>
            <button className="icon-btn" onClick={onClose} title="Close">
              <X size={20} />
            </button>
          </div>
        </div>

        <div className="connections-list">
          {connections.length === 0 && (
            <div style={{
              textAlign: 'center',
              padding: '3rem',
              color: 'var(--text-tertiary)'
            }}>
              <Database size={48} style={{ opacity: 0.3, marginBottom: '1rem' }} />
              <p>No database connections yet.</p>
              <p style={{ fontSize: '0.85rem' }}>Click "Add Connection" to get started.</p>
            </div>
          )}

          {connections.map(conn => (
            <div key={conn.id} className="connection-card">
              <div className="connection-icon" style={{
                background: `${getDbTypeColor(conn.db_type)}15`,
                padding: '0.75rem',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <img
                  src={getDbTypeIcon(conn.db_type)}
                  alt={conn.db_type}
                  style={{ width: '32px', height: '32px', objectFit: 'contain' }}
                />
              </div>

              <div className="connection-info">
                <div className="connection-name">{conn.connection_name}</div>
                <div className="connection-details">
                  <span style={{
                    textTransform: 'uppercase',
                    fontWeight: 600,
                    color: getDbTypeColor(conn.db_type)
                  }}>
                    {conn.db_type}
                  </span>
                  {' • '}
                  {conn.host}:{conn.port}
                  {' • '}
                  {conn.database_name}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: '0.25rem' }}>
                  User: {conn.username}
                  {conn.ssl_enabled && ' • SSL Enabled'}
                </div>

                {/* Test Result Status */}
                {testResults[conn.id] && (
                  <div style={{
                    marginTop: '0.5rem',
                    padding: '0.5rem',
                    borderRadius: '6px',
                    fontSize: '0.8rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    background: testResults[conn.id].success
                      ? 'rgba(34, 197, 94, 0.1)'
                      : 'rgba(239, 68, 68, 0.1)',
                    color: testResults[conn.id].success ? '#22c55e' : '#ef4444'
                  }}>
                    {testResults[conn.id].success ? (
                      <CheckCircle size={14} />
                    ) : (
                      <XCircle size={14} />
                    )}
                    <span>{testResults[conn.id].message}</span>
                  </div>
                )}
              </div>

              <div className="connection-actions">
                <button
                  className="btn btn-sm"
                  onClick={() => handleTest(conn.id)}
                  disabled={testingId === conn.id}
                  title="Test Connection"
                  style={{ minWidth: '70px' }}
                >
                  {testingId === conn.id ? (
                    <>
                      <Loader size={14} className="spinning" />
                      Testing
                    </>
                  ) : (
                    'Test'
                  )}
                </button>
                <button
                  className="icon-btn edit-btn"
                  onClick={() => handleEdit(conn)}
                  title="Edit Connection"
                >
                  <Edit size={14} />
                </button>
                <button
                  className="icon-btn delete-btn"
                  onClick={() => handleDelete(conn)}
                  title="Delete Connection"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="manager-footer">
          <button className="btn btn-ghost" onClick={onClose}>
            Close
          </button>
        </div>

        {showForm && (
          <ConnectionForm
            connection={editingConnection}
            onClose={handleFormClose}
            onSave={handleFormSave}
          />
        )}

        {deleteConfirm.isOpen && (
          <div className="modal-overlay" onClick={() => setDeleteConfirm({ isOpen: false, connection: null })}>
            <div className="modal-content" onClick={e => e.stopPropagation()}>
              <div className="modal-header">
                <div className="modal-title">Delete Connection</div>
                <div className="modal-desc">
                  Are you sure you want to delete "{deleteConfirm.connection?.connection_name}"?
                  This will also remove all synced tables from this connection.
                </div>
              </div>
              <div className="modal-actions">
                <button
                  className="btn btn-ghost"
                  onClick={() => setDeleteConfirm({ isOpen: false, connection: null })}
                >
                  Cancel
                </button>
                <button className="btn btn-danger" onClick={confirmDelete}>
                  Delete
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ConnectionManager;
