import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useProject } from '../context/ProjectContext';
import { getProjectTokenUsage } from '../api/projects';
import {
    FolderKanban,
    Plus,
    Users,
    Sun,
    Moon,
    Loader,
    ChevronRight,
    Trash2,
    Coins
} from 'lucide-react';
import ConfirmationModal from '../components/common/ConfirmationModal';
import ProfileMenu from '../components/common/ProfileMenu';
import TokenBadge from '../components/common/TokenTooltip';
import MembersPanel from '../components/MembersPanel';
import ChangePasswordModal from '../components/common/ChangePasswordModal';
import CredentialsModal from '../components/common/CredentialsModal';
import './ProjectsPage.css';

const ProjectsPage = () => {
    const navigate = useNavigate();
    const { user } = useAuth();
    const { projects, loading, refreshProjects, createProject, deleteProject, selectProject } = useProject();

    const [theme, setTheme] = useState(() => {
        return localStorage.getItem('theme') || 'dark';
    });
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [newProjectName, setNewProjectName] = useState('');
    const [newProjectDescription, setNewProjectDescription] = useState('');
    const [creating, setCreating] = useState(false);
    const [error, setError] = useState('');

    const [deleteConfirm, setDeleteConfirm] = useState({ isOpen: false, project: null });
    const [deleting, setDeleting] = useState(false);

    const [membersProject, setMembersProject] = useState(null);
    const [showChangePassword, setShowChangePassword] = useState(false);
    const [showCredentials, setShowCredentials] = useState(false);

    const [tokenUsage, setTokenUsage] = useState({});

    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
    }, [theme]);

    useEffect(() => {
        refreshProjects();
    }, [refreshProjects]);

    // Fetch token usage for each project
    useEffect(() => {
        const fetchTokenUsage = async () => {
            const usage = {};
            for (const project of projects) {
                try {
                    usage[project.id] = await getProjectTokenUsage(project.id);
                } catch (err) {
                    usage[project.id] = null;
                }
            }
            setTokenUsage(usage);
        };
        if (projects.length > 0) {
            fetchTokenUsage();
        }
    }, [projects]);

    const toggleTheme = () => {
        setTheme(prev => prev === 'dark' ? 'light' : 'dark');
    };

    const handleCreateProject = async (e) => {
        e.preventDefault();
        if (!newProjectName.trim()) return;

        setCreating(true);
        setError('');

        try {
            const project = await createProject({
                name: newProjectName.trim(),
                description: newProjectDescription.trim() || null,
            });
            setShowCreateModal(false);
            setNewProjectName('');
            setNewProjectDescription('');
            navigate(`/projects/${project.id}`);
        } catch (err) {
            const message = err.response?.data?.detail || 'Failed to create project';
            setError(typeof message === 'string' ? message : JSON.stringify(message));
        } finally {
            setCreating(false);
        }
    };

    const handleDeleteProject = async () => {
        if (!deleteConfirm.project) return;

        setDeleting(true);
        try {
            await deleteProject(deleteConfirm.project.id);
            setDeleteConfirm({ isOpen: false, project: null });
        } catch (err) {
            alert(err.response?.data?.detail || 'Failed to delete project');
        } finally {
            setDeleting(false);
        }
    };

    const openProject = (projectId) => {
        navigate(`/projects/${projectId}`);
    };

    const handleManageMembers = async (e, project) => {
        e.stopPropagation();
        try {
            await selectProject(project.id);
            setMembersProject(project);
        } catch (err) {
            alert('Failed to load project members');
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

    const formatTokenCount = (count) => {
        if (count === undefined || count === null) return '-';
        if (count >= 1000000) return (count / 1000000).toFixed(1) + 'M';
        if (count >= 1000) return (count / 1000).toFixed(1) + 'K';
        return count.toString();
    };

    return (
        <div className="projects-page">
            <header className="projects-header">
                <div className="header-left">
                    <FolderKanban size={28} className="header-icon" />
                    <h1>Projects</h1>
                </div>
                <div className="header-right">
                    <button className="icon-btn" onClick={toggleTheme} title="Toggle theme">
                        {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
                    </button>
                    <ProfileMenu
                        onChangePassword={() => setShowChangePassword(true)}
                        onCredentials={() => setShowCredentials(true)}
                    />
                </div>
            </header>

            <main className="projects-main">
                <div className="projects-toolbar">
                    <p className="projects-count">
                        {projects.length} project{projects.length !== 1 ? 's' : ''}
                    </p>
                    <button
                        className="create-project-btn"
                        onClick={() => setShowCreateModal(true)}
                    >
                        <Plus size={18} />
                        <span>New Project</span>
                    </button>
                </div>

                {loading ? (
                    <div className="projects-loading">
                        <Loader className="spin" size={32} />
                        <p>Loading projects...</p>
                    </div>
                ) : projects.length === 0 ? (
                    <div className="projects-empty">
                        <FolderKanban size={64} className="empty-icon" />
                        <h2>No projects yet</h2>
                        <p>Create your first project to get started with DataTalk</p>
                        <button
                            className="create-project-btn large"
                            onClick={() => setShowCreateModal(true)}
                        >
                            <Plus size={20} />
                            <span>Create Project</span>
                        </button>
                    </div>
                ) : (
                    <div className="projects-grid">
                        {projects.map((project) => (
                            <div
                                key={project.id}
                                className="project-card"
                                onClick={() => openProject(project.id)}
                            >
                                <div className="project-card-header">
                                    <h3 className="project-name">{project.name}</h3>
                                    <span className={`role-badge ${getRoleBadgeClass(project.role)}`}>
                                        {project.role}
                                    </span>
                                </div>
                                {project.description && (
                                    <p className="project-description">{project.description}</p>
                                )}
                                <div className="project-card-footer">
                                    <div className="project-meta-row">
                                        <div className="project-meta">
                                            <Users size={14} />
                                            <span>{project.member_count || 1} member{(project.member_count || 1) !== 1 ? 's' : ''}</span>
                                        </div>
                                        {tokenUsage[project.id] && (
                                            <TokenBadge data={tokenUsage[project.id]} type="project" position="top">
                                                <Coins size={14} />
                                                <span>{formatTokenCount(tokenUsage[project.id].total_tokens)} tokens</span>
                                            </TokenBadge>
                                        )}
                                    </div>
                                    <div className="project-actions">
                                        {project.role === 'admin' && (
                                            <>
                                                <button
                                                    className="project-action-btn"
                                                    onClick={(e) => handleManageMembers(e, project)}
                                                    title="Manage members"
                                                >
                                                    <Users size={16} />
                                                </button>
                                                <button
                                                    className="project-action-btn danger"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        setDeleteConfirm({ isOpen: true, project });
                                                    }}
                                                    title="Delete project"
                                                >
                                                    <Trash2 size={16} />
                                                </button>
                                            </>
                                        )}
                                        <ChevronRight size={20} className="chevron" />
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </main>

            {/* Create Project Modal */}
            {showCreateModal && (
                <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
                    <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                        <h2>Create New Project</h2>
                        <form onSubmit={handleCreateProject}>
                            {error && <div className="modal-error">{error}</div>}

                            <div className="form-group">
                                <label htmlFor="projectName">Project Name *</label>
                                <input
                                    type="text"
                                    id="projectName"
                                    value={newProjectName}
                                    onChange={(e) => setNewProjectName(e.target.value)}
                                    placeholder="Enter project name"
                                    required
                                    maxLength={100}
                                    autoFocus
                                />
                            </div>

                            <div className="form-group">
                                <label htmlFor="projectDescription">Description</label>
                                <textarea
                                    id="projectDescription"
                                    value={newProjectDescription}
                                    onChange={(e) => setNewProjectDescription(e.target.value)}
                                    placeholder="Optional project description"
                                    maxLength={500}
                                    rows={3}
                                />
                            </div>

                            <div className="modal-actions">
                                <button
                                    type="button"
                                    className="modal-btn secondary"
                                    onClick={() => setShowCreateModal(false)}
                                    disabled={creating}
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="modal-btn primary"
                                    disabled={creating || !newProjectName.trim()}
                                >
                                    {creating ? (
                                        <>
                                            <Loader className="spin" size={16} />
                                            <span>Creating...</span>
                                        </>
                                    ) : (
                                        <span>Create Project</span>
                                    )}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Delete Confirmation Modal */}
            <ConfirmationModal
                isOpen={deleteConfirm.isOpen}
                title="Delete Project"
                message={`Are you sure you want to delete "${deleteConfirm.project?.name}"? This will permanently delete all connections, tables, and data. This action cannot be undone.`}
                confirmText={deleting ? 'Deleting...' : 'Delete Project'}
                isDanger={true}
                onConfirm={handleDeleteProject}
                onCancel={() => setDeleteConfirm({ isOpen: false, project: null })}
            />

            {/* Members Panel */}
            {membersProject && (
                <MembersPanel
                    onClose={() => setMembersProject(null)}
                />
            )}

            {/* Change Password Modal */}
            {showChangePassword && (
                <ChangePasswordModal
                    onClose={() => setShowChangePassword(false)}
                />
            )}

            {/* Credentials Modal */}
            {showCredentials && (
                <CredentialsModal
                    onClose={() => setShowCredentials(false)}
                />
            )}
        </div>
    );
};

export default ProjectsPage;
