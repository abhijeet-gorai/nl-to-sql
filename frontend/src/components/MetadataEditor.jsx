import React, { useState } from 'react';
import { Check, ChevronLeft, ChevronRight } from 'lucide-react';

const MetadataEditor = ({ 
  tables, 
  onSave, 
  onCancel,
  isMultiple = false 
}) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [editedTables, setEditedTables] = useState(tables);

  const currentTable = editedTables[currentIndex];
  const isExternal = currentTable.source_type === 'external' || currentTable.schema_name;

  const handleDescriptionChange = (value) => {
    const updated = [...editedTables];
    updated[currentIndex] = { ...updated[currentIndex], description: value };
    setEditedTables(updated);
  };

  const handleColumnDescriptionChange = (columnIndex, value) => {
    const updated = [...editedTables];
    const columns = [...updated[currentIndex].columns];
    columns[columnIndex] = { ...columns[columnIndex], description: value };
    updated[currentIndex] = { ...updated[currentIndex], columns };
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

  const handleSave = () => {
    onSave(isMultiple ? editedTables : editedTables[0]);
  };

  return (
    <div className="editor-wrapper">
      <div className="editor-card">
        <div className="editor-header">
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>
              Metadata Configuration
              {isMultiple && ` (${currentIndex + 1} of ${editedTables.length})`}
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
              Review and enrich your dataset before analyzing.
            </p>
          </div>
        </div>

        <div className="editor-body">
          <div className="editor-row">
            <div className="field-group">
              <label className="field-label">Table Name</label>
              <input
                className="input-text"
                value={currentTable.table_name}
                disabled
                style={{ opacity: 0.6, cursor: 'not-allowed' }}
              />
            </div>
            <div className="field-group">
              <label className="field-label">
                {isExternal ? 'Schema Name' : 'Original Filename'}
              </label>
              <input 
                className="input-text" 
                value={isExternal ? currentTable.schema_name : currentTable.original_filename} 
                disabled 
                style={{ opacity: 0.6, cursor: 'not-allowed' }} 
              />
            </div>
          </div>

          <div className="field-group">
            <label className="field-label">Description</label>
            <textarea
              className="input-area"
              rows={2}
              value={currentTable.description || ''}
              onChange={(e) => handleDescriptionChange(e.target.value)}
              placeholder="What does this dataset contain?"
            />
          </div>

          <div className="columns-header">
            {currentTable.columns.length} Columns Detected
          </div>

          <div className="column-list">
            {currentTable.columns.map((col, idx) => (
              <div key={idx} className="column-row">
                <div className="col-meta">
                  <div className="col-name">{col.name}</div>
                  <div className="col-type">{col.type}</div>
                </div>
                <textarea
                  className="col-desc-input"
                  placeholder="Add a description for this column..."
                  rows={2}
                  value={col.description || ''}
                  onChange={(e) => handleColumnDescriptionChange(idx, e.target.value)}
                />
              </div>
            ))}
          </div>
        </div>

        <div className="editor-footer">
          {isMultiple && (
            <div style={{ display: 'flex', gap: '0.5rem', marginRight: 'auto' }}>
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
          )}
          <button className="btn btn-ghost" onClick={onCancel}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleSave}>
            <Check size={18} />
            {isMultiple ? 'Save All' : (currentTable.isEditing ? 'Save Changes' : 'Complete Registration')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default MetadataEditor;

// Made with Bob
