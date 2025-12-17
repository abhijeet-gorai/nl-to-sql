import React, { useState } from 'react';
import { X, ChevronLeft, ChevronRight, Save } from 'lucide-react';

const API_BASE_URL = 'http://localhost:8000';

const MetadataReview = ({ tables, onClose, onSave }) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [editedTables, setEditedTables] = useState(tables);
  const [saving, setSaving] = useState(false);

  const currentTable = editedTables[currentIndex];

  const handleDescriptionChange = (value) => {
    const updated = [...editedTables];
    updated[currentIndex] = { ...updated[currentIndex], description: value };
    setEditedTables(updated);
  };

  const handleColumnDescriptionChange = (columnIndex, value) => {
    const updated = [...editedTables];
    const columns = JSON.parse(updated[currentIndex].columns_metadata || '[]');
    columns[columnIndex] = { ...columns[columnIndex], description: value };
    updated[currentIndex] = {
      ...updated[currentIndex],
      columns_metadata: JSON.stringify(columns)
    };
    setEditedTables(updated);
  };

  const handleNext = () => {
    if (currentIndex < editedTables.length - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  };

  const handlePrevious = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  };

  const handleSaveAll = async () => {
    setSaving(true);
    try {
      // Save each table's metadata
      for (const table of editedTables) {
        await fetch(`${API_BASE_URL}/tables/${table.table_name}/metadata`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            description: table.description,
            columns: JSON.parse(table.columns_metadata || '[]')
          })
        });
      }
      onSave();
    } catch (e) {
      console.error('Failed to save metadata:', e);
    } finally {
      setSaving(false);
    }
  };

  const columns = JSON.parse(currentTable.columns_metadata || '[]');

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '800px', maxHeight: '90vh' }} onClick={e => e.stopPropagation()}>
        <div className="modal-header" style={{ position: 'relative' }}>
          <div>
            <div className="modal-title">
              Review Metadata ({currentIndex + 1} of {editedTables.length})
            </div>
            <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
              {currentTable.table_name}
            </div>
          </div>
          <button 
            className="icon-btn" 
            onClick={onClose}
            style={{ position: 'absolute', right: '1rem', top: '1rem' }}
          >
            <X size={20} />
          </button>
        </div>

        <div style={{ padding: '1.5rem', overflowY: 'auto', flex: 1 }}>
          <div className="field-group" style={{ marginBottom: '1.5rem' }}>
            <label className="field-label">Table Description</label>
            <textarea
              className="input-text"
              value={currentTable.description || ''}
              onChange={(e) => handleDescriptionChange(e.target.value)}
              placeholder="Describe what this table contains..."
              rows={3}
              style={{ resize: 'vertical' }}
            />
          </div>

          <div className="field-group">
            <label className="field-label">Column Descriptions</label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {columns.map((col, idx) => (
                <div key={idx} style={{ 
                  padding: '0.75rem', 
                  background: 'var(--bg-element)', 
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)'
                }}>
                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '0.5rem',
                    marginBottom: '0.5rem'
                  }}>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                      {col.name}
                    </span>
                    <span style={{ 
                      fontSize: '0.75rem', 
                      color: 'var(--text-tertiary)',
                      textTransform: 'uppercase'
                    }}>
                      {col.type}
                    </span>
                  </div>
                  <input
                    type="text"
                    className="input-text"
                    value={col.description || ''}
                    onChange={(e) => handleColumnDescriptionChange(idx, e.target.value)}
                    placeholder="Describe this column..."
                    style={{ fontSize: '0.9rem' }}
                  />
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="modal-actions" style={{ 
          display: 'flex', 
          justifyContent: 'space-between',
          borderTop: '1px solid var(--border-subtle)',
          padding: '1rem 1.5rem'
        }}>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button 
              className="btn btn-ghost"
              onClick={handlePrevious}
              disabled={currentIndex === 0}
            >
              <ChevronLeft size={16} />
              Previous
            </button>
            <button 
              className="btn btn-ghost"
              onClick={handleNext}
              disabled={currentIndex === editedTables.length - 1}
            >
              Next
              <ChevronRight size={16} />
            </button>
          </div>
          
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="btn btn-ghost" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button 
              className="btn btn-primary" 
              onClick={handleSaveAll}
              disabled={saving}
            >
              {saving ? (
                <>Saving...</>
              ) : (
                <>
                  <Save size={16} />
                  Save All
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MetadataReview;

// Made with Bob
