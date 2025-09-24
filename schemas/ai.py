from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List

class GenerateRequest(BaseModel):
    # Aceita tanto prompt pronto quanto só a URL; se vierem os dois, usa `prompt`.
    prompt: Optional[str] = Field(default=None, description="Prompt final já com a URL embutida (--cref, etc.)")
    s3Url: Optional[HttpUrl] = Field(default=None, description="URL pública da imagem no S3")
    aspect_ratio: str = Field(default="9:16")

class GenerateResponse(BaseModel):
    task_id: str

class ProgressResponse(BaseModel):
    progress: int
    image_urls: Optional[List[HttpUrl]] = None
