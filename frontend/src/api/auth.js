import apiClient from './client';

/**
 * Register a new user
 * @param {Object} data - { username, full_name, email, password }
 * @returns {Promise<Object>} - User info
 */
export const register = async (data) => {
    const response = await apiClient.post('/auth/register', data);
    return response.data;
};

/**
 * Login user
 * @param {string} username
 * @param {string} password
 * @returns {Promise<Object>} - { access_token, token_type, user }
 */
export const login = async (username, password) => {
    const response = await apiClient.post('/auth/login', { username, password });
    return response.data;
};

/**
 * Logout current user
 * @returns {Promise<Object>}
 */
export const logout = async () => {
    const response = await apiClient.post('/auth/logout');
    return response.data;
};

/**
 * Get current user profile
 * @returns {Promise<Object>} - User info
 */
export const getMe = async () => {
    const response = await apiClient.get('/auth/me');
    return response.data;
};

/**
 * Change password
 * @param {string} currentPassword
 * @param {string} newPassword
 * @returns {Promise<Object>}
 */
export const changePassword = async (currentPassword, newPassword) => {
    const response = await apiClient.put('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
    });
    return response.data;
};

/**
 * Search users by query
 * @param {string} query
 * @param {number} limit
 * @returns {Promise<Array>} - List of users
 */
export const searchUsers = async (query, limit = 10) => {
    const response = await apiClient.get('/auth/users/search', {
        params: { q: query, limit },
    });
    return response.data;
};

/**
 * Verify email with token
 * @param {string} token - Verification token from email
 * @returns {Promise<Object>} - { status, message }
 */
export const verifyEmail = async (token) => {
    const response = await apiClient.get('/auth/verify-email', {
        params: { token },
    });
    return response.data;
};

/**
 * Resend verification email
 * @param {string} email - Email address to send verification to
 * @returns {Promise<Object>} - { status, message }
 */
export const resendVerification = async (email) => {
    const response = await apiClient.post('/auth/resend-verification', { email });
    return response.data;
};
