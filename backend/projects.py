"""
Projects Module
Handles project management and member access control
"""

from typing import Optional, List, Dict
from pydantic import BaseModel
import asyncpg

from database_config import get_connection, get_transaction, execute, fetch, fetchrow, fetchval

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


async def init_projects_tables():
    """Initialize the projects and project_members tables"""
    async with get_connection() as conn:
        # Create projects table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        """)

        # Create project_members table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS project_members (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('read', 'write', 'admin')),
                added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                added_by INTEGER,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (added_by) REFERENCES users(id),
                UNIQUE(project_id, user_id)
            )
        """)


async def create_project(name: str, description: str, created_by: int) -> int:
    """
    Create a new project and add creator as admin.
    Returns the project ID.
    """
    try:
        async with get_transaction() as conn:
            # Create project
            project_id = await conn.fetchval(
                """
                INSERT INTO projects (name, description, created_by)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                name, description, created_by
            )

            # Add creator as admin
            await conn.execute(
                """
                INSERT INTO project_members (project_id, user_id, role, added_by)
                VALUES ($1, $2, 'admin', $3)
                """,
                project_id, created_by, created_by
            )

            return project_id

    except asyncpg.UniqueViolationError:
        raise ValueError(f"Project name '{name}' already exists")


async def get_project(project_id: int) -> Optional[Dict]:
    """Get project by ID"""
    row = await fetchrow("SELECT * FROM projects WHERE id = $1", project_id)
    return dict(row) if row else None


async def get_user_projects(user_id: int) -> List[Dict]:
    """Get all projects a user has access to"""
    rows = await fetch(
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
        WHERE pm.user_id = $1
        ORDER BY p.name
        """,
        user_id
    )
    return [dict(row) for row in rows]


async def update_project(project_id: int, name: str = None, description: str = None) -> bool:
    """Update project details"""
    try:
        updates = []
        values = []
        param_num = 1

        if name is not None:
            updates.append(f"name = ${param_num}")
            values.append(name)
            param_num += 1
        if description is not None:
            updates.append(f"description = ${param_num}")
            values.append(description)
            param_num += 1

        if not updates:
            return False

        updates.append("updated_at = NOW()")
        values.append(project_id)

        query = f"""
            UPDATE projects 
            SET {", ".join(updates)}
            WHERE id = ${param_num}
        """
        result = await execute(query, *values)
        return "UPDATE" in result

    except asyncpg.UniqueViolationError:
        raise ValueError(f"Project name '{name}' already exists")


async def delete_project(project_id: int) -> bool:
    """
    Delete a project and all associated resources.
    This will cascade delete project_members due to FK constraint.
    """
    async with get_transaction() as conn:
        # Delete associated resources first
        # Delete external tables
        await conn.execute(
            "DELETE FROM external_tables WHERE project_id = $1", project_id
        )

        # Delete connections
        await conn.execute(
            "DELETE FROM db_connections WHERE project_id = $1", project_id
        )

        # Delete CSV table metadata
        await conn.execute(
            "DELETE FROM app_metadata WHERE project_id = $1", project_id
        )

        # Delete project (cascades to project_members)
        result = await conn.execute("DELETE FROM projects WHERE id = $1", project_id)
        return "DELETE" in result


async def add_project_member(project_id: int, user_id: int, role: str, added_by: int) -> bool:
    """Add a user to a project with specified role"""
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role. Must be one of: {VALID_ROLES}")

    try:
        await execute(
            """
            INSERT INTO project_members (project_id, user_id, role, added_by)
            VALUES ($1, $2, $3, $4)
            """,
            project_id, user_id, role, added_by
        )
        return True

    except asyncpg.UniqueViolationError:
        raise ValueError("User is already a member of this project")


async def remove_project_member(project_id: int, user_id: int) -> bool:
    """Remove a user from a project"""
    async with get_transaction() as conn:
        # Check if this is the last admin
        other_admins = await conn.fetchval(
            """
            SELECT COUNT(*) FROM project_members 
            WHERE project_id = $1 AND role = 'admin' AND user_id != $2
            """,
            project_id, user_id
        )

        # Check if user being removed is an admin
        user_role = await conn.fetchval(
            """
            SELECT role FROM project_members 
            WHERE project_id = $1 AND user_id = $2
            """,
            project_id, user_id
        )

        if user_role == "admin" and other_admins == 0:
            raise ValueError("Cannot remove the last admin from the project")

        result = await conn.execute(
            """
            DELETE FROM project_members 
            WHERE project_id = $1 AND user_id = $2
            """,
            project_id, user_id
        )
        return "DELETE" in result


async def update_member_role(project_id: int, user_id: int, new_role: str) -> bool:
    """Update a member's role in a project"""
    if new_role not in VALID_ROLES:
        raise ValueError(f"Invalid role. Must be one of: {VALID_ROLES}")

    async with get_transaction() as conn:
        # Check if demoting last admin
        current_role = await conn.fetchval(
            """
            SELECT role FROM project_members 
            WHERE project_id = $1 AND user_id = $2
            """,
            project_id, user_id
        )

        if not current_role:
            return False

        if current_role == "admin" and new_role != "admin":
            # Check if there's another admin
            other_admins = await conn.fetchval(
                """
                SELECT COUNT(*) FROM project_members 
                WHERE project_id = $1 AND role = 'admin' AND user_id != $2
                """,
                project_id, user_id
            )

            if other_admins == 0:
                raise ValueError("Cannot demote the last admin")

        result = await conn.execute(
            """
            UPDATE project_members 
            SET role = $1
            WHERE project_id = $2 AND user_id = $3
            """,
            new_role, project_id, user_id
        )
        return "UPDATE" in result


async def get_project_members(project_id: int) -> List[Dict]:
    """Get all members of a project"""
    rows = await fetch(
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
        WHERE pm.project_id = $1
        ORDER BY pm.role DESC, u.username
        """,
        project_id
    )
    members = []
    for row in rows:
        member = dict(row)
        # Convert datetime to ISO string for Pydantic compatibility
        if member.get("added_at") and hasattr(member["added_at"], "isoformat"):
            member["added_at"] = member["added_at"].isoformat()
        members.append(member)
    return members


async def get_user_role(project_id: int, user_id: int) -> Optional[str]:
    """Get a user's role in a project"""
    return await fetchval(
        """
        SELECT role FROM project_members 
        WHERE project_id = $1 AND user_id = $2
        """,
        project_id, user_id
    )


async def user_has_access(project_id: int, user_id: int, min_role: str = "read") -> bool:
    """
    Check if user has at least the specified role level.
    Role hierarchy: admin > write > read
    """
    role = await get_user_role(project_id, user_id)
    if not role:
        return False

    role_levels = {"read": 1, "write": 2, "admin": 3}
    return role_levels.get(role, 0) >= role_levels.get(min_role, 0)
