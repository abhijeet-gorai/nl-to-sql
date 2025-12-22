import { API_BASE_URL } from './client';

/**
 * Send chat message with streaming response
 * @param {number} projectId
 * @param {string} message
 * @param {Array} selectedTables - List of table selection objects
 * @param {string} threadId
 * @returns {Promise<Response>} - Fetch response for streaming
 */
export const sendChatMessage = async (projectId, message, selectedTables, threadId) => {
    const token = localStorage.getItem('token');

    // Format tables for backend
    const formattedTables = selectedTables.map(t => ({
        table_name: t.table_name,
        source_type: t.source_type || 'csv',
        connection_id: t.connection_id,
        schema: t.schema_name,
    }));

    const response = await fetch(`${API_BASE_URL}/projects/${projectId}/chat`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
            message,
            selected_tables: formattedTables,
            thread_id: threadId,
        }),
    });

    if (!response.ok) {
        if (response.status === 401) {
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            window.location.href = '/login';
        }
        throw new Error(response.statusText);
    }

    return response;
};
