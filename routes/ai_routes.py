from fastapi import APIRouter, HTTPException
from schemas.ai import GenerateRequest, GenerateResponse, ProgressResponse
from services.apiframe_service import ApiframeService

router = APIRouter(tags=["ai"])

@router.post("/generate", response_model=GenerateResponse)
async def generate(body: GenerateRequest):
    api = ApiframeService()

    # Monta prompt: se já veio pronto, usa; senão constrói simples com s3Url
    if body.prompt and body.prompt.strip():
        prompt = body.prompt.strip()
    elif body.s3Url:
        prompt = f"Crie uma imagem baseada na seguinte URL: {body.s3Url}"
    else:
        raise HTTPException(status_code=422, detail="Envie `prompt` ou `s3Url`")

    try:
        task_id = await api.imagine(prompt=prompt, aspect_ratio=body.aspect_ratio)
        return GenerateResponse(task_id=task_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/progress/{task_id}", response_model=ProgressResponse)
async def progress(task_id: str):
    api = ApiframeService()
    status = await api.fetch_status(task_id)
    if not status:
        # mantém contrato do seu front: responde 200 com progresso “erro”
        return ProgressResponse(progress=0)

    # Normaliza progresso (pode vir string)
    perc = status.get("percentage", 0)
    try:
        progress = int(perc)
    except Exception:
        progress = 0

    # Estados conhecidos do Apiframe (ajuste se necessário)
    st = (status.get("status") or "").lower()
    if st == "staged":
        progress = max(progress, 0)
    elif st == "processing":
        progress = max(progress, progress)
    elif "image_urls" in status:
        return ProgressResponse(progress=100, image_urls=status["image_urls"])

    return ProgressResponse(progress=progress)
