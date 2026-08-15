"""Public collector catalog.

Collectors themselves live in ``services.collectors``. This module is the
plug-in surface for the provider registry so scoring never imports HTTP clients.
"""
from services.providers.registry import PUBLIC_PROVIDERS

__all__ = ["PUBLIC_PROVIDERS"]
