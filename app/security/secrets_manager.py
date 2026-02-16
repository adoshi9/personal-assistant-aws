"""AWS Secrets Manager integration."""

import json
from functools import lru_cache
from typing import Any, Dict, Optional

import boto3
import structlog
from botocore.exceptions import ClientError

from app.config import get_settings

logger = structlog.get_logger(__name__)


class SecretsManager:
    """Manage secrets using AWS Secrets Manager."""

    def __init__(self, region: Optional[str] = None, prefix: Optional[str] = None):
        """Initialize SecretsManager.

        Args:
            region: AWS region (defaults to settings)
            prefix: Secret name prefix (defaults to settings)
        """
        settings = get_settings()
        self.region = region or settings.aws_region
        self.prefix = prefix or settings.aws_secrets_prefix
        self.client = boto3.client("secretsmanager", region_name=self.region)
        self._cache: Dict[str, Any] = {}

    def _get_full_secret_name(self, secret_name: str) -> str:
        """Get full secret name with prefix.

        Args:
            secret_name: Base secret name

        Returns:
            Full secret name with prefix
        """
        if secret_name.startswith(self.prefix):
            return secret_name
        return f"{self.prefix}{secret_name}"

    async def get_secret(self, secret_name: str, use_cache: bool = True) -> str:
        """Get secret value from AWS Secrets Manager.

        Args:
            secret_name: Name of the secret (without prefix)
            use_cache: Whether to use cached value

        Returns:
            Secret value as string

        Raises:
            ValueError: If secret not found or cannot be retrieved
        """
        full_name = self._get_full_secret_name(secret_name)

        # Check cache
        if use_cache and full_name in self._cache:
            logger.debug("Retrieved secret from cache", secret_name=full_name)
            return self._cache[full_name]

        try:
            logger.info("Retrieving secret from AWS Secrets Manager", secret_name=full_name)
            response = self.client.get_secret_value(SecretId=full_name)

            # Handle both string and binary secrets
            if "SecretString" in response:
                secret_value = response["SecretString"]
            else:
                secret_value = response["SecretBinary"].decode("utf-8")

            # Cache the value
            self._cache[full_name] = secret_value
            logger.info("Successfully retrieved secret", secret_name=full_name)
            return secret_value

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(
                "Failed to retrieve secret",
                secret_name=full_name,
                error_code=error_code,
                error=str(e),
            )

            if error_code == "ResourceNotFoundException":
                raise ValueError(f"Secret not found: {full_name}") from e
            elif error_code == "InvalidRequestException":
                raise ValueError(f"Invalid request for secret: {full_name}") from e
            elif error_code == "InvalidParameterException":
                raise ValueError(f"Invalid parameter for secret: {full_name}") from e
            else:
                raise ValueError(f"Failed to retrieve secret {full_name}: {e}") from e

    async def get_secret_json(self, secret_name: str, use_cache: bool = True) -> Dict[str, Any]:
        """Get secret value as JSON object.

        Args:
            secret_name: Name of the secret (without prefix)
            use_cache: Whether to use cached value

        Returns:
            Secret value parsed as JSON

        Raises:
            ValueError: If secret not found, cannot be retrieved, or is not valid JSON
        """
        secret_value = await self.get_secret(secret_name, use_cache=use_cache)
        try:
            return json.loads(secret_value)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse secret as JSON", secret_name=secret_name, error=str(e))
            raise ValueError(f"Secret {secret_name} is not valid JSON: {e}") from e

    async def create_secret(
        self, secret_name: str, secret_value: str, description: Optional[str] = None
    ) -> None:
        """Create a new secret in AWS Secrets Manager.

        Args:
            secret_name: Name of the secret (without prefix)
            secret_value: Value of the secret
            description: Optional description

        Raises:
            ValueError: If secret creation fails
        """
        full_name = self._get_full_secret_name(secret_name)

        try:
            logger.info("Creating secret in AWS Secrets Manager", secret_name=full_name)
            self.client.create_secret(
                Name=full_name, SecretString=secret_value, Description=description or ""
            )
            logger.info("Successfully created secret", secret_name=full_name)

            # Invalidate cache
            if full_name in self._cache:
                del self._cache[full_name]

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(
                "Failed to create secret",
                secret_name=full_name,
                error_code=error_code,
                error=str(e),
            )

            if error_code == "ResourceExistsException":
                raise ValueError(f"Secret already exists: {full_name}") from e
            else:
                raise ValueError(f"Failed to create secret {full_name}: {e}") from e

    async def update_secret(self, secret_name: str, secret_value: str) -> None:
        """Update an existing secret in AWS Secrets Manager.

        Args:
            secret_name: Name of the secret (without prefix)
            secret_value: New value of the secret

        Raises:
            ValueError: If secret update fails
        """
        full_name = self._get_full_secret_name(secret_name)

        try:
            logger.info("Updating secret in AWS Secrets Manager", secret_name=full_name)
            self.client.update_secret(SecretId=full_name, SecretString=secret_value)
            logger.info("Successfully updated secret", secret_name=full_name)

            # Invalidate cache
            if full_name in self._cache:
                del self._cache[full_name]

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(
                "Failed to update secret",
                secret_name=full_name,
                error_code=error_code,
                error=str(e),
            )
            raise ValueError(f"Failed to update secret {full_name}: {e}") from e

    def clear_cache(self) -> None:
        """Clear the secrets cache."""
        logger.info("Clearing secrets cache")
        self._cache.clear()


@lru_cache
def get_secrets_manager() -> SecretsManager:
    """Get cached SecretsManager instance."""
    return SecretsManager()
