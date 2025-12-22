import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import * as authApi from '../api/auth';

const AuthContext = createContext(null);

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(() => localStorage.getItem('token'));
    const [loading, setLoading] = useState(true);

    // Check for existing session on mount
    useEffect(() => {
        const initAuth = async () => {
            const storedToken = localStorage.getItem('token');
            if (storedToken) {
                try {
                    const userData = await authApi.getMe();
                    setUser(userData);
                    setToken(storedToken);
                } catch (error) {
                    // Token is invalid, clear it
                    localStorage.removeItem('token');
                    localStorage.removeItem('user');
                    setToken(null);
                    setUser(null);
                }
            }
            setLoading(false);
        };

        initAuth();
    }, []);

    const login = useCallback(async (username, password) => {
        const response = await authApi.login(username, password);
        const { access_token, user: userData } = response;

        localStorage.setItem('token', access_token);
        localStorage.setItem('user', JSON.stringify(userData));

        setToken(access_token);
        setUser(userData);

        return userData;
    }, []);

    const register = useCallback(async (data) => {
        const userData = await authApi.register(data);
        return userData;
    }, []);

    const logout = useCallback(async () => {
        try {
            await authApi.logout();
        } catch (error) {
            // Ignore logout errors
        }

        localStorage.removeItem('token');
        localStorage.removeItem('user');
        setToken(null);
        setUser(null);
    }, []);

    const changePassword = useCallback(async (currentPassword, newPassword) => {
        await authApi.changePassword(currentPassword, newPassword);
    }, []);

    const value = {
        user,
        token,
        loading,
        isAuthenticated: !!token && !!user,
        login,
        register,
        logout,
        changePassword,
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
};

export default AuthContext;
