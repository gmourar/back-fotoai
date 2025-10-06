from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import SessionLocal
from controllers.photo_controller import PhotoController
from entities.photo import GeneroEnum
from schemas.photo import PhotoOut, PhotoUpdate, IAThemeRequest, IAPromptRequest, QuantidadeUpdate, SaveIARequest
from repositories.photo_repository import PhotoRepository

router = APIRouter(prefix="/photos", tags=["photos"])


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


@router.post("/upload", response_model=PhotoOut)
async def upload_photo(
        file: UploadFile = File(...),
        session: AsyncSession = Depends(get_session),
):
    ctrl = PhotoController(session)
    try:
        photo = await ctrl.upload(file=file)
        return photo
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


async def upload_photo(
        file: UploadFile = File(...),
        nome: str = Form(...),
        quantidade: int = Form(1),
        session: AsyncSession = Depends(get_session),
    ):


    ctrl = PhotoController(session)
    try:
        photo = await ctrl.upload(file=file, nome=nome, quantidade=quantidade)
        return photo
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{photo_id}/generate-ia", response_model=PhotoOut)
async def generate_ia_with_prompt(photo_id: int, body: IAPromptRequest, session: AsyncSession = Depends(get_session)):
    ctrl = PhotoController(session)
    try:
        photo = await ctrl.generate_ia_with_prompt(photo_id=photo_id, prompt=body.prompt, aspect_ratio=body.aspect_ratio)
        return photo
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



@router.get("/{photo_id}", response_model=PhotoOut)
async def get_photo(photo_id: int, session: AsyncSession = Depends(get_session)):
    repo = PhotoRepository(session)
    photo = await repo.get_by_id(photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="not found")
    return photo

@router.post("/{nome}/save-ia", response_model=PhotoOut)
async def save_ia(nome: str, body: SaveIARequest, session: AsyncSession = Depends(get_session)):
    ctrl = PhotoController(session)
    photo = await ctrl.save_ia_by_name(
        nome=nome,
        image_url=str(body.image_url),
        genero=GeneroEnum(body.genero),
        tema=body.tema,
        menor=body.menor,
    )
    return photo


@router.patch("/{nome}/quantidade", response_model=PhotoOut)
async def update_quantidade_by_name(
    nome: str,                              # <-- string, não int
    body: QuantidadeUpdate,
    session: AsyncSession = Depends(get_session),
):
    ctrl = PhotoController(session)
    try:
        photo = await ctrl.update_quantidade_by_name(
            nome=nome,
            quantidade=body.quantidade
        )
        return photo
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
