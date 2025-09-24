from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Literal
from entities.photo import GeneroEnum  # <- importe do model


class PhotoBase(BaseModel):
    nome: str = Field(..., examples=["foto1"])
    quantidade: int = Field(ge=1, default=1)

class PhotoCreate(PhotoBase):
    pass

class PhotoUpdate(BaseModel):
    quantidade: Optional[int] = Field(ge=1, default=None)
    impressa: Optional[bool] = None

class PhotoOut(BaseModel):
    id: int
    nome: str
    original_url: Optional[HttpUrl] | None
    ia_url: Optional[HttpUrl] | None
    quantidade: int
    impressa: bool
    genero: Optional[GeneroEnum] = None   # ✅ NADA de Mapped aqui
    tema: Optional[str] = None

    class Config:
        from_attributes = True  # ok no Pydantic v2


class IAThemeRequest(BaseModel):
    tema: str = Field(..., description="Tema escolhido para compor o prompt com a foto original")
    aspect_ratio: str = Field(default="1:1")

class IASelect(BaseModel):
    selected_url: HttpUrl

class IAPromptRequest(BaseModel):
    prompt: str = Field(..., description="Prompt final já com a URL S3 embutida (ex: --cref https://... )")
    aspect_ratio: str = Field(default="9:16")

class QuantidadeUpdate(BaseModel):
    quantidade: int = Field(ge=0, description="Quantidade desejada (>= 0)")

class SaveIARequest(BaseModel):
    image_url: HttpUrl
    genero: Literal["masculino", "feminino"]
    tema: str = Field(min_length=1, max_length=100)