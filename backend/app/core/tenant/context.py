"""
Multi-tenant context using contextvars.
Inspired by LibreChat's AsyncLocalStorage pattern, rewritten for Python.
"""
from contextvars import ContextVar
from typing import Optional
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

# Context variables for the current request
_current_tenant_id: ContextVar[Optional[UUID]] = ContextVar("current_tenant_id", default=None)
_current_user_id: ContextVar[Optional[UUID]] = ContextVar("current_user_id", default=None)
_current_user_role: ContextVar[Optional[str]] = ContextVar("current_user_role", default=None)
_current_user_email: ContextVar[Optional[str]] = ContextVar("current_user_email", default=None)
_is_system_context: ContextVar[bool] = ContextVar("is_system_context", default=False)


class TenantContext:
    """Context manager for setting tenant scope."""

    def __init__(
        self,
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
        user_role: Optional[str] = None,
        user_email: Optional[str] = None,
    ):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.user_role = user_role
        self.user_email = user_email
        self._tokens = []

    def __enter__(self):
        self._tokens.append(_current_tenant_id.set(self.tenant_id))
        if self.user_id:
            self._tokens.append(_current_user_id.set(self.user_id))
        if self.user_role:
            self._tokens.append(_current_user_role.set(self.user_role))
        if self.user_email:
            self._tokens.append(_current_user_email.set(self.user_email))
        return self

    def __exit__(self, *args):
        for token in reversed(self._tokens):
            token.var.reset(token)
        self._tokens.clear()


def get_current_tenant_id() -> Optional[UUID]:
    """Get current tenant ID from context."""
    return _current_tenant_id.get()


def get_current_user_id() -> Optional[UUID]:
    """Get current user ID from context."""
    return _current_user_id.get()


def get_current_user_role() -> Optional[str]:
    """Get current user role from context."""
    return _current_user_role.get()


def get_current_user_email() -> Optional[str]:
    """Get current user email from context."""
    return _current_user_email.get()


def require_tenant_id() -> UUID:
    """Get current tenant ID or raise exception."""
    tid = _current_tenant_id.get()
    if tid is None and not _is_system_context.get():
        raise RuntimeError(
            "No tenant context found. Query rejected (TENANT_ISOLATION_STRICT)."
        )
    return tid


class SystemContext:
    """Context manager for system operations (cross-tenant)."""

    def __enter__(self):
        self._token = _is_system_context.set(True)
        return self

    def __exit__(self, *args):
        _is_system_context.reset(self._token)


def is_system_context() -> bool:
    """Check if we're in system context."""
    return _is_system_context.get()
