from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from services.photo_service import PhotoService
from entities.photo import Photo


class PhotoController:
    def __init__(self, session: AsyncSession):
        self.service = PhotoService(session)


    async def upload(self, *, file: UploadFile) -> Photo:
        return await self.service.create_with_upload(file=file)


    async def generate_ia_with_prompt(self, *, photo_id: int, prompt: str, aspect_ratio: str = "9:16"):
        return await self.service.generate_ia_with_prompt(photo_id=photo_id, prompt=prompt, aspect_ratio=aspect_ratio)

    async def update(self, *, photo_id: int, quantidade: int | None, impressa: bool | None) -> Photo:
        return await self.service.update_fields(photo_id=photo_id, quantidade=quantidade, impressa=impressa)

    async def save_ia_by_name(self, *, nome: str, image_url: str, genero: str | None, tema: str | None,
                              menor: bool | None = None):
        return await self.service.save_ia_from_name(
            nome=nome, image_url=image_url, genero=genero, tema=tema, menor=menor
        )

    async def update_quantidade_by_name(self, *, nome: str, quantidade: int):
        return await self.service.update_quantidade_from_name(nome=nome, quantidade=quantidade)