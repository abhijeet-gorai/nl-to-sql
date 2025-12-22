import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import * as projectsApi from '../api/projects';
import { useAuth } from './AuthContext';

const ProjectContext = createContext(null);

export const useProject = () => {
    const context = useContext(ProjectContext);
    if (!context) {
        throw new Error('useProject must be used within a ProjectProvider');
    }
    return context;
};

export const ProjectProvider = ({ children }) => {
    const { isAuthenticated } = useAuth();

    const [projects, setProjects] = useState([]);
    const [currentProject, setCurrentProject] = useState(null);
    const [members, setMembers] = useState([]);
    const [userRole, setUserRole] = useState(null);
    const [loading, setLoading] = useState(false);

    // Load projects when authenticated
    const refreshProjects = useCallback(async () => {
        if (!isAuthenticated) return;

        setLoading(true);
        try {
            const projectList = await projectsApi.listProjects();
            setProjects(projectList);
        } catch (error) {
            console.error('Failed to fetch projects:', error);
        } finally {
            setLoading(false);
        }
    }, [isAuthenticated]);

    // Load projects on auth change
    useEffect(() => {
        if (isAuthenticated) {
            refreshProjects();
        } else {
            setProjects([]);
            setCurrentProject(null);
            setMembers([]);
            setUserRole(null);
        }
    }, [isAuthenticated, refreshProjects]);

    // Select a project and load its details
    const selectProject = useCallback(async (projectId) => {
        if (!projectId) {
            setCurrentProject(null);
            setMembers([]);
            setUserRole(null);
            return;
        }

        try {
            const project = await projectsApi.getProject(projectId);
            setCurrentProject(project);
            setUserRole(project.role);

            // Also load members
            const memberList = await projectsApi.listMembers(projectId);
            setMembers(memberList);
        } catch (error) {
            console.error('Failed to select project:', error);
            throw error;
        }
    }, []);

    // Refresh members list
    const refreshMembers = useCallback(async () => {
        if (!currentProject) return;

        try {
            const memberList = await projectsApi.listMembers(currentProject.id);
            setMembers(memberList);
        } catch (error) {
            console.error('Failed to fetch members:', error);
        }
    }, [currentProject]);

    // Create a new project
    const createProject = useCallback(async (data) => {
        const newProject = await projectsApi.createProject(data);
        await refreshProjects();
        return newProject;
    }, [refreshProjects]);

    // Delete a project
    const deleteProject = useCallback(async (projectId) => {
        await projectsApi.deleteProject(projectId);

        // If deleted project was current, clear it
        if (currentProject?.id === projectId) {
            setCurrentProject(null);
            setMembers([]);
            setUserRole(null);
        }

        await refreshProjects();
    }, [currentProject, refreshProjects]);

    // Add member to current project
    const addMember = useCallback(async (usernameOrEmail, role) => {
        if (!currentProject) throw new Error('No project selected');

        await projectsApi.addMember(currentProject.id, usernameOrEmail, role);
        await refreshMembers();
    }, [currentProject, refreshMembers]);

    // Update member role
    const updateMemberRole = useCallback(async (userId, newRole) => {
        if (!currentProject) throw new Error('No project selected');

        await projectsApi.updateMemberRole(currentProject.id, userId, newRole);
        await refreshMembers();
    }, [currentProject, refreshMembers]);

    // Remove member
    const removeMember = useCallback(async (userId) => {
        if (!currentProject) throw new Error('No project selected');

        await projectsApi.removeMember(currentProject.id, userId);
        await refreshMembers();
    }, [currentProject, refreshMembers]);

    const value = {
        projects,
        currentProject,
        members,
        userRole,
        loading,

        // Permission helpers
        canRead: !!userRole,
        canWrite: userRole === 'write' || userRole === 'admin',
        isAdmin: userRole === 'admin',

        // Actions
        refreshProjects,
        selectProject,
        refreshMembers,
        createProject,
        deleteProject,
        addMember,
        updateMemberRole,
        removeMember,
    };

    return (
        <ProjectContext.Provider value={value}>
            {children}
        </ProjectContext.Provider>
    );
};

export default ProjectContext;
