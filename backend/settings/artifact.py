"""Settings for S3-compatible workflow artifact storage."""

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from settings.base import BaseSettings


class ArtifactSettings(BaseSettings):
    """Artifact storage, quota, retention, and signed-link configuration."""

    model_config = SettingsConfigDict(env_prefix="artifact_")

    endpoint: str = Field(default="minio:9000", title="Internal S3 endpoint")
    public_endpoint: str = Field(
        default="localhost:9000", title="Browser-reachable S3 endpoint"
    )
    access_key: str = Field(default="graphai", title="S3 access key")
    secret_key: str = Field(default="graphai-local-secret", title="S3 secret key")
    secure: bool = Field(default=False, title="Use HTTPS for internal S3 requests")
    public_secure: bool = Field(
        default=False, title="Use HTTPS in browser-facing signed URLs"
    )
    bucket: str = Field(default="graph-ai-artifacts", title="Artifact bucket")
    max_upload_bytes: int = Field(
        default=20 * 1024 * 1024,
        ge=1,
        title="Maximum bytes accepted by one upload",
    )
    max_user_bytes: int = Field(
        default=500 * 1024 * 1024,
        ge=0,
        title="Maximum stored bytes per user; 0 disables the quota",
    )
    retention_days: int = Field(
        default=30,
        ge=0,
        title="Days before an artifact expires; 0 retains indefinitely",
    )
    signed_url_expire_seconds: int = Field(
        default=300,
        ge=30,
        le=86_400,
        title="Lifetime of a signed artifact download URL",
    )


artifact_settings = ArtifactSettings()
