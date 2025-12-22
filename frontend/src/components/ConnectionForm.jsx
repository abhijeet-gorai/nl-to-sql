import React, { useState, useEffect } from 'react';
import { X, Loader, AlertCircle } from 'lucide-react';
import * as connectionsApi from '../api/connections';

const ConnectionForm = ({ projectId, connection, onClose, onSave }) => {
  const isEditing = !!connection;

  const [formData, setFormData] = useState({
    connection_name: '',
    db_type: 'postgresql',
    host: '',
    port: 5432,
    database_name: '',
    username: '',
    password: '',
    ssl_enabled: false
  });

  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (connection) {
      setFormData({
        connection_name: connection.connection_name || '',
        db_type: connection.db_type || 'postgresql',
        host: connection.host || '',
        port: connection.port || 5432,
        database_name: connection.database_name || '',
        username: connection.username || '',
        password: '', // Don't pre-fill password for security
        ssl_enabled: connection.ssl_enabled || false
      });
    }
  }, [connection]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
    setTestResult(null);
    setError('');
  };

  const handleDbTypeChange = (e) => {
    const dbType = e.target.value;
    const defaultPorts = {
      postgresql: 5432,
      db2: 50000,
      mysql: 3306,
      oracle: 1521
    };

    setFormData(prev => ({
      ...prev,
      db_type: dbType,
      port: defaultPorts[dbType] || 5432
    }));
    setTestResult(null);
  };

  const handleTest = async () => {
    if (!projectId) return;

    // For editing, if password is empty, we need to use the existing connection
    if (isEditing && !formData.password) {
      setTesting(true);
      setTestResult(null);
      setError('');

      try {
        const result = await connectionsApi.testConnection(projectId, connection.id);

        if (result.success) {
          setTestResult({ success: true, message: result.version || result.message });
        } else {
          setTestResult({ success: false, message: result.message });
        }
      } catch (e) {
        setTestResult({ success: false, message: e.response?.data?.detail || e.message });
      } finally {
        setTesting(false);
      }
      return;
    }

    setTesting(true);
    setTestResult(null);
    setError('');

    try {
      const result = await connectionsApi.testConnectionData(projectId, formData);

      if (result.success) {
        setTestResult({ success: true, message: result.version || result.message });
      } else {
        setTestResult({ success: false, message: result.message });
      }
    } catch (e) {
      setTestResult({ success: false, message: e.response?.data?.detail || e.message });
    } finally {
      setTesting(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!projectId) return;

    setError('');
    setSaving(true);

    try {
      // For editing, only send changed fields
      const payload = isEditing && !formData.password
        ? { ...formData, password: undefined }
        : formData;

      if (isEditing) {
        await connectionsApi.updateConnection(projectId, connection.id, payload);
      } else {
        await connectionsApi.createConnection(projectId, payload);
      }

      onSave();
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to save connection');
    } finally {
      setSaving(false);
    }
  };

  const dbTypeOptions = [
    { value: 'postgresql', label: 'PostgreSQL', icon: '/postgresql.svg', enabled: true },
    { value: 'db2', label: 'IBM Db2', icon: '/ibm-db2.svg', enabled: true },
    { value: 'mysql', label: 'MySQL', icon: '/mysql.svg', enabled: false },
    { value: 'oracle', label: 'Oracle', icon: '/oracle.svg', enabled: false }
  ];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content connection-form-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header" style={{ position: 'relative' }}>
          <div className="modal-title">
            {isEditing ? 'Edit Connection' : 'New Database Connection'}
          </div>
          <button
            className="icon-btn"
            onClick={onClose}
            style={{ position: 'absolute', right: '1rem', top: '1rem' }}
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-body" style={{ padding: '1.5rem 1.5rem 0 1.5rem' }}>
            {error && (
              <div className="alert alert-error">
                <AlertCircle size={16} />
                {error}
              </div>
            )}

            <div className="field-group" style={{ marginBottom: '1rem' }}>
              <label className="field-label">Connection Name *</label>
              <input
                type="text"
                name="connection_name"
                className="input-text"
                value={formData.connection_name}
                onChange={handleChange}
                placeholder="e.g., Production PostgreSQL"
                required
                disabled={isEditing}
              />
            </div>

            <div className="field-group">
              <label className="field-label">Database Type *</label>
              <div className="db-type-selector">
                {dbTypeOptions.map(option => (
                  <label
                    key={option.value}
                    className={`db-type-option ${formData.db_type === option.value ? 'selected' : ''} ${!option.enabled ? 'disabled' : ''}`}
                  >
                    <input
                      type="radio"
                      name="db_type"
                      value={option.value}
                      checked={formData.db_type === option.value}
                      onChange={handleDbTypeChange}
                      disabled={!option.enabled}
                    />
                    <img src={option.icon} alt={option.label} className="db-type-icon" />
                    <span className="db-type-label">{option.label}</span>
                    {!option.enabled && <span className="coming-soon">Coming Soon</span>}
                  </label>
                ))}
              </div>
            </div>

            <div className="editor-row" style={{ marginBottom: '1rem' }}>
              <div className="field-group">
                <label className="field-label">Host *</label>
                <input
                  type="text"
                  name="host"
                  className="input-text"
                  value={formData.host}
                  onChange={handleChange}
                  placeholder="localhost"
                  required
                />
              </div>
              <div className="field-group">
                <label className="field-label">Port *</label>
                <input
                  type="number"
                  name="port"
                  className="input-text"
                  value={formData.port}
                  onChange={handleChange}
                  required
                />
              </div>
            </div>

            <div className="field-group" style={{ marginBottom: '1rem' }}>
              <label className="field-label">Database Name *</label>
              <input
                type="text"
                name="database_name"
                className="input-text"
                value={formData.database_name}
                onChange={handleChange}
                placeholder="mydb"
                required
              />
            </div>

            <div className="field-group" style={{ marginBottom: '1rem' }}>
              <label className="field-label">Username *</label>
              <input
                type="text"
                name="username"
                className="input-text"
                value={formData.username}
                onChange={handleChange}
                placeholder="postgres"
                required
              />
            </div>

            <div className="field-group" style={{ marginBottom: '1rem' }}>
              <label className="field-label">
                Password {isEditing && <span style={{ color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>(leave blank to keep current)</span>}
              </label>
              <input
                type="password"
                name="password"
                className="input-text"
                value={formData.password}
                onChange={handleChange}
                placeholder={isEditing ? '••••••••' : 'Enter password'}
                required={!isEditing}
              />
            </div>

            <div className="field-group" style={{ marginBottom: '1.5rem' }}>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  name="ssl_enabled"
                  checked={formData.ssl_enabled}
                  onChange={handleChange}
                />
                <span>Enable SSL/TLS</span>
              </label>
            </div>

            {testResult && (
              <div className={`alert ${testResult.success ? 'alert-success' : 'alert-error'}`}>
                {testResult.success ? '✅' : '❌'} {testResult.message}
              </div>
            )}
          </div>

          <div className="modal-actions">
            <button
              type="button"
              className="btn btn-ghost"
              onClick={handleTest}
              disabled={testing || saving}
            >
              {testing ? (
                <>
                  <Loader size={16} className="spinning" />
                  Testing...
                </>
              ) : (
                'Test Connection'
              )}
            </button>
            <div style={{ flex: 1 }} />
            <button
              type="button"
              className="btn btn-ghost"
              onClick={onClose}
              disabled={saving}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={saving || testing}
            >
              {saving ? (
                <>
                  <Loader size={16} className="spinning" />
                  Saving...
                </>
              ) : (
                isEditing ? 'Update' : 'Create'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ConnectionForm;
