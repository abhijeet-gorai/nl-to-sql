"""
Projects Module
Handles project management and member access control
"""

import sqlite3
from typing import Optional, List, Dict
from pydantic import BaseModel

# Database path
DB_PATH = "database.db"

# Valid roles
VALID_ROLES = ["read", "write", "admin"]


class Project(BaseModel):
    """Project model for API responses"""

    id: int
    name: str
    description: Optional[str] = None
    created_by: int
    created_at: Optional[str] = None


class ProjectMember(BaseModel):
    """Project member model"""

    user_id: int
    username: str
    full_name: str
    email: str
    role: str
    added_at: Optional[str] = None


def init_projects_tables():
    """Initialize the projects and project_members tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create projects table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """)

    # Create project_members table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('read', 'write', 'admin')),
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            added_by INTEGER,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (added_by) REFERENCES users(id),
            UNIQUE(project_id, user_id)
        )
    """)

    conn.commit()
    conn.close()


def create_project(name: str, description: str, created_by: int) -> int:
    """
    Create a new project and add creator as admin.
    Returns the project ID.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Create project
        cursor.execute(
            """
            INSERT INTO projects (name, description, created_by)
            VALUES (?, ?, ?)
        """,
            (name, description, created_by),
        )

        project_id = cursor.lastrowid

        # Add creator as admin
        cursor.execute(
            """
            INSERT INTO project_members (project_id, user_id, role, added_by)
            VALUES (?, ?, 'admin', ?)
        """,
            (project_id, created_by, created_by),
        )

        conn.commit()
        return project_id

    except sqlite3.IntegrityError:
        raise ValueError(f"Project name '{name}' already exists")
    finally:
        conn.close()


def get_project(project_id: int) -> Optional[Dict]:
    """Get project by ID"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def get_user_projects(user_id: int) -> List[Dict]:
    """Get all projects a user has access to"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT 
            p.id,
            p.name,
            p.description,
            p.created_by,
            p.created_at,
            pm.role,
            (SELECT COUNT(*) FROM project_members WHERE project_id = p.id) as member_count
        FROM projects p
        JOIN project_members pm ON p.id = pm.project_id
        WHERE pm.user_id = ?
        ORDER BY p.name
    """,
        (user_id,),
    )

    projects = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return projects


def update_project(project_id: int, name: str = None, description: str = None) -> bool:
    """Update project details"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        updates = []
        values = []

        if name is not None:
            updates.append("name = ?")
            values.append(name)
        if description is not None:
            updates.append("description = ?")
            values.append(description)

        if not updates:
            return False

        updates.append("updated_at = CURRENT_TIMESTAMP")
        values.append(project_id)

        cursor.execute(
            f"""
            UPDATE projects 
            SET {", ".join(updates)}
            WHERE id = ?
        """,
            tuple(values),
        )

        conn.commit()
        return cursor.rowcount > 0

    except sqlite3.IntegrityError:
        raise ValueError(f"Project name '{name}' already exists")
    finally:
        conn.close()


def delete_project(project_id: int) -> bool:
    """
    Delete a project and all associated resources.
    This will cascade delete project_members due to FK constraint.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Delete associated resources first
        # Delete external tables
        cursor.execute(
            "DELETE FROM external_tables WHERE project_id = ?", (project_id,)
        )

        # Delete connections
        cursor.execute("DELETE FROM db_connections WHERE project_id = ?", (project_id,))

        # Delete CSV table metadata
        cursor.execute("DELETE FROM app_metadata WHERE project_id = ?", (project_id,))

        # Delete project (cascades to project_members)
        cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))

        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def add_project_member(project_id: int, user_id: int, role: str, added_by: int) -> bool:
    """Add a user to a project with specified role"""
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role. Must be one of: {VALID_ROLES}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO project_members (project_id, user_id, role, added_by)
            VALUES (?, ?, ?, ?)
        """,
            (project_id, user_id, role, added_by),
        )

        conn.commit()
        return True

    except sqlite3.IntegrityError:
        raise ValueError("User is already a member of this project")
    finally:
        conn.close()


def remove_project_member(project_id: int, user_id: int) -> bool:
    """Remove a user from a project"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if this is the last admin
        cursor.execute(
            """
            SELECT COUNT(*) FROM project_members 
            WHERE project_id = ? AND role = 'admin' AND user_id != ?
        """,
            (project_id, user_id),
        )

        other_admins = cursor.fetchone()[0]

        # Check if user being removed is an admin
        cursor.execute(
            """
            SELECT role FROM project_members 
            WHERE project_id = ? AND user_id = ?
        """,
            (project_id, user_id),
        )

        user_role = cursor.fetchone()
        if user_role and user_role[0] == "admin" and other_admins == 0:
            raise ValueError("Cannot remove the last admin from the project")

        cursor.execute(
            """
            DELETE FROM project_members 
            WHERE project_id = ? AND user_id = ?
        """,
            (project_id, user_id),
        )

        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_member_role(project_id: int, user_id: int, new_role: str) -> bool:
    """Update a member's role in a project"""
    if new_role not in VALID_ROLES:
        raise ValueError(f"Invalid role. Must be one of: {VALID_ROLES}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if demoting last admin
        cursor.execute(
            """
            SELECT role FROM project_members 
            WHERE project_id = ? AND user_id = ?
        """,
            (project_id, user_id),
        )

        current = cursor.fetchone()
        if not current:
            return False

        if current[0] == "admin" and new_role != "admin":
            # Check if there's another admin
            cursor.execute(
                """
                SELECT COUNT(*) FROM project_members 
                WHERE project_id = ? AND role = 'admin' AND user_id != ?
            """,
                (project_id, user_id),
            )

            if cursor.fetchone()[0] == 0:
                raise ValueError("Cannot demote the last admin")

        cursor.execute(
            """
            UPDATE project_members 
            SET role = ?
            WHERE project_id = ? AND user_id = ?
        """,
            (new_role, project_id, user_id),
        )

        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_project_members(project_id: int) -> List[Dict]:
    """Get all members of a project"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT 
            u.id as user_id,
            u.username,
            u.full_name,
            u.email,
            pm.role,
            pm.added_at
        FROM project_members pm
        JOIN users u ON pm.user_id = u.id
        WHERE pm.project_id = ?
        ORDER BY pm.role DESC, u.username
    """,
        (project_id,),
    )

    members = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return members


def get_user_role(project_id: int, user_id: int) -> Optional[str]:
    """Get a user's role in a project"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT role FROM project_members 
        WHERE project_id = ? AND user_id = ?
    """,
        (project_id, user_id),
    )

    row = cursor.fetchone()
    conn.close()

    return row[0] if row else None


def user_has_access(project_id: int, user_id: int, min_role: str = "read") -> bool:
    """
    Check if user has at least the specified role level.
    Role hierarchy: admin > write > read
    """
    role = get_user_role(project_id, user_id)
    if not role:
        return False

    role_levels = {"read": 1, "write": 2, "admin": 3}
    return role_levels.get(role, 0) >= role_levels.get(min_role, 0)
