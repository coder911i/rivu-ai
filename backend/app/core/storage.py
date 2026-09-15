"""S3-compatible object storage client (MinIO/AWS S3)."""

import hashlib
import io
from typing import Optional, BinaryIO
import aioboto3
import boto3
from botocore.exceptions import ClientError
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


def _get_boto_config():
    return {
        "endpoint_url": settings.S3_ENDPOINT if not settings.S3_USE_SSL else None,
        "aws_access_key_id": settings.S3_ACCESS_KEY,
        "aws_secret_access_key": settings.S3_SECRET_KEY,
        "region_name": settings.S3_REGION,
    }


class StorageClient:
    """Async S3-compatible storage client."""

    def __init__(self):
        self._session = aioboto3.Session()
        self.bucket = settings.S3_BUCKET

    async def upload_file(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: dict | None = None,
    ) -> str:
        """Upload file to object storage. Returns the storage key."""
        async with self._session.client("s3", **_get_boto_config()) as s3:
            try:
                await s3.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=data,
                    ContentType=content_type,
                    Metadata=metadata or {},
                )
                logger.info("storage_upload", key=key, content_type=content_type)
                return key
            except ClientError as e:
                logger.error("storage_upload_failed", key=key, error=str(e))
                raise

    async def download_file(self, key: str) -> bytes:
        """Download file from object storage."""
        async with self._session.client("s3", **_get_boto_config()) as s3:
            try:
                response = await s3.get_object(Bucket=self.bucket, Key=key)
                data = await response["Body"].read()
                logger.info("storage_download", key=key, size=len(data))
                return data
            except ClientError as e:
                logger.error("storage_download_failed", key=key, error=str(e))
                raise

    async def get_download_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned download URL."""
        async with self._session.client("s3", **_get_boto_config()) as s3:
            url = await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            )
            return url

    async def delete_file(self, key: str) -> None:
        """Delete a file from storage."""
        async with self._session.client("s3", **_get_boto_config()) as s3:
            await s3.delete_object(Bucket=self.bucket, Key=key)
            logger.info("storage_delete", key=key)

    async def file_exists(self, key: str) -> bool:
        """Check if a file exists in storage."""
        async with self._session.client("s3", **_get_boto_config()) as s3:
            try:
                await s3.head_object(Bucket=self.bucket, Key=key)
                return True
            except ClientError:
                return False

    async def ensure_bucket(self) -> None:
        """Create the bucket if it doesn't exist."""
        async with self._session.client("s3", **_get_boto_config()) as s3:
            try:
                await s3.head_bucket(Bucket=self.bucket)
            except ClientError:
                await s3.create_bucket(Bucket=self.bucket)
                logger.info("storage_bucket_created", bucket=self.bucket)


def compute_checksum(data: bytes) -> str:
    """SHA-256 checksum of file data."""
    return hashlib.sha256(data).hexdigest()


def build_storage_key(
    org_id: str,
    project_id: str,
    dataset_id: str,
    version: int,
    filename: str,
) -> str:
    """Build a deterministic, organized S3 key."""
    return f"orgs/{org_id}/projects/{project_id}/datasets/{dataset_id}/v{version}/{filename}"


# Singleton
_storage_client: StorageClient | None = None


def get_storage() -> StorageClient:
    global _storage_client
    if _storage_client is None:
        _storage_client = StorageClient()
    return _storage_client
