import apiClient from './client';

/**
 * List all projects the current user has access to
 * @returns {Promise<Array>} - List of projects
 */
export const listProjects = async () => {
    const response = await apiClient.get('/projects');
    return response.data;
};

/**
 * Create a new project
 * @param {Object} data - { name, description? }
 * @returns {Promise<Object>} - Created project
 */
export const createProject = async (data) => {
    const response = await apiClient.post('/projects', data);
    return response.data;
};

/**
 * Get project details
 * @param {number} projectId
 * @returns {Promise<Object>} - Project details
 */
export const getProject = async (projectId) => {
    const response = await apiClient.get(`/projects/${projectId}`);
    return response.data;
};

/**
 * Update project
 * @param {number} projectId
 * @param {Object} data - { name?, description? }
 * @returns {Promise<Object>} - Updated project
 */
export const updateProject = async (projectId, data) => {
    const response = await apiClient.put(`/projects/${projectId}`, data);
    return response.data;
};

/**
 * Delete a project
 * @param {number} projectId
 * @returns {Promise<Object>}
 */
export const deleteProject = async (projectId) => {
    const response = await apiClient.delete(`/projects/${projectId}`);
    return response.data;
};

/**
 * List project members
 * @param {number} projectId
 * @returns {Promise<Array>} - List of members
 */
export const listMembers = async (projectId) => {
    const response = await apiClient.get(`/projects/${projectId}/members`);
    return response.data;
};

/**
 * Add member to project
 * @param {number} projectId
 * @param {string} usernameOrEmail
 * @param {string} role - 'read' | 'write' | 'admin'
 * @returns {Promise<Object>}
 */
export const addMember = async (projectId, usernameOrEmail, role) => {
    const response = await apiClient.post(`/projects/${projectId}/members`, {
        username_or_email: usernameOrEmail,
        role,
    });
    return response.data;
};

/**
 * Update member role
 * @param {number} projectId
 * @param {number} userId
 * @param {string} role - 'read' | 'write' | 'admin'
 * @returns {Promise<Object>}
 */
export const updateMemberRole = async (projectId, userId, role) => {
    const response = await apiClient.put(`/projects/${projectId}/members/${userId}`, {
        role,
    });
    return response.data;
};

/**
 * Remove member from project
 * @param {number} projectId
 * @param {number} userId
 * @returns {Promise<Object>}
 */
export const removeMember = async (projectId, userId) => {
    const response = await apiClient.delete(`/projects/${projectId}/members/${userId}`);
    return response.data;
};
