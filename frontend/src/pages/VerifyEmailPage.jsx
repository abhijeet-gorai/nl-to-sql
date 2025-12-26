import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Database, CheckCircle, XCircle, Loader, Sun, Moon, Mail } from 'lucide-react';
import { verifyEmail, resendVerification } from '../api/auth';
import './VerifyEmailPage.css';

const VerifyEmailPage = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const token = searchParams.get('token');

    const [status, setStatus] = useState('loading'); // loading, success, error, no-token
    const [message, setMessage] = useState('');
    const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');
    const [resendEmail, setResendEmail] = useState('');
    const [resendLoading, setResendLoading] = useState(false);
    const [resendMessage, setResendMessage] = useState('');

    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
    }, [theme]);

    useEffect(() => {
        if (!token) {
            setStatus('no-token');
            setMessage('No verification token provided.');
            return;
        }

        const verifyToken = async () => {
            try {
                const result = await verifyEmail(token);
                setStatus('success');
                setMessage(result.message || 'Email verified successfully!');
            } catch (err) {
                setStatus('error');
                const errorDetail = err.response?.data?.detail;
                setMessage(typeof errorDetail === 'string' ? errorDetail : 'Failed to verify email. The link may be invalid or expired.');
            }
        };

        verifyToken();
    }, [token]);

    const toggleTheme = () => {
        setTheme(prev => prev === 'dark' ? 'light' : 'dark');
    };

    const handleResend = async (e) => {
        e.preventDefault();
        if (!resendEmail) return;

        setResendLoading(true);
        setResendMessage('');

        try {
            const result = await resendVerification(resendEmail);
            setResendMessage(result.message || 'Verification email sent!');
        } catch (err) {
            const errorDetail = err.response?.data?.detail;
            setResendMessage(typeof errorDetail === 'string' ? errorDetail : 'Failed to resend verification email.');
        } finally {
            setResendLoading(false);
        }
    };

    const renderContent = () => {
        switch (status) {
            case 'loading':
                return (
                    <div className="verify-status loading">
                        <div className="verify-icon">
                            <Loader className="spin" size={48} />
                        </div>
                        <h2>Verifying your email...</h2>
                        <p>Please wait while we verify your email address.</p>
                    </div>
                );

            case 'success':
                return (
                    <div className="verify-status success">
                        <div className="verify-icon success-icon">
                            <CheckCircle size={48} />
                        </div>
                        <h2>Email Verified!</h2>
                        <p>{message}</p>
                        <button
                            className="verify-button"
                            onClick={() => navigate('/login')}
                        >
                            Continue to Login
                        </button>
                    </div>
                );

            case 'error':
            case 'no-token':
                return (
                    <div className="verify-status error">
                        <div className="verify-icon error-icon">
                            <XCircle size={48} />
                        </div>
                        <h2>Verification Failed</h2>
                        <p>{message}</p>

                        <div className="resend-section">
                            <h3>Need a new verification link?</h3>
                            <form onSubmit={handleResend} className="resend-form">
                                <div className="resend-input-wrapper">
                                    <Mail size={18} className="input-icon" />
                                    <input
                                        type="email"
                                        value={resendEmail}
                                        onChange={(e) => setResendEmail(e.target.value)}
                                        placeholder="Enter your email"
                                        required
                                    />
                                </div>
                                <button
                                    type="submit"
                                    className="resend-button"
                                    disabled={resendLoading}
                                >
                                    {resendLoading ? (
                                        <>
                                            <Loader className="spin" size={16} />
                                            <span>Sending...</span>
                                        </>
                                    ) : (
                                        <span>Resend Verification Email</span>
                                    )}
                                </button>
                            </form>
                            {resendMessage && (
                                <p className="resend-message">{resendMessage}</p>
                            )}
                        </div>

                        <Link to="/login" className="back-to-login">
                            Back to Login
                        </Link>
                    </div>
                );

            default:
                return null;
        }
    };

    return (
        <div className="verify-page">
            {/* Theme Toggle */}
            <button
                className="theme-toggle-btn"
                onClick={toggleTheme}
                title="Toggle Theme"
            >
                {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
            </button>

            <div className="verify-container">
                <div className="verify-header">
                    <div className="verify-logo">
                        <Database size={40} />
                    </div>
                    <h1 className="verify-title">DataTalk</h1>
                </div>

                {renderContent()}
            </div>
        </div>
    );
};

export default VerifyEmailPage;
