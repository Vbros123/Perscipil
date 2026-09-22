"""Central tenant authorization. All lookups include the tenant identity."""

from fastapi import HTTPException
from sqlalchemy import select
from models.organizations import (
    Membership,
    Organization,
    OrganizationResource,
    OrganizationAudit,
)

PERMISSIONS = {
    "owner": {"read", "write", "members", "keys", "owner"},
    "admin": {"read", "write", "members", "keys"},
    "member": {"read", "write"},
}


def authorize(db, organization_id, user, permission="read"):
    member = db.get(Membership, (organization_id, user.id))
    if not member or not member.active:
        raise HTTPException(404, "Workspace not found")
    if permission not in PERMISSIONS.get(member.role, set()):
        raise HTTPException(403, "Workspace permission denied")
    return member


def locked_organization(db, organization_id):
    return db.scalar(
        select(Organization).where(Organization.id == organization_id).with_for_update()
    )


def resource(db, organization_id, resource_id, kind=None):
    row = db.scalar(
        select(OrganizationResource).where(
            OrganizationResource.organization_id == organization_id,
            OrganizationResource.id == resource_id,
        )
    )
    if row is None or (kind and row.kind != kind):
        raise HTTPException(404, "Resource not found")
    return row


def audit(db, organization_id, user_id, action, resource_id=None):
    db.add(
        OrganizationAudit(
            organization_id=organization_id,
            actor_id=user_id,
            action=action,
            resource_id=resource_id,
        )
    )
