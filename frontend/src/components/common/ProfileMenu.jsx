import React, { useState, useRef, useEffect } from 'react';
import { User, LogOut, Key, ChevronDown, X, Settings } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import './ProfileMenu.css';

const ProfileMenu = ({ onChangePassword, onCredentials }) => {
    const { user, logout } = useAuth();
    const [isOpen, setIsOpen] = useState(false);
    const menuRef = useRef(null);

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (menuRef.current && !menuRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleLogout = async () => {
        setIsOpen(false);
        await logout();
    };

    const handleChangePassword = () => {
        setIsOpen(false);
        if (onChangePassword) {
            onChangePassword();
        }
    };

    const handleCredentials = () => {
        setIsOpen(false);
        if (onCredentials) {
            onCredentials();
        }
    };

    if (!user) return null;

    return (
        <div className="profile-menu-wrapper" ref={menuRef}>
            <button
                className="profile-trigger"
                onClick={() => setIsOpen(!isOpen)}
                title="Profile"
            >
                <div className="profile-avatar">
                    {user.full_name?.charAt(0).toUpperCase() || user.username?.charAt(0).toUpperCase()}
                </div>
                <ChevronDown size={14} className={`chevron ${isOpen ? 'rotated' : ''}`} />
            </button>

            {isOpen && (
                <div className="profile-dropdown">
                    <div className="profile-header">
                        <div className="profile-avatar large">
                            {user.full_name?.charAt(0).toUpperCase() || user.username?.charAt(0).toUpperCase()}
                        </div>
                        <div className="profile-info">
                            <div className="profile-name">{user.full_name}</div>
                            <div className="profile-email">{user.email}</div>
                            <div className="profile-username">@{user.username}</div>
                        </div>
                    </div>

                    <div className="profile-divider" />

                    <div className="profile-actions">
                        <button className="profile-action" onClick={handleCredentials}>
                            <Settings size={16} />
                            <span>WatsonX Credentials</span>
                        </button>
                        <button className="profile-action" onClick={handleChangePassword}>
                            <Key size={16} />
                            <span>Change Password</span>
                        </button>
                        <button className="profile-action danger" onClick={handleLogout}>
                            <LogOut size={16} />
                            <span>Logout</span>
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ProfileMenu;

