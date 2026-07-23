from sqlalchemy import select
from sqlalchemy.orm import Session

from app.identity.models import Organization, User


def get_user_by_identity(
    session: Session,
    *,
    organization_slug: str,
    email: str,
) -> User | None:
    """Return one user scoped to an organization slug and email address."""
    statement = (
        select(User)
        .join(User.organization)
        .where(Organization.slug == organization_slug, User.email == email.lower())
    )
    return session.scalar(statement)


def get_user_by_id(session: Session, user_id: str) -> User | None:
    """Return a user by UUID string, or None for an invalid identifier."""
    from uuid import UUID

    try:
        parsed_id = UUID(user_id)
    except ValueError:
        return None
    return session.get(User, parsed_id)
