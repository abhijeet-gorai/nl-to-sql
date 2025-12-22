import React, { useState } from 'react';
import { X, Loader, Key, Eye, EyeOff } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import './ChangePasswordModal.css';

const ChangePasswordModal = ({ onClose }) => {
    const { changePassword } = useAuth();

    const [currentPassword, setCurrentPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [showCurrent, setShowCurrent] = useState(false);
    const [showNew, setShowNew] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');

        if (newPassword !== confirmPassword) {
            setError('New passwords do not match');
            return;
        }

        if (newPassword.length < 8) {
            setError('New password must be at least 8 characters');
            return;
        }

        setLoading(true);
        try {
            await changePassword(currentPassword, newPassword);
            setSuccess(true);
            setTimeout(() => {
                onClose();
            }, 1500);
        } catch (err) {
            const message = err.response?.data?.detail || 'Failed to change password';
            setError(typeof message === 'string' ? message : JSON.stringify(message));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="change-password-modal" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <div className="modal-title">
                        <Key size={20} />
                        <span>Change Password</span>
                    </div>
                    <button className="icon-btn" onClick={onClose}>
                        <X size={20} />
                    </button>
                </div>

                {success ? (
                    <div className="success-message">
                        <div className="success-icon">✓</div>
                        <p>Password changed successfully!</p>
                    </div>
                ) : (
                    <form onSubmit={handleSubmit}>
                        <div className="modal-body">
                            {error && <div className="error-message">{error}</div>}

                            <div className="form-group">
                                <label>Current Password</label>
                                <div className="password-input">
                                    <input
                                        type={showCurrent ? 'text' : 'password'}
                                        value={currentPassword}
                                        onChange={(e) => setCurrentPassword(e.target.value)}
                                        placeholder="Enter current password"
                                        required
                                    />
                                    <button
                                        type="button"
                                        className="toggle-btn"
                                        onClick={() => setShowCurrent(!showCurrent)}
                                    >
                                        {showCurrent ? <EyeOff size={16} /> : <Eye size={16} />}
                                    </button>
                                </div>
                            </div>

                            <div className="form-group">
                                <label>New Password</label>
                                <div className="password-input">
                                    <input
                                        type={showNew ? 'text' : 'password'}
                                        value={newPassword}
                                        onChange={(e) => setNewPassword(e.target.value)}
                                        placeholder="Enter new password (min 8 characters)"
                                        required
                                        minLength={8}
                                    />
                                    <button
                                        type="button"
                                        className="toggle-btn"
                                        onClick={() => setShowNew(!showNew)}
                                    >
                                        {showNew ? <EyeOff size={16} /> : <Eye size={16} />}
                                    </button>
                                </div>
                            </div>

                            <div className="form-group">
                                <label>Confirm New Password</label>
                                <input
                                    type="password"
                                    value={confirmPassword}
                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                    placeholder="Confirm new password"
                                    required
                                />
                            </div>
                        </div>

                        <div className="modal-actions">
                            <button
                                type="button"
                                className="btn-secondary"
                                onClick={onClose}
                                disabled={loading}
                            >
                                Cancel
                            </button>
                            <button
                                type="submit"
                                className="btn-primary"
                                disabled={loading}
                            >
                                {loading ? (
                                    <>
                                        <Loader size={16} className="spin" />
                                        <span>Changing...</span>
                                    </>
                                ) : (
                                    <span>Change Password</span>
                                )}
                            </button>
                        </div>
                    </form>
                )}
            </div>
        </div>
    );
};

export default ChangePasswordModal;
