import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import { LoginPage, ProjectsPage, WorkspacePage } from './pages';

// Protected route wrapper
const ProtectedRoute = ({ children }) => {
    const { isAuthenticated, loading } = useAuth();

    if (loading) {
        return (
            <div className="app-loading">
                <div className="loading-spinner"></div>
                <p>Loading...</p>
            </div>
        );
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    return children;
};

// Public route wrapper (redirect if already authenticated)
const PublicRoute = ({ children }) => {
    const { isAuthenticated, loading } = useAuth();

    if (loading) {
        return (
            <div className="app-loading">
                <div className="loading-spinner"></div>
                <p>Loading...</p>
            </div>
        );
    }

    if (isAuthenticated) {
        return <Navigate to="/projects" replace />;
    }

    return children;
};

const AppRouter = () => {
    return (
        <Routes>
            {/* Public routes */}
            <Route
                path="/login"
                element={
                    <PublicRoute>
                        <LoginPage />
                    </PublicRoute>
                }
            />

            {/* Protected routes */}
            <Route
                path="/projects"
                element={
                    <ProtectedRoute>
                        <ProjectsPage />
                    </ProtectedRoute>
                }
            />

            <Route
                path="/projects/:projectId"
                element={
                    <ProtectedRoute>
                        <WorkspacePage />
                    </ProtectedRoute>
                }
            />

            {/* Default redirect */}
            <Route
                path="/"
                element={<Navigate to="/projects" replace />}
            />

            {/* 404 - redirect to projects */}
            <Route
                path="*"
                element={<Navigate to="/projects" replace />}
            />
        </Routes>
    );
};

export default AppRouter;
