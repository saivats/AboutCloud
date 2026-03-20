"""
API __init__
"""

from .auth import AuthManager, get_auth_manager, setup_demo_keys

__all__ = [
    "AuthManager",
    "get_auth_manager",
    "setup_demo_keys",
]
