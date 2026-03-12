"""Azure Key Vault client using DefaultAzureCredential (Managed Identity in prod)."""

from __future__ import annotations

from src.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)
_client = None


def _get_client() -> object | None:
    global _client
    if _client is not None:
        return _client
    if not settings.azure_keyvault_url:
        logger.debug("keyvault_disabled", reason="AZURE_KEYVAULT_URL not set")
        return None
    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
        credential = DefaultAzureCredential()
        _client = SecretClient(vault_url=settings.azure_keyvault_url, credential=credential)
        return _client
    except ImportError:
        logger.warning("keyvault_sdk_missing", msg="azure-keyvault-secrets not installed")
        return None


def get_secret(name: str) -> str | None:
    """Retrieve a secret from Azure Key Vault. Returns None in dev mode."""
    client = _get_client()
    if client is None:
        return None
    try:
        secret = client.get_secret(name)  # type: ignore[union-attr]
        return secret.value
    except Exception as exc:
        logger.error("keyvault_error", secret=name, error=str(exc))
        return None
