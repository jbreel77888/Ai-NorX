"""
Cloudflare R2 Storage Client - for file uploads.
Uses S3-compatible API.
"""
import logging
import asyncio
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class R2Storage:
    """Cloudflare R2 storage client (S3-compatible)."""

    def __init__(self):
        self.bucket_name = settings.R2_BUCKET_NAME
        self.endpoint_url = settings.R2_ENDPOINT
        self._client = None

    @property
    def client(self):
        """Lazy-initialize the S3 client."""
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                region_name="auto",
                config=Config(
                    signature_version="s3v4",
                    retries={"max_attempts": 3, "mode": "standard"},
                ),
            )
        return self._client

    async def upload_file(
        self,
        file_data: bytes,
        file_name: str,
        content_type: str,
        tenant_id: UUID,
        user_id: UUID,
    ) -> dict:
        """Upload a file to R2."""
        object_key = f"tenants/{tenant_id}/users/{user_id}/{uuid4().hex}_{file_name}"

        try:
            await asyncio.to_thread(
                self.client.put_object,
                Bucket=self.bucket_name,
                Key=object_key,
                Body=file_data,
                ContentType=content_type,
                Metadata={
                    "tenant_id": str(tenant_id),
                    "user_id": str(user_id),
                    "original_name": file_name,
                    "uploaded_at": datetime.utcnow().isoformat(),
                },
            )

            public_url = f"{settings.R2_PUBLIC_URL}/{object_key}" if settings.R2_PUBLIC_URL else None
            presigned_url = await asyncio.to_thread(
                self.client.generate_presigned_url,
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": object_key},
                ExpiresIn=7 * 24 * 3600,
            )

            return {
                "key": object_key,
                "url": public_url or presigned_url,
                "presigned_url": presigned_url,
                "size": len(file_data),
                "content_type": content_type,
                "original_name": file_name,
            }

        except ClientError as e:
            logger.error(f"R2 upload failed: {e}")
            raise Exception(f"File upload failed: {e}")

    async def download_file(self, key: str) -> bytes:
        """Download a file from R2."""
        try:
            response = await asyncio.to_thread(
                self.client.get_object,
                Bucket=self.bucket_name,
                Key=key,
            )
            return response["Body"].read()
        except ClientError as e:
            logger.error(f"R2 download failed: {e}")
            raise Exception(f"File download failed: {e}")

    async def delete_file(self, key: str) -> bool:
        """Delete a file from R2."""
        try:
            await asyncio.to_thread(
                self.client.delete_object,
                Bucket=self.bucket_name,
                Key=key,
            )
            return True
        except ClientError as e:
            logger.error(f"R2 delete failed: {e}")
            return False


r2_storage = R2Storage()
