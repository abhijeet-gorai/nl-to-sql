import React, { useState, useEffect } from 'react';
import { X, Key, Check, AlertCircle, Loader, Trash2 } from 'lucide-react';
import apiClient from '../../api/client';
import './CredentialsModal.css';

const CredentialsModal = ({ onClose }) => {
    const [credentials, setCredentials] = useState({
        groq_api_key: ''
    });
    const [existingCredentials, setExistingCredentials] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [validating, setValidating] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [isValidated, setIsValidated] = useState(false);

    useEffect(() => {
        fetchExistingCredentials();
    }, []);

    const fetchExistingCredentials = async () => {
        try {
            const response = await apiClient.get('/users/credentials');
            if (response.data.has_credentials) {
                setExistingCredentials(response.data);
            }
        } catch (err) {
            console.error('Failed to fetch credentials:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleChange = (e) => {
        const { name, value } = e.target;
        setCredentials(prev => ({ ...prev, [name]: value }));
        setIsValidated(false);
        setError('');
        setSuccess('');
    };

    const handleValidate = async () => {
        if (!credentials.groq_api_key) {
            setError('API key is required');
            return;
        }

        setValidating(true);
        setError('');
        setSuccess('');

        try {
            await apiClient.post('/users/credentials/validate', credentials);
            setIsValidated(true);
            setSuccess('Credentials validated successfully!');
        } catch (err) {
            setError(err.response?.data?.detail || 'Validation failed');
            setIsValidated(false);
        } finally {
            setValidating(false);
        }
    };

    const handleSave = async () => {
        if (!isValidated) {
            setError('Please validate credentials first');
            return;
        }

        setSaving(true);
        setError('');

        try {
            await apiClient.post('/users/credentials', credentials);
            setSuccess('Credentials saved successfully!');
            setTimeout(() => onClose(), 1500);
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to save credentials');
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!window.confirm('Are you sure you want to delete your Groq credentials?')) {
            return;
        }

        setDeleting(true);
        setError('');

        try {
            await apiClient.delete('/users/credentials');
            setExistingCredentials(null);
            setCredentials({
                groq_api_key: ''
            });
            setSuccess('Credentials deleted successfully!');
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to delete credentials');
        } finally {
            setDeleting(false);
        }
    };

    if (loading) {
        return (
            <div className="modal-overlay">
                <div className="credentials-modal">
                    <div className="modal-loading">
                        <Loader className="spin" size={24} />
                        <span>Loading...</span>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
            <div className="credentials-modal">
                <div className="modal-header">
                    <div className="modal-title">
                        <Key size={20} />
                        <span>Groq API Credentials</span>
                    </div>
                    <button className="close-btn" onClick={onClose}>
                        <X size={20} />
                    </button>
                </div>

                <div className="modal-body">
                    {existingCredentials && (
                        <div className="existing-credentials">
                            <p className="info-text">
                                You have saved credentials. Enter a new API key to update them.
                            </p>
                            <div className="masked-key">
                                Current API Key: <code>{existingCredentials.groq_api_key_masked}</code>
                            </div>
                        </div>
                    )}

                    <div className="form-group">
                        <label htmlFor="groq_api_key">Groq API Key *</label>
                        <input
                            type="password"
                            id="groq_api_key"
                            name="groq_api_key"
                            value={credentials.groq_api_key}
                            onChange={handleChange}
                            placeholder={existingCredentials ? "Enter new API key to update" : "gsk_..."}
                        />
                        <small className="help-text">
                            Get your API key from <a href="https://console.groq.com/keys" target="_blank" rel="noopener noreferrer">console.groq.com/keys</a>
                        </small>
                    </div>

                    {error && (
                        <div className="message error">
                            <AlertCircle size={16} />
                            <span>{error}</span>
                        </div>
                    )}

                    {success && (
                        <div className="message success">
                            <Check size={16} />
                            <span>{success}</span>
                        </div>
                    )}
                </div>

                <div className="modal-footer">
                    {existingCredentials && (
                        <button
                            className="btn btn-danger"
                            onClick={handleDelete}
                            disabled={deleting}
                        >
                            {deleting ? <Loader className="spin" size={16} /> : <Trash2 size={16} />}
                            <span>Delete</span>
                        </button>
                    )}

                    <div className="footer-right">
                        <button
                            className="btn btn-secondary"
                            onClick={handleValidate}
                            disabled={validating || !credentials.groq_api_key}
                        >
                            {validating ? <Loader className="spin" size={16} /> : <Check size={16} />}
                            <span>{validating ? 'Validating...' : 'Test Connection'}</span>
                        </button>

                        <button
                            className="btn btn-primary"
                            onClick={handleSave}
                            disabled={!isValidated || saving}
                        >
                            {saving ? <Loader className="spin" size={16} /> : <Key size={16} />}
                            <span>{saving ? 'Saving...' : 'Save Credentials'}</span>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default CredentialsModal;
