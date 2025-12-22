import React, { useState, useEffect } from 'react';
import { X, Users, UserPlus, Trash2, Loader, Search, Shield, Pencil, Eye } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { useAuth } from '../context/AuthContext';
import * as authApi from '../api/auth';
import CustomSelect from './CustomSelect';
import './MembersPanel.css';

const MembersPanel = ({ onClose }) => {
    const { user } = useAuth();
    const {
        currentProject,
        members,
        refreshMembers,
        addMember,
        updateMemberRole,
        removeMember,
        isAdmin
    } = useProject();

    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [searching, setSearching] = useState(false);
    const [selectedRole, setSelectedRole] = useState('read');
    const [showAddForm, setShowAddForm] = useState(false);
    const [addingMember, setAddingMember] = useState(false);
    const [error, setError] = useState('');

    const roleOptions = [
        { value: 'read', label: 'Read Only' },
        { value: 'write', label: 'Write' },
        { value: 'admin', label: 'Admin' }
    ];

    useEffect(() => {
        refreshMembers();
    }, [refreshMembers]);

    // Debounced search
    useEffect(() => {
        if (!searchQuery.trim()) {
            setSearchResults([]);
            return;
        }

        const timer = setTimeout(async () => {
            setSearching(true);
            try {
                const results = await authApi.searchUsers(searchQuery, 10);
                // Filter out users who are already members
                const filtered = results.filter(
                    u => !members.some(m => m.user_id === u.id)
                );
                setSearchResults(filtered);
            } catch (err) {
                console.error('Search failed:', err);
            } finally {
                setSearching(false);
            }
        }, 300);

        return () => clearTimeout(timer);
    }, [searchQuery, members]);

    const handleAddMember = async (userToAdd) => {
        setAddingMember(true);
        setError('');

        try {
            await addMember(userToAdd.username, selectedRole);
            setSearchQuery('');
            setSearchResults([]);
            setShowAddForm(false);
        } catch (err) {
            const message = err.response?.data?.detail || 'Failed to add member';
            setError(typeof message === 'string' ? message : JSON.stringify(message));
        } finally {
            setAddingMember(false);
        }
    };

    const handleRoleChange = async (userId, newRole) => {
        try {
            await updateMemberRole(userId, newRole);
        } catch (err) {
            alert(err.response?.data?.detail || 'Failed to update role');
        }
    };

    const handleRemoveMember = async (userId, username) => {
        if (!confirm(`Remove ${username} from this project?`)) return;

        try {
            await removeMember(userId);
        } catch (err) {
            alert(err.response?.data?.detail || 'Failed to remove member');
        }
    };

    const getRoleIcon = (role) => {
        switch (role) {
            case 'admin': return <Shield size={14} />;
            case 'write': return <Pencil size={14} />;
            case 'read': return <Eye size={14} />;
            default: return null;
        }
    };

    const getRoleBadgeClass = (role) => {
        switch (role) {
            case 'admin': return 'badge-admin';
            case 'write': return 'badge-write';
            case 'read': return 'badge-read';
            default: return '';
        }
    };

    return (
        <div className="members-overlay" onClick={onClose}>
            <div className="members-panel" onClick={(e) => e.stopPropagation()}>
                <div className="members-header">
                    <div className="members-title">
                        <Users size={20} />
                        <div>
                            <h2>Project Members</h2>
                            {currentProject && (
                                <span className="project-name-subtitle">{currentProject.name}</span>
                            )}
                        </div>
                    </div>
                    <button className="icon-btn close-btn" onClick={onClose}>
                        <X size={20} />
                    </button>
                </div>

                <div className="members-content">
                    {/* Add Member Section (Admin only) */}
                    {isAdmin && (
                        <div className="add-member-section">
                            {!showAddForm ? (
                                <button
                                    className="add-member-btn"
                                    onClick={() => setShowAddForm(true)}
                                >
                                    <UserPlus size={18} />
                                    <span>Add Member</span>
                                </button>
                            ) : (
                                <div className="add-member-form">
                                    <div className="form-row">
                                        <div className="search-wrapper">
                                            <Search size={16} className="search-icon" />
                                            <input
                                                type="text"
                                                placeholder="Search by username or email..."
                                                value={searchQuery}
                                                onChange={(e) => setSearchQuery(e.target.value)}
                                                autoFocus
                                            />
                                            {searching && <Loader size={16} className="spin search-loader" />}
                                        </div>
                                    </div>

                                    <div className="form-row role-row">
                                        <CustomSelect
                                            label="Role"
                                            options={roleOptions}
                                            value={selectedRole}
                                            onChange={setSelectedRole}
                                            placeholder="Select role..."
                                        />
                                    </div>

                                    {searchResults.length > 0 && (
                                        <div className="search-results">
                                            <div className="search-results-label">Select user to add:</div>
                                            {searchResults.map((u) => (
                                                <div
                                                    key={u.id}
                                                    className="search-result-item"
                                                    onClick={() => handleAddMember(u)}
                                                >
                                                    <div className="result-avatar">
                                                        {u.full_name?.charAt(0).toUpperCase() || u.username.charAt(0).toUpperCase()}
                                                    </div>
                                                    <div className="result-info">
                                                        <span className="result-name">{u.full_name}</span>
                                                        <span className="result-email">{u.email}</span>
                                                    </div>
                                                    <span className="result-username">@{u.username}</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}

                                    {searchQuery && !searching && searchResults.length === 0 && (
                                        <div className="no-results">
                                            <span>No users found matching "{searchQuery}"</span>
                                        </div>
                                    )}

                                    {error && <div className="add-error">{error}</div>}

                                    <div className="form-actions">
                                        <button
                                            className="btn-secondary"
                                            onClick={() => {
                                                setShowAddForm(false);
                                                setSearchQuery('');
                                                setSearchResults([]);
                                                setError('');
                                            }}
                                        >
                                            Cancel
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Members List */}
                    <div className="members-list">
                        <div className="members-list-header">
                            <span>{members.length} member{members.length !== 1 ? 's' : ''}</span>
                        </div>

                        {members.length === 0 ? (
                            <div className="no-members">
                                <Users size={40} />
                                <p>No members yet</p>
                            </div>
                        ) : (
                            members.map((member) => (
                                <div key={member.user_id} className="member-item">
                                    <div className="member-avatar">
                                        {member.full_name?.charAt(0).toUpperCase() || '?'}
                                    </div>
                                    <div className="member-info">
                                        <span className="member-name">
                                            {member.full_name}
                                            {member.user_id === user?.id && (
                                                <span className="you-badge">you</span>
                                            )}
                                        </span>
                                        <span className="member-email">{member.email}</span>
                                    </div>

                                    <div className="member-actions">
                                        {isAdmin && member.user_id !== user?.id ? (
                                            <>
                                                <CustomSelect
                                                    options={roleOptions}
                                                    value={member.role}
                                                    onChange={(newRole) => handleRoleChange(member.user_id, newRole)}
                                                />
                                                <button
                                                    className="icon-btn remove-btn"
                                                    onClick={() => handleRemoveMember(member.user_id, member.username)}
                                                    title="Remove member"
                                                >
                                                    <Trash2 size={16} />
                                                </button>
                                            </>
                                        ) : (
                                            <span className={`role-badge ${getRoleBadgeClass(member.role)}`}>
                                                {getRoleIcon(member.role)}
                                                <span>{member.role}</span>
                                            </span>
                                        )}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default MembersPanel;
