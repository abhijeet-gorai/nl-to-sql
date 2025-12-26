"""
Projects Router
FastAPI router for project management and member endpoints
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Optional, List

import projects
import auth
from dependencies import (
    get_current_user,
    require_read_access,
    require_admin_access,
)

router = APIRouter(prefix="/projects", tags=["Projects"])


# ============================================
# Request/Response Models
# ============================================


class CreateProjectRequest(BaseModel):
    """Project creation request"""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class UpdateProjectRequest(BaseModel):
    """Project update request"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class ProjectResponse(BaseModel):
    """Project response"""

    id: int
    name: str
    description: Optional[str]
    created_by: int
    role: Optional[str] = None
    member_count: Optional[int] = None


class AddMemberRequest(BaseModel):
    """Add member request"""

    username_or_email: str
    role: str = Field(..., pattern="^(read|write|admin)$")


class UpdateMemberRoleRequest(BaseModel):
    """Update member role request"""

    role: str = Field(..., pattern="^(read|write|admin)$")


class MemberResponse(BaseModel):
    """Project member response"""

    user_id: int
    username: str
    full_name: str
    email: str
    role: str
    added_at: Optional[str] = None


# ============================================
# Project CRUD Endpoints
# ============================================


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: CreateProjectRequest, current_user: dict = Depends(get_current_user)
):
    """
    Create a new project. The creator is automatically added as admin.

    - **name**: Unique project name
    - **description**: Optional project description
    """
    try:
        project_id = await projects.create_project(
            name=request.name,
            description=request.description,
            created_by=current_user["id"],
        )

        return ProjectResponse(
            id=project_id,
            name=request.name,
            description=request.description,
            created_by=current_user["id"],
            role="admin",
            member_count=1,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=List[ProjectResponse])
async def list_projects(current_user: dict = Depends(get_current_user)):
    """
    List all projects the current user has access to.
    """
    user_projects = await projects.get_user_projects(current_user["id"])

    return [
        ProjectResponse(
            id=p["id"],
            name=p["name"],
            description=p.get("description"),
            created_by=p["created_by"],
            role=p.get("role"),
            member_count=p.get("member_count"),
        )
        for p in user_projects
    ]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, access: dict = Depends(require_read_access)):
    """
    Get project details. Requires at least read access.
    """
    project = access["project"]
    members = await projects.get_project_members(project_id)
    member_count = len(members)

    return ProjectResponse(
        id=project["id"],
        name=project["name"],
        description=project.get("description"),
        created_by=project["created_by"],
        role=access["role"],
        member_count=member_count,
    )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    request: UpdateProjectRequest,
    access: dict = Depends(require_admin_access),
):
    """
    Update project details. Requires admin access.
    """
    try:
        success = await projects.update_project(
            project_id=project_id, name=request.name, description=request.description
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update project",
            )

        # Get updated project
        project = await projects.get_project(project_id)
        members = await projects.get_project_members(project_id)
        member_count = len(members)

        return ProjectResponse(
            id=project["id"],
            name=project["name"],
            description=project.get("description"),
            created_by=project["created_by"],
            role=access["role"],
            member_count=member_count,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{project_id}")
async def delete_project(project_id: int, access: dict = Depends(require_admin_access)):
    """
    Delete a project and all associated resources. Requires admin access.

    **Warning**: This will permanently delete all connections, tables, and data
    associated with this project.
    """
    success = await projects.delete_project(project_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete project",
        )

    return {"status": "success", "message": "Project deleted successfully"}


# ============================================
# Member Management Endpoints
# ============================================


@router.get("/{project_id}/members", response_model=List[MemberResponse])
async def list_members(project_id: int, access: dict = Depends(require_read_access)):
    """
    List all members of a project. Requires at least read access.
    """
    members = await projects.get_project_members(project_id)

    return [
        MemberResponse(
            user_id=m["user_id"],
            username=m["username"],
            full_name=m["full_name"],
            email=m["email"],
            role=m["role"],
            added_at=m.get("added_at"),
        )
        for m in members
    ]


@router.post("/{project_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member(
    project_id: int,
    request: AddMemberRequest,
    access: dict = Depends(require_admin_access),
):
    """
    Add a user to the project. Requires admin access.

    - **username_or_email**: Username or email of the user to add
    - **role**: Role to assign (read, write, or admin)
    """
    # Find user by username or email
    user = await auth.get_user_by_username(request.username_or_email)
    if not user:
        user = await auth.get_user_by_email(request.username_or_email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    try:
        await projects.add_project_member(
            project_id=project_id,
            user_id=user["id"],
            role=request.role,
            added_by=access["user"]["id"],
        )

        return {
            "status": "success",
            "user_id": user["id"],
            "username": user["username"],
            "role": request.role,
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.put("/{project_id}/members/{user_id}")
async def update_member_role(
    project_id: int,
    user_id: int,
    request: UpdateMemberRoleRequest,
    access: dict = Depends(require_admin_access),
):
    """
    Update a member's role. Requires admin access.

    - **role**: New role (read, write, or admin)
    """
    try:
        success = await projects.update_member_role(
            project_id=project_id, user_id=user_id, new_role=request.role
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found in this project",
            )

        return {"status": "success", "user_id": user_id, "role": request.role}

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{project_id}/members/{user_id}")
async def remove_member(
    project_id: int, user_id: int, access: dict = Depends(require_admin_access)
):
    """
    Remove a member from the project. Requires admin access.

    Note: Cannot remove the last admin from a project.
    """
    try:
        success = await projects.remove_project_member(project_id=project_id, user_id=user_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found in this project",
            )

        return {"status": "success", "message": "Member removed successfully"}

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
