"""Pydantic models for Auth module request/response validation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Request Models ────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str
    entity_code: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


class CreateUserRequest(BaseModel):
    username: str = ""
    display_name: str = ""
    email: str = ""
    phone: str = ""
    department: str = ""
    position: str = ""
    user_type: str = "admin"
    status: str = "active"
    linked_employee_id: str = ""
    linked_employee_number: str = ""
    language_preference: str = "ja"
    initial_password: str = ""
    role_ids: List[str] = Field(default_factory=list)


class UpdateUserRequest(BaseModel):
    username: Optional[str] = None
    display_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    user_type: Optional[str] = None
    status: Optional[str] = None
    linked_employee_id: Optional[str] = None
    linked_employee_number: Optional[str] = None
    language_preference: Optional[str] = None
    role_ids: Optional[List[str]] = None
    account_locked: Optional[bool] = None


class UpdateRolePermissionsRequest(BaseModel):
    permission_ids: List[str]


# ── Response Helpers ──────────────────────────────────────────────────────

def success_response(data: Any = None) -> dict:
    result: dict = {"success": True}
    if data is not None:
        result["data"] = data
    return result


def error_response(message: str, errors: Optional[List[str]] = None) -> dict:
    result: dict = {"success": False, "error": message}
    if errors:
        result["errors"] = errors
    return result


def paginated_response(data: list, page: int, page_size: int, total: int,
                       total_all: Optional[int] = None, filtered: Optional[bool] = None) -> dict:
    pagination: dict = {"page": page, "page_size": page_size, "total": total}
    if total_all is not None:
        pagination["total_all"] = total_all
    if filtered is not None:
        pagination["filtered"] = filtered
    return {"success": True, "data": data, "pagination": pagination}
