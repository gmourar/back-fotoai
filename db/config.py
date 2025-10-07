from pydantic import AnyUrl, Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "photo-ia-backend"
    APP_ENV: str = "dev"


    # Database
    DATABASE_URL: AnyUrl = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/photo_db"
    )

    # S3 (or any S3-compatible: MinIO, Cloudflare R2, etc.)
    S3_ENDPOINT_URL: str | None = Field(default=None, validation_alias=AliasChoices("s3_endpoint_url", "S3_ENDPOINT_URL"))
    S3_REGION: str = Field(default="us-east-1", validation_alias=AliasChoices("s3_region", "S3_REGION"))
    S3_ACCESS_KEY_ID: str = Field(default="changeme", validation_alias=AliasChoices("s3_access_key_id", "S3_ACCESS_KEY_ID"))
    S3_SECRET_ACCESS_KEY: str = Field(default="changeme", validation_alias=AliasChoices("s3_secret_access_key", "S3_SECRET_ACCESS_KEY"))
    S3_BUCKET: str = Field(default="my-photo-bucket", validation_alias=AliasChoices("s3_bucket", "S3_BUCKET"))
    S3_PUBLIC_BASE_URL: str | None = Field(default=None, validation_alias=AliasChoices("s3_public_base_url", "S3_PUBLIC_BASE_URL"))
    S3_ENABLE_ACL: bool = Field(default=False, validation_alias=AliasChoices("s3_enable_acl", "S3_ENABLE_ACL"))   # mapeia .env S3_ENABLE_ACL=false/true

    # Apiframe / Midjourney
    APIFRAME_API_KEY: str = "86b864f9-4f57-4932-8254-4b46e23f0ddc"
    APIFRAME_IMAGINE_BASE: str = "https://api.apiframe.ai/pro"
    APIFRAME_FETCH_BASE: str = "https://api.apiframe.pro"

    # Runway
    RUNWAY_API_KEY: str = "changeme"
    RUNWAY_BASE_URL: str = "https://api.runwayml.com/v1"
    RUNWAY_MODEL: str = "gen4_image"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

settings = Settings()