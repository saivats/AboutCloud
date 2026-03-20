"""
Authentication & Authorization

API key-based auth with tenant scoping.
Each API key belongs to a tenant — requests are automatically scoped.
"""

import hashlib
import secrets
from typing import Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class APIKey:
    """Represents a registered API key."""
    key_hash: str         # SHA-256 hash of the key
    tenant_id: str        # Tenant this key belongs to
    name: str             # Human-readable name
    created_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True
    permissions: list = field(default_factory=lambda: ["read", "write"])


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class AuthorizationError(Exception):
    """Raised when authorization fails (e.g., cross-tenant access)."""
    pass


class AuthManager:
    """
    Manages API key authentication and tenant authorization.

    Usage:
        >>> auth = AuthManager()
        >>> key = auth.create_api_key("acme-corp", "prod-key")
        >>> tenant_id = auth.authenticate(key)
        >>> auth.authorize(tenant_id, requested_tenant="acme-corp")
    """

    def __init__(self):
        """Initialize auth manager with empty key store."""
        # key_hash -> APIKey
        self._keys: Dict[str, APIKey] = {}

    @staticmethod
    def _hash_key(raw_key: str) -> str:
        """Hash an API key for secure storage."""
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def create_api_key(
        self,
        tenant_id: str,
        name: str = "default",
        permissions: Optional[list] = None,
    ) -> str:
        """
        Create a new API key for a tenant.

        Args:
            tenant_id: Tenant this key belongs to
            name: Human-readable name for the key
            permissions: List of permissions (default: ["read", "write"])

        Returns:
            str: The raw API key (only shown once!)
        """
        raw_key = f"ac_{secrets.token_urlsafe(32)}"
        key_hash = self._hash_key(raw_key)

        api_key = APIKey(
            key_hash=key_hash,
            tenant_id=tenant_id,
            name=name,
            permissions=permissions or ["read", "write"],
        )

        self._keys[key_hash] = api_key
        return raw_key

    def authenticate(self, raw_key: str) -> str:
        """
        Authenticate a request using an API key.

        Args:
            raw_key: The raw API key from the request header

        Returns:
            str: The tenant_id associated with this key

        Raises:
            AuthenticationError: If key is invalid or inactive
        """
        if not raw_key:
            raise AuthenticationError("No API key provided")

        key_hash = self._hash_key(raw_key)
        api_key = self._keys.get(key_hash)

        if api_key is None:
            raise AuthenticationError("Invalid API key")

        if not api_key.is_active:
            raise AuthenticationError("API key is deactivated")

        return api_key.tenant_id

    def authorize(
        self,
        authenticated_tenant: str,
        requested_tenant: str,
        required_permission: str = "read",
    ) -> None:
        """
        Check if an authenticated tenant can access the requested resource.

        Args:
            authenticated_tenant: Tenant from authentication
            requested_tenant: Tenant being accessed in the request
            required_permission: Permission needed ("read" or "write")

        Raises:
            AuthorizationError: If access is denied
        """
        if authenticated_tenant != requested_tenant:
            raise AuthorizationError(
                f"Tenant '{authenticated_tenant}' cannot access "
                f"data belonging to tenant '{requested_tenant}'"
            )

    def revoke_key(self, raw_key: str) -> bool:
        """
        Deactivate an API key.

        Args:
            raw_key: The raw API key to revoke

        Returns:
            bool: True if key was found and revoked
        """
        key_hash = self._hash_key(raw_key)
        api_key = self._keys.get(key_hash)

        if api_key is None:
            return False

        api_key.is_active = False
        return True

    def list_keys(self, tenant_id: Optional[str] = None) -> list:
        """List registered keys (without raw values)."""
        keys = self._keys.values()
        if tenant_id:
            keys = [k for k in keys if k.tenant_id == tenant_id]

        return [
            {
                "name": k.name,
                "tenant_id": k.tenant_id,
                "created_at": k.created_at.isoformat(),
                "is_active": k.is_active,
                "permissions": k.permissions,
            }
            for k in keys
        ]


# Global auth manager instance
_auth_manager = AuthManager()


def get_auth_manager() -> AuthManager:
    """Get the global auth manager."""
    return _auth_manager


def setup_demo_keys() -> Dict[str, str]:
    """
    Create demo API keys for development/testing.

    Returns:
        Dict of tenant_id -> raw API key
    """
    mgr = get_auth_manager()
    keys = {}

    keys["demo-tenant"] = mgr.create_api_key("demo-tenant", "demo-key")
    keys["benchmark-tenant"] = mgr.create_api_key("benchmark-tenant", "benchmark-key")

    return keys
