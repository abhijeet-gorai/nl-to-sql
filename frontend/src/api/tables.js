import apiClient from './client';

/**
 * Analyze a CSV file
 * @param {number} projectId
 * @param {File} file
 * @returns {Promise<Object>} - Analysis result
 */
export const analyzeFile = async (projectId, file) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post(`/projects/${projectId}/analyze`, formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

/**
 * Register a table in a project
 * @param {number} projectId
 * @param {Object} data - { file_path, metadata }
 * @returns {Promise<Object>}
 */
export const registerTable = async (projectId, data) => {
    const response = await apiClient.post(`/projects/${projectId}/tables/register`, data);
    return response.data;
};

/**
 * Get all tables in a project
 * @param {number} projectId
 * @returns {Promise<Array>} - List of tables
 */
export const getTables = async (projectId) => {
    const response = await apiClient.get(`/projects/${projectId}/tables`);
    return response.data;
};

/**
 * Update table metadata
 * @param {number} projectId
 * @param {string} tableName
 * @param {Object} metadata
 * @param {Object} options - { sourceType, connectionId, schema }
 * @returns {Promise<Object>}
 */
export const updateTable = async (projectId, tableName, metadata, options = {}) => {
    const params = new URLSearchParams();
    if (options.sourceType) params.append('source_type', options.sourceType);
    if (options.connectionId) params.append('connection_id', options.connectionId);
    if (options.schema) params.append('schema', options.schema);

    const queryString = params.toString() ? `?${params.toString()}` : '';

    const response = await apiClient.put(
        `/projects/${projectId}/tables/${tableName}${queryString}`,
        { metadata }
    );
    return response.data;
};

/**
 * Delete a table
 * @param {number} projectId
 * @param {string} tableName
 * @param {Object} options - { sourceType, connectionId, schema }
 * @returns {Promise<Object>}
 */
export const deleteTable = async (projectId, tableName, options = {}) => {
    const params = new URLSearchParams();
    if (options.sourceType) params.append('source_type', options.sourceType);
    if (options.connectionId) params.append('connection_id', options.connectionId);
    if (options.schema) params.append('schema', options.schema);

    const queryString = params.toString() ? `?${params.toString()}` : '';

    const response = await apiClient.delete(
        `/projects/${projectId}/tables/${tableName}${queryString}`
    );
    return response.data;
};

/**
 * Get external tables in a project
 * @param {number} projectId
 * @param {number} connectionId - Optional
 * @returns {Promise<Array>}
 */
export const getExternalTables = async (projectId, connectionId = null) => {
    const params = connectionId ? { connection_id: connectionId } : {};
    const response = await apiClient.get(`/projects/${projectId}/external-tables`, { params });
    return response.data;
};
