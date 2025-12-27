import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Eye, EyeOff, Database, Loader, Sun, Moon, Mail, CheckCircle } from 'lucide-react';
import { resendVerification } from '../api/auth';
import './LoginPage.css';

const LoginPage = () => {
    const navigate = useNavigate();
    const { login, register } = useAuth();

    const [isRegister, setIsRegister] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');

    // Email verification states
    const [registrationSuccess, setRegistrationSuccess] = useState(false);
    const [registrationEmail, setRegistrationEmail] = useState('');
    const [emailNotVerified, setEmailNotVerified] = useState(false);
    const [unverifiedEmail, setUnverifiedEmail] = useState('');
    const [resendLoading, setResendLoading] = useState(false);
    const [resendMessage, setResendMessage] = useState('');

    // Form fields
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');

    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
    }, [theme]);

    // Enable scrolling on login page
    useEffect(() => {
        document.body.classList.add('allow-scroll');
        return () => {
            document.body.classList.remove('allow-scroll');
        };
    }, []);

    const toggleTheme = () => {
        setTheme(prev => prev === 'dark' ? 'light' : 'dark');
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setEmailNotVerified(false);
        setResendMessage('');
        setLoading(true);

        try {
            if (isRegister) {
                // Register (don't auto-login - user needs to verify email first)
                const result = await register({
                    username,
                    full_name: fullName,
                    email,
                    password,
                });
                setRegistrationSuccess(true);
                setRegistrationEmail(email);
                // Clear form
                setUsername('');
                setPassword('');
                setFullName('');
                setEmail('');
            } else {
                await login(username, password);
                navigate('/projects');
            }
        } catch (err) {
            const detail = err.response?.data?.detail;

            // Check if it's an email not verified error
            if (detail && typeof detail === 'object' && detail.code === 'EMAIL_NOT_VERIFIED') {
                setEmailNotVerified(true);
                setUnverifiedEmail(detail.email || '');
                setError('');
            } else {
                const message = typeof detail === 'string' ? detail : (err.message || 'Authentication failed');
                setError(message);
            }
        } finally {
            setLoading(false);
        }
    };

    const handleResendVerification = async () => {
        const emailToResend = emailNotVerified ? unverifiedEmail : registrationEmail;
        if (!emailToResend) return;

        setResendLoading(true);
        setResendMessage('');

        try {
            const result = await resendVerification(emailToResend);
            setResendMessage(result.message || 'Verification email sent!');
        } catch (err) {
            const detail = err.response?.data?.detail;
            setResendMessage(typeof detail === 'string' ? detail : 'Failed to resend verification email.');
        } finally {
            setResendLoading(false);
        }
    };

    const toggleMode = () => {
        setIsRegister(!isRegister);
        setError('');
        setRegistrationSuccess(false);
        setEmailNotVerified(false);
        setResendMessage('');
    };

    // Show registration success message
    if (registrationSuccess) {
        return (
            <div className="login-page">
                <button
                    className="theme-toggle-btn"
                    onClick={toggleTheme}
                    title="Toggle Theme"
                >
                    {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
                </button>

                <div className="login-container">
                    <div className="login-header">
                        <div className="login-logo success-logo">
                            <CheckCircle size={40} />
                        </div>
                        <h1 className="login-title">Check Your Email</h1>
                        <p className="login-subtitle">
                            We've sent a verification link to
                        </p>
                        <p className="email-highlight">{registrationEmail}</p>
                    </div>

                    <div className="verification-info">
                        <p>Click the link in the email to verify your account, then come back to log in.</p>

                        <div className="resend-section-inline">
                            <p>Didn't receive the email?</p>
                            <button
                                type="button"
                                className="resend-link-btn"
                                onClick={handleResendVerification}
                                disabled={resendLoading}
                            >
                                {resendLoading ? (
                                    <>
                                        <Loader className="spin" size={14} />
                                        <span>Sending...</span>
                                    </>
                                ) : (
                                    <span>Resend verification email</span>
                                )}
                            </button>
                            {resendMessage && (
                                <p className="resend-message-inline">{resendMessage}</p>
                            )}
                        </div>
                    </div>

                    <div className="login-footer">
                        <p>
                            Already verified?
                            <button
                                type="button"
                                className="toggle-mode-btn"
                                onClick={() => {
                                    setRegistrationSuccess(false);
                                    setIsRegister(false);
                                }}
                            >
                                Sign In
                            </button>
                        </p>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="login-page">
            {/* Theme Toggle */}
            <button
                className="theme-toggle-btn"
                onClick={toggleTheme}
                title="Toggle Theme"
            >
                {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
            </button>

            <div className="login-container">
                <div className="login-header">
                    <div className="login-logo">
                        <Database size={40} />
                    </div>
                    <h1 className="login-title">DataTalk</h1>
                    <p className="login-subtitle">
                        {isRegister ? 'Create your account' : 'Sign in to continue'}
                    </p>
                </div>

                <form className="login-form" onSubmit={handleSubmit}>
                    {error && (
                        <div className="login-error">
                            {error}
                        </div>
                    )}

                    {emailNotVerified && (
                        <div className="email-not-verified-notice">
                            <Mail size={20} />
                            <div className="notice-content">
                                <p><strong>Email not verified</strong></p>
                                <p>Please check your email ({unverifiedEmail}) for the verification link.</p>
                                <button
                                    type="button"
                                    className="resend-link-btn"
                                    onClick={handleResendVerification}
                                    disabled={resendLoading}
                                >
                                    {resendLoading ? 'Sending...' : 'Resend verification email'}
                                </button>
                                {resendMessage && (
                                    <p className="resend-message-inline">{resendMessage}</p>
                                )}
                            </div>
                        </div>
                    )}

                    <div className="form-group">
                        <label htmlFor="username">Username</label>
                        <input
                            type="text"
                            id="username"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            placeholder="Enter your username"
                            required
                            minLength={3}
                            maxLength={50}
                            autoComplete="username"
                        />
                    </div>

                    {isRegister && (
                        <>
                            <div className="form-group">
                                <label htmlFor="fullName">Full Name</label>
                                <input
                                    type="text"
                                    id="fullName"
                                    value={fullName}
                                    onChange={(e) => setFullName(e.target.value)}
                                    placeholder="Enter your full name"
                                    required
                                    maxLength={100}
                                    autoComplete="name"
                                />
                            </div>

                            <div className="form-group">
                                <label htmlFor="email">Email</label>
                                <input
                                    type="email"
                                    id="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="Enter your email"
                                    required
                                    autoComplete="email"
                                />
                            </div>
                        </>
                    )}

                    <div className="form-group">
                        <label htmlFor="password">Password</label>
                        <div className="password-input-wrapper">
                            <input
                                type={showPassword ? 'text' : 'password'}
                                id="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="Enter your password"
                                required
                                minLength={8}
                                autoComplete={isRegister ? 'new-password' : 'current-password'}
                            />
                            <button
                                type="button"
                                className="password-toggle"
                                onClick={() => setShowPassword(!showPassword)}
                                tabIndex={-1}
                            >
                                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                            </button>
                        </div>
                    </div>

                    <button
                        type="submit"
                        className="login-button"
                        disabled={loading}
                    >
                        {loading ? (
                            <>
                                <Loader className="spin" size={18} />
                                <span>{isRegister ? 'Creating account...' : 'Signing in...'}</span>
                            </>
                        ) : (
                            <span>{isRegister ? 'Create Account' : 'Sign In'}</span>
                        )}
                    </button>
                </form>

                <div className="login-footer">
                    <p>
                        {isRegister ? 'Already have an account?' : "Don't have an account?"}
                        <button
                            type="button"
                            className="toggle-mode-btn"
                            onClick={toggleMode}
                        >
                            {isRegister ? 'Sign In' : 'Create Account'}
                        </button>
                    </p>
                </div>
            </div>
        </div>
    );
};

export default LoginPage;
