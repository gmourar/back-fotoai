from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from schemas.ai import GenerateRequest, GenerateResponse, ProgressResponse
from services.runway_service import RunwayService

router = APIRouter(tags=["ai"])

@router.post("/generate", response_model=GenerateResponse)
async def generate(body: GenerateRequest):
    api = RunwayService()

    # Runway não aceita URL pública direta como referência; baixamos quando s3Url vier
    if body.prompt and body.prompt.strip():
        prompt = body.prompt.strip()
    elif body.s3Url:
        prompt = "Crie uma imagem baseada na foto fornecida"
    else:
        raise HTTPException(status_code=422, detail="Envie `prompt` ou `s3Url`")

    try:
        task_id = await api.imagine(
            prompt=prompt,
            aspect_ratio=body.aspect_ratio,
            s3_url=(str(body.s3Url) if body.s3Url else None),
        )
        return GenerateResponse(task_id=task_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/progress/{task_id}", response_model=ProgressResponse)
async def progress(task_id: str):
    api = RunwayService()
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

    # Estados internos: PENDING, RUNNING, SUCCEEDED, FAILED
    st = (status.get("status") or "").lower()
    if st in {"pending", "running"}:
        progress = max(progress, 1 if st == "pending" else 50)
    elif st == "succeeded" and "image_urls" in status:
        return ProgressResponse(progress=100, image_urls=status["image_urls"])
    elif st == "failed":
        progress = 0

    return ProgressResponse(progress=progress)


@router.post("/generate-upload", response_model=GenerateResponse)
async def generate_upload(
    file: UploadFile = File(...),
    prompt: str | None = Form(default=None),
    aspect_ratio: str = Form(default="9:16"),
):
    api = RunwayService()
    try:
        data = await file.read()
        # Constrói data URI para referência
        content_type = file.content_type or "image/png"
        import base64

        data_uri = f"data:{content_type};base64,{base64.b64encode(data).decode('utf-8')}"
        final_prompt = (prompt or "Crie uma imagem baseada na foto fornecida").strip()

        task_id = await api.imagine(
            prompt=final_prompt,
            aspect_ratio=aspect_ratio,
            reference_images=[{"uri": data_uri, "tag": "ref"}],
        )
        return GenerateResponse(task_id=task_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
