"""
S3 Storage Service

Handles resume PDF uploads, downloads, and pre-signed URL generation.
Compatible with AWS S3 and MinIO.
"""

import uuid
from typing import BinaryIO

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class StorageService:
    """S3-compatible storage service for resume PDFs and files."""

    def __init__(self) -> None:
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key.get_secret_value(),
            aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
            region_name=settings.s3_region,
        )
        self.bucket = settings.s3_bucket_name
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Create bucket if it doesn't exist."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            try:
                self.client.create_bucket(Bucket=self.bucket)
                logger.info("Created S3 bucket", bucket=self.bucket)
            except ClientError as e:
                logger.error("Failed to create bucket", error=str(e))

    def upload_pdf(
        self, file_data: BinaryIO, user_id: str, resume_id: str
    ) -> str:
        """
        Upload a PDF to S3.
        Returns the S3 key.
        """
        s3_key = f"resumes/{user_id}/{resume_id}/{uuid.uuid4().hex}.pdf"
        try:
            self.client.upload_fileobj(
                file_data,
                self.bucket,
                s3_key,
                ExtraArgs={"ContentType": "application/pdf"},
            )
            logger.info("PDF uploaded", key=s3_key)
            return s3_key
        except ClientError as e:
            logger.error("PDF upload failed", error=str(e))
            raise

    def upload_bytes(
        self, data: bytes, user_id: str, resume_id: str, filename: str = "resume.pdf"
    ) -> str:
        """Upload raw bytes to S3."""
        import io
        return self.upload_pdf(io.BytesIO(data), user_id, resume_id)

    def get_download_url(self, s3_key: str, expires_in: int = 3600) -> str:
        """Generate a pre-signed download URL."""
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": s3_key},
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error("URL generation failed", error=str(e))
            raise

    def delete_file(self, s3_key: str) -> None:
        """Delete a file from S3."""
        try:
            self.client.delete_object(Bucket=self.bucket, Key=s3_key)
            logger.info("File deleted", key=s3_key)
        except ClientError as e:
            logger.error("File deletion failed", error=str(e))
            raise
