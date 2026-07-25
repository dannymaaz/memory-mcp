from __future__ import annotations

import pytest

from persistent_memory_mcp.authorization import (
    WorkspaceCapability,
    WorkspaceMembership,
    WorkspaceRole,
    capabilities_for_role,
    require_capability,
    role_allows,
    validate_role_assignment,
)


def membership(role: WorkspaceRole, *, status: str = "active") -> WorkspaceMembership:
    return WorkspaceMembership(
        workspace_id="workspace-1",
        user_id=f"user-{role.value}",
        role=role,
        status=status,
    )


def test_role_capabilities_are_explicit() -> None:
    assert capabilities_for_role(WorkspaceRole.OWNER) == frozenset(WorkspaceCapability)
    assert role_allows(WorkspaceRole.ADMIN, WorkspaceCapability.ADMINISTER)
    assert role_allows(WorkspaceRole.MEMBER, WorkspaceCapability.WRITE)
    assert role_allows(WorkspaceRole.READER, WorkspaceCapability.READ)
    assert not role_allows(WorkspaceRole.READER, WorkspaceCapability.WRITE)


def test_reader_cannot_write() -> None:
    with pytest.raises(PermissionError, match="does not allow 'write'"):
        require_capability(membership(WorkspaceRole.READER), WorkspaceCapability.WRITE)


def test_member_cannot_manage_members() -> None:
    with pytest.raises(PermissionError, match="manage_members"):
        require_capability(
            membership(WorkspaceRole.MEMBER),
            WorkspaceCapability.MANAGE_MEMBERS,
        )


def test_admin_cannot_transfer_ownership() -> None:
    with pytest.raises(PermissionError, match="ownership transfer"):
        validate_role_assignment(
            membership(WorkspaceRole.ADMIN),
            target_role=WorkspaceRole.OWNER,
        )


def test_admin_cannot_grant_admin_role() -> None:
    with pytest.raises(PermissionError, match="cannot grant the admin role"):
        validate_role_assignment(
            membership(WorkspaceRole.ADMIN),
            target_role=WorkspaceRole.ADMIN,
        )


def test_owner_can_assign_non_owner_roles() -> None:
    actor = membership(WorkspaceRole.OWNER)
    assert validate_role_assignment(actor, target_role=WorkspaceRole.ADMIN) is WorkspaceRole.ADMIN
    assert validate_role_assignment(actor, target_role=WorkspaceRole.MEMBER) is WorkspaceRole.MEMBER
    assert validate_role_assignment(actor, target_role=WorkspaceRole.READER) is WorkspaceRole.READER


def test_inactive_membership_is_rejected() -> None:
    with pytest.raises(PermissionError, match="not active"):
        require_capability(
            membership(WorkspaceRole.MEMBER, status="suspended"),
            WorkspaceCapability.READ,
        )


def test_membership_record_normalization() -> None:
    result = WorkspaceMembership.from_record(
        {
            "workspace_id": "workspace-2",
            "user_id": "user-2",
            "role": "reader",
        }
    )
    assert result.workspace_id == "workspace-2"
    assert result.user_id == "user-2"
    assert result.role is WorkspaceRole.READER
    assert result.status == "active"
