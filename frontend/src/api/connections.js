import apiClient from './client';

/**
 * Create a new database connection
 * @param {number} projectId
 * @param {Object} data - Connection details
 * @returns {Promise<Object>}
 */
export const createConnection = async (projectId, data) => {
    const response = await apiClient.post(`/projects/${projectId}/connections`, data);
    return response.data;
};

/**
 * List all connections in a project
 * @param {number} projectId
 * @returns {Promise<Array>}
 */
export const listConnections = async (projectId) => {
    const response = await apiClient.get(`/projects/${projectId}/connections`);
    return response.data;
};

/**
 * Get connection details
 * @param {number} projectId
 * @param {number} connectionId
 * @returns {Promise<Object>}
 */
export const getConnection = async (projectId, connectionId) => {
    const response = await apiClient.get(`/projects/${projectId}/connections/${connectionId}`);
    return response.data;
};

/**
 * Update a connection
 * @param {number} projectId
 * @param {number} connectionId
 * @param {Object} data
 * @returns {Promise<Object>}
 */
export const updateConnection = async (projectId, connectionId, data) => {
    const response = await apiClient.put(`/projects/${projectId}/connections/${connectionId}`, data);
    return response.data;
};

/**
 * Delete a connection
 * @param {number} projectId
 * @param {number} connectionId
 * @returns {Promise<Object>}
 */
export const deleteConnection = async (projectId, connectionId) => {
    const response = await apiClient.delete(`/projects/${projectId}/connections/${connectionId}`);
    return response.data;
};

/**
 * Test a saved connection
 * @param {number} projectId
 * @param {number} connectionId
 * @returns {Promise<Object>}
 */
export const testConnection = async (projectId, connectionId) => {
    const response = await apiClient.post(`/projects/${projectId}/connections/${connectionId}/test`);
    return response.data;
};

/**
 * Test connection data without saving
 * @param {number} projectId
 * @param {Object} data - Connection details
 * @returns {Promise<Object>}
 */
export const testConnectionData = async (projectId, data) => {
    const response = await apiClient.post(`/projects/${projectId}/connections/test`, data);
    return response.data;
};

/**
 * List schemas in a database
 * @param {number} projectId
 * @param {number} connectionId
 * @returns {Promise<Array>}
 */
export const listSchemas = async (projectId, connectionId) => {
    const response = await apiClient.get(`/projects/${projectId}/connections/${connectionId}/schemas`);
    return response.data;
};

/**
 * List tables in a schema
 * @param {number} projectId
 * @param {number} connectionId
 * @param {string} schema - Optional
 * @returns {Promise<Array>}
 */
export const listTables = async (projectId, connectionId, schema = null) => {
    const params = schema ? { schema } : {};
    const response = await apiClient.get(`/projects/${projectId}/connections/${connectionId}/tables`, { params });
    return response.data;
};

/**
 * Get table metadata
 * @param {number} projectId
 * @param {number} connectionId
 * @param {string} tableName
 * @param {string} schema
 * @returns {Promise<Object>}
 */
export const getTableMetadata = async (projectId, connectionId, tableName, schema = 'public') => {
    const response = await apiClient.get(
        `/projects/${projectId}/connections/${connectionId}/tables/${tableName}`,
        { params: { schema } }
    );
    return response.data;
};

/**
 * Sync tables from external database
 * @param {number} projectId
 * @param {number} connectionId
 * @param {Array} tables - List of table objects to sync
 * @returns {Promise<Object>}
 */
export const syncTables = async (projectId, connectionId, tables) => {
    const response = await apiClient.post(
        `/projects/${projectId}/connections/${connectionId}/tables/sync`,
        { tables }
    );
    return response.data;
};

/**
 * Preview table data
 * @param {number} projectId
 * @param {number} connectionId
 * @param {string} tableName
 * @param {string} schema
 * @param {number} limit
 * @returns {Promise<Object>}
 */
export const previewTable = async (projectId, connectionId, tableName, schema = 'public', limit = 100) => {
    const response = await apiClient.get(
        `/projects/${projectId}/connections/${connectionId}/tables/${tableName}/preview`,
        { params: { schema, limit } }
    );
    return response.data;
};
