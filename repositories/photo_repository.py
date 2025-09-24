from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Sequence, Optional
from entities.photo import Photo, GeneroEnum


class PhotoRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, nome: str, quantidade: int, original_url: str | None) -> Photo:
        photo = Photo(nome=nome, quantidade=quantidade, impressa=False, original_url=original_url)
        self.session.add(photo)
        await self.session.flush()
        return photo

    async def get_by_id(self, photo_id: int) -> Photo | None:
        res = await self.session.execute(select(Photo).where(Photo.id == photo_id))
        return res.scalar_one_or_none()

    async def get_by_nome(self, nome: str) -> Photo | None:
        res = await self.session.execute(select(Photo).where(Photo.nome == nome))
        return res.scalar_one_or_none()

    async def list(self) -> Sequence[Photo]:
        res = await self.session.execute(select(Photo).order_by(Photo.id.desc()))
        return res.scalars().all()

    async def set_ia_url(self, photo: Photo, ia_url: str) -> Photo:
        photo.ia_url = ia_url
        self.session.add(photo)
        await self.session.flush()
        return photo

    async def set_ia_and_meta(
            self,
            photo: Photo,
            *,
            ia_url: str,
            genero: Optional[GeneroEnum] = None,
            tema: Optional[str] = None
    ) -> Photo:
        photo.ia_url = ia_url
        if genero is not None:
            photo.genero = genero
        if tema is not None:
            photo.tema = tema
        self.session.add(photo)
        await self.session.flush()
        return photo

    async def update_fields(self, photo: Photo, *, quantidade: int | None = None, impressa: bool | None = None) -> Photo:
        if quantidade is not None:
            photo.quantidade = quantidade
        if impressa is not None:
            photo.impressa = impressa
        self.session.add(photo)
        await self.session.flush()
        return photo

    async def get_next_nome(self) -> str:
        """Gera 'fotoN' onde N = 1 + max(sufixo numérico) entre nomes 'foto\\d+'."""
        res = await self.session.execute(select(Photo.nome))
        nomes = [row[0] for row in res.all() if row[0]]
        max_n = 0
        for n in nomes:
            if n.startswith("foto"):
                suf = n[4:]
                if suf.isdigit():
                    max_n = max(max_n, int(suf))
        return f"foto{max_n + 1}"
