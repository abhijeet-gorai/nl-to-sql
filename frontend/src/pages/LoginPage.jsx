import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Eye, EyeOff, Database, Loader, Sun, Moon } from 'lucide-react';
import './LoginPage.css';

const LoginPage = () => {
    const navigate = useNavigate();
    const { login, register } = useAuth();

    const [isRegister, setIsRegister] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');

    // Form fields
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');

    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
    }, [theme]);

    const toggleTheme = () => {
        setTheme(prev => prev === 'dark' ? 'light' : 'dark');
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            if (isRegister) {
                // Register then login
                await register({
                    username,
                    full_name: fullName,
                    email,
                    password,
                });
                // After registration, log in
                await login(username, password);
            } else {
                await login(username, password);
            }
            navigate('/projects');
        } catch (err) {
            const message = err.response?.data?.detail || err.message || 'Authentication failed';
            setError(typeof message === 'string' ? message : JSON.stringify(message));
        } finally {
            setLoading(false);
        }
    };

    const toggleMode = () => {
        setIsRegister(!isRegister);
        setError('');
    };

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
