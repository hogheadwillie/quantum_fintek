from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.identity.models import Organization, User
from app.identity.normalization import normalize_email


class TenantScopedUserRepository:
    """Repository for user lookups constrained by tenant identity."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_identity(
        self,
        *,
        organization_slug: str,
        email: str,
    ) -> User | None:
        """Return one user scoped to an organization slug and email address."""
        statement = (
            select(User)
            .join(User.organization)
            .where(
                Organization.slug == organization_slug,
                User.email == normalize_email(email),
            )
        )
        return self._session.scalar(statement)

    def get_by_id(self, user_id: str | UUID) -> User | None:
        """Return a user by UUID string, or None for an invalid identifier."""
        try:
            parsed_id = user_id if isinstance(user_id, UUID) else UUID(user_id)
        except ValueError:
            return None
        return self._session.get(User, parsed_id)

    def list_for_organization(self, organization_id: UUID) -> list[User]:
        """Return users belonging to one organization in stable email order."""
        statement = (
            select(User)
            .where(User.organization_id == organization_id)
            .order_by(User.email)
        )
        return list(self._session.scalars(statement))


def get_user_by_identity(
    session: Session,
    *,
    organization_slug: str,
    email: str,
) -> User | None:
    """Return one user scoped to an organization slug and email address."""
    return TenantScopedUserRepository(session).get_by_identity(
        organization_slug=organization_slug,
        email=email,
    )


def get_user_by_id(session: Session, user_id: str | UUID) -> User | None:
    """Return a user by UUID string, or None for an invalid identifier."""
    return TenantScopedUserRepository(session).get_by_id(user_id)
