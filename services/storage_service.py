# app/services/storage_service.py
import io
import httpx
import boto3
from typing import BinaryIO
from db.config import settings

class StorageService:
    def __init__(self) -> None:
        self.client = boto3.client(
            "s3",
            region_name=settings.S3_REGION,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            endpoint_url=settings.S3_ENDPOINT_URL,
        )
        self.bucket = settings.S3_BUCKET
        self.public_base = settings.S3_PUBLIC_BASE_URL

    def _public_url(self, key: str) -> str:
        if self.public_base:
            return f"{self.public_base.rstrip('/')}/{key}"
        if settings.S3_ENDPOINT_URL and "amazonaws.com" not in (settings.S3_ENDPOINT_URL or ""):
            return f"{settings.S3_ENDPOINT_URL.rstrip('/')}/{self.bucket}/{key}"
        return f"https://{self.bucket}.s3.{settings.S3_REGION}.amazonaws.com/{key}"

    def upload_fileobj(self, fileobj: BinaryIO, key: str, content_type: str = "application/octet-stream") -> str:
        # ⚠️ Nada de ACL aqui
        # Se estiver usando fileobj reutilizável, garanta o ponteiro no início
        try:
            fileobj.seek(0)
        except Exception:
            pass

        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=fileobj,
            ContentType=content_type,
        )
        return self._public_url(key)

    async def upload_from_url(self, url: str, key: str, content_type: str | None = None) -> str:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = io.BytesIO(resp.content)
        return self.upload_fileobj(data, key, content_type or resp.headers.get("content-type", "application/octet-stream"))
