import io
import os
import re
from sqlite3 import IntegrityError
from PIL import Image, ImageOps

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile
from repositories.photo_repository import PhotoRepository
from services.apiframe_service import ApiframeService
from services.storage_service import StorageService
from services.image_gen_service import ImageGenService
from entities.photo import Photo

class PhotoService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PhotoRepository(session)
        self.storage = StorageService()
        self.image_gen = ImageGenService()
        self.ai = ApiframeService()

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        # novas molduras
        self.frame_paths = [
            os.path.join(base_dir, "Moldura1.png"),
            os.path.join(base_dir, "Moldura2.png"),
        ]

    async def _download_bytes(self, url: str) -> bytes:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content

    def _select_frame_path(self, *, nome: str) -> str:
        """
        Alterna entre Moldura1 e Moldura2 pela paridade do número no 'nome'.
        Ex.: 'foto1' -> Moldura1, 'foto2' -> Moldura2.
        Se não encontrar número, cai no índice 0 (Moldura1).
        """
        m = re.search(r"(\d+)$", nome)
        if m:
            n = int(m.group(1))
            idx = 0 if (n % 2 == 1) else 1
        else:
            idx = 0
        # fallback se arquivo não existir por algum motivo
        path = self.frame_paths[idx]
        if not os.path.exists(path):
            # tenta a outra; se também não existir, levanta erro claro
            alt = self.frame_paths[1 - idx]
            if os.path.exists(alt):
                return alt
            raise FileNotFoundError(f"Nenhuma moldura encontrada em {self.frame_paths}")
        return path

    def _apply_local_frame(self, base_bytes: bytes, frame_path: str) -> bytes:
        base = Image.open(io.BytesIO(base_bytes)).convert("RGBA")
        frame = Image.open(frame_path).convert("RGBA")
        fitted_frame = ImageOps.fit(frame, base.size, method=Image.LANCZOS)
        composed = Image.new("RGBA", base.size)
        composed.alpha_composite(base)
        composed.alpha_composite(fitted_frame)
        out = io.BytesIO()
        composed.save(out, format="PNG")
        out.seek(0)
        return out.getvalue()

    async def create_with_upload(self, *, file: UploadFile) -> Photo:
        data = await file.read()
        attempts = 3
        last_err = None
        for _ in range(attempts):
            nome = await self.repo.get_next_nome()
            key = f"{nome}.png"
            original_url = self.storage.upload_fileobj(
                io.BytesIO(data),
                key,
                content_type=file.content_type or "image/png"
            )
            try:
                photo = await self.repo.create(nome=nome, quantidade=0, original_url=original_url)
                await self.session.commit()
                return photo
            except IntegrityError as e:
                await self.session.rollback()
                last_err = e
                continue
        raise RuntimeError(f"Falha ao gerar nome sequencial (último erro: {last_err})")

    async def generate_ia_with_prompt(self, *, photo_id: int, prompt: str, aspect_ratio: str = "9:16"):
        photo = await self.repo.get_by_id(photo_id)
        if not photo:
            raise ValueError("Photo not found")

        task_id = await self.ai.imagine(prompt=prompt, aspect_ratio=aspect_ratio)
        image_url = await self.ai.monitor_until_ready(task_id)
        if not image_url:
            raise RuntimeError("Falha ao gerar imagem IA")

        base_bytes = await self._download_bytes(image_url)
        frame_path = self._select_frame_path(nome=photo.nome)
        final_bytes = self._apply_local_frame(base_bytes, frame_path)

        key = f"{photo.nome}IA.png"
        ia_public_url = self.storage.upload_fileobj(
            io.BytesIO(final_bytes),
            key,
            content_type="image/png"
        )

        await self.repo.set_ia_url(photo, ia_public_url)
        await self.session.commit()
        return photo

    async def save_ia_from_name(self, *, nome: str, image_url: str, genero: str | None = None, tema: str | None = None):
        photo = await self.repo.get_by_nome(nome)
        if not photo:
            raise ValueError("Photo not found")

        base_bytes = await self._download_bytes(image_url)
        frame_path = self._select_frame_path(nome=photo.nome)
        final_bytes = self._apply_local_frame(base_bytes, frame_path)

        key = f"{photo.nome}IA.png"
        ia_public_url = self.storage.upload_fileobj(
            io.BytesIO(final_bytes),
            key,
            content_type="image/png"
        )
        await self.repo.set_ia_and_meta(photo, ia_url=ia_public_url, genero=genero, tema=tema)
        await self.session.commit()
        return photo

    async def update_fields(self, *, photo_id: int, quantidade: int | None = None, impressa: bool | None = None) -> Photo:
        photo = await self.repo.get_by_id(photo_id)
        if not photo:
            raise ValueError("Photo not found")
        await self.repo.update_fields(photo, quantidade=quantidade, impressa=impressa)
        await self.session.commit()
        return photo

    async def update_quantidade_from_name(self, *, nome: str, quantidade: int):
        photo = await self.repo.get_by_nome(nome)
        if not photo:
            raise ValueError("Photo not found")
        await self.repo.update_fields(photo, quantidade=quantidade, impressa=True)
        await self.session.commit()
        return photo
