from db.logs import logger
from services.apiframe_service import ApiframeService

class ImageGenService:
    def __init__(self, provider: str = "apiframe") -> None:
        self.provider = provider
        self.api = ApiframeService()

    async def generate_from_url_and_theme(self, *, s3_url: str, aspect_ratio: str = "9:16") -> str | None:
        # Monta um prompt simples combinando URL + tema
        prompt = f"Crie uma imagem baseada na seguinte URL: {s3_url}"
        task_id = await self.api.imagine(prompt=prompt, aspect_ratio=aspect_ratio)
        image_url = await self.api.monitor_progress(task_id)
        if not image_url:
            logger.error("[ImageGen] Falha na geração (task_id=%s)", task_id)
            return None
        return image_url