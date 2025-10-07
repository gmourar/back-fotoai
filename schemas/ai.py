from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List


class ReferenceImage(BaseModel):
    # Usa string simples para suportar data URI (data:image/png;base64,...) além de URLs
    uri: str
    tag: str = Field(default="ref")


class GenerateV2Request(BaseModel):
    # Novo contrato compatível com a API do Runway
    promptText: str
    ratio: str = Field(default="1080:1920")
    model: Optional[str] = Field(default=None, description="Override do modelo (ex.: gen4_image)")
    referenceImages: Optional[List[ReferenceImage]] = None


class GenerateResponse(BaseModel):
    task_id: str


class ProgressResponse(BaseModel):
    progress: int
    image_urls: Optional[List[HttpUrl]] = None
