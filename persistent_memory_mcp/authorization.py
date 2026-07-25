"""Workspace membership roles and centralized authorization checks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class WorkspaceRole(StrEnum):
    """Supported workspace membership roles."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    READER = "reader"


class WorkspaceCapability(StrEnum):
    """Capabilities enforced by the workspace authorization layer."""

    READ = "read"
    WRITE = "write"
    MANAGE_MEMBERS = "manage_members"
    ADMINISTER = "administer"
    TRANSFER_OWNERSHIP = "transfer_ownership"


_ROLE_CAPABILITIES: dict[WorkspaceRole, frozenset[WorkspaceCapability]] = {
    WorkspaceRole.OWNER: frozenset(WorkspaceCapability),
    WorkspaceRole.ADMIN: frozenset(
        {
            WorkspaceCapability.READ,
            WorkspaceCapability.WRITE,
            WorkspaceCapability.MANAGE_MEMBERS,
            WorkspaceCapability.ADMINISTER,
        }
    ),
    WorkspaceRole.MEMBER: frozenset(
        {
            WorkspaceCapability.READ,
            WorkspaceCapability.WRITE,
        }
    ),
    WorkspaceRole.READER: frozenset({WorkspaceCapability.READ}),
}


@dataclass(frozen=True)
class WorkspaceMembership:
    """Normalized workspace membership record."""

    workspace_id: str
    user_id: str
    role: WorkspaceRole
    status: str = "active"

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "WorkspaceMembership":
        return cls(
            workspace_id=str(record["workspace_id"]),
            user_id=str(record["user_id"]),
            role=WorkspaceRole(str(record["role"])),
            status=str(record.get("status", "active")),
        )


def capabilities_for_role(role: WorkspaceRole | str) -> frozenset[WorkspaceCapability]:
    """Return the immutable capability set for a role."""

    return _ROLE_CAPABILITIES[WorkspaceRole(role)]


def role_allows(
    role: WorkspaceRole | str,
    capability: WorkspaceCapability | str,
) -> bool:
    """Return whether a role grants a capability."""

    return WorkspaceCapability(capability) in capabilities_for_role(role)


def require_capability(
    membership: WorkspaceMembership,
    capability: WorkspaceCapability | str,
) -> None:
    """Reject inactive memberships and insufficient roles."""

    requested = WorkspaceCapability(capability)
    if membership.status != "active":
        raise PermissionError("Workspace membership is not active")
    if not role_allows(membership.role, requested):
        raise PermissionError(
            f"Workspace role '{membership.role.value}' does not allow '{requested.value}'"
        )


def validate_role_assignment(
    actor: WorkspaceMembership,
    *,
    target_role: WorkspaceRole | str,
) -> WorkspaceRole:
    """Validate membership management without allowing ownership transfer."""

    role = WorkspaceRole(target_role)
    require_capability(actor, WorkspaceCapability.MANAGE_MEMBERS)
    if role is WorkspaceRole.OWNER:
        raise PermissionError("Workspace ownership transfer is not supported")
    if actor.role is WorkspaceRole.ADMIN and role is WorkspaceRole.ADMIN:
        raise PermissionError("Admins cannot grant the admin role")
    return role
