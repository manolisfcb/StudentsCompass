import boto3
import os
import logging
from botocore.exceptions import ClientError
from io import BytesIO
import asyncio
from typing import Optional

LOGGER = logging.getLogger(__name__)

class S3Service:
    """Service for handling S3 file operations"""
    
    def __init__(self):
        self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.bucket_name = os.getenv("BUCKET_NAME")
        self.aws_region = os.getenv("AWS_REGION", "us-east-1")
        
        if not all([self.aws_access_key_id, self.aws_secret_access_key, self.bucket_name]):
            raise ValueError("AWS credentials or bucket name not configured. Check your .env file.")
        
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.aws_region
        )
    
    async def upload_file(self, file_bytes: bytes, file_name: str, content_type: str = "application/pdf") -> dict:
        """
        Upload a file to S3 bucket
        
        Args:
            file_bytes: File content as bytes
            file_name: Name of the file to store in S3
            content_type: MIME type of the file
            
        Returns:
            dict with file_key and file_url
        """
        try:
            loop = asyncio.get_event_loop()
            
            # Generate unique file key (you can customize this pattern)
            file_key = f"resumes/{file_name}"
            
            # Upload to S3 (run in executor to avoid blocking)
            def do_upload():
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=file_key,
                    Body=file_bytes,
                    ContentType=content_type
                )
                return file_key
            
            uploaded_key = await loop.run_in_executor(None, do_upload)
            
            # Generate URL
            file_url = f"https://{self.bucket_name}.s3.{self.aws_region}.amazonaws.com/{file_key}"
            
            LOGGER.info(f"File uploaded successfully to S3: {file_key}")
            
            return {
                "file_key": uploaded_key,
                "file_url": file_url,
                "bucket": self.bucket_name
            }
            
        except ClientError as e:
            LOGGER.error(f"Error uploading file to S3: {e}")
            raise Exception(f"Failed to upload file to S3: {str(e)}")
    
    async def download_file(self, file_key: str) -> bytes:
        """
        Download a file from S3 bucket
        
        Args:
            file_key: S3 key of the file to download
            
        Returns:
            File content as bytes
        """
        try:
            loop = asyncio.get_event_loop()
            
            def do_download():
                response = self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=file_key
                )
                return response['Body'].read()
            
            file_content = await loop.run_in_executor(None, do_download)
            
            LOGGER.info(f"File downloaded successfully from S3: {file_key}")
            return file_content
            
        except ClientError as e:
            LOGGER.error(f"Error downloading file from S3: {e}")
            raise Exception(f"Failed to download file from S3: {str(e)}")
    
    async def delete_file(self, file_key: str) -> bool:
        """
        Delete a file from S3 bucket
        
        Args:
            file_key: S3 key of the file to delete
            
        Returns:
            True if successful
        """
        try:
            loop = asyncio.get_event_loop()
            
            def do_delete():
                self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=file_key
                )
            
            await loop.run_in_executor(None, do_delete)
            
            LOGGER.info(f"File deleted successfully from S3: {file_key}")
            return True
            
        except ClientError as e:
            LOGGER.warning(f"Error deleting file from S3: {e}")
            return False
    
    async def generate_presigned_url(self, file_key: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for temporary access to a file
        
        Args:
            file_key: S3 key of the file
            expiration: Time in seconds for the URL to remain valid (default: 1 hour)
            
        Returns:
            Presigned URL string or None if failed
        """
        try:
            loop = asyncio.get_event_loop()
            
            def generate_url():
                return self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': self.bucket_name,
                        'Key': file_key
                    },
                    ExpiresIn=expiration
                )
            
            url = await loop.run_in_executor(None, generate_url)
            
            LOGGER.info(f"Presigned URL generated for: {file_key}")
            return url
            
        except ClientError as e:
            LOGGER.error(f"Error generating presigned URL: {e}")
            return None
