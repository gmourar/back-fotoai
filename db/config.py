from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "photo-ia-backend"
    APP_ENV: str = "dev"


    # Database
    DATABASE_URL: AnyUrl = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/photo_db"
    )

    # S3 (or any S3-compatible: MinIO, Cloudflare R2, etc.)
    S3_ENDPOINT_URL: str | None = None
    S3_REGION: str = "us-east-1"
    S3_ACCESS_KEY_ID: str = "changeme"
    S3_SECRET_ACCESS_KEY: str = "changeme"
    S3_BUCKET: str = "my-photo-bucket"
    S3_PUBLIC_BASE_URL: str | None = None
    S3_ENABLE_ACL: bool = False   # mapeia .env S3_ENABLE_ACL=false/true

    # Apiframe / Midjourney
    APIFRAME_API_KEY: str = "86b864f9-4f57-4932-8254-4b46e23f0ddc"
    APIFRAME_IMAGINE_BASE: str = "https://api.apiframe.ai/pro"
    APIFRAME_FETCH_BASE: str = "https://api.apiframe.pro"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

settings = Settings()