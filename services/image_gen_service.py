from db.logs import logger
from services.runway_service import RunwayService

class ImageGenService:
    def __init__(self, provider: str = "apiframe") -> None:
        self.provider = provider
        self.api = RunwayService()

    async def generate_from_url_and_theme(self, *, s3_url: str, aspect_ratio: str = "9:16") -> str | None:
        # Monta um prompt simples combinando URL + tema
        prompt = "Crie uma imagem baseada na foto fornecida"
        task_id = await self.api.imagine(prompt=prompt, aspect_ratio=aspect_ratio, s3_url=s3_url)
        # Runway devolve via monitor_until_ready uma lista; pegamos a primeira
        images = await self.api.monitor_until_ready(task_id)
        image_url = images[0] if images else None
        if not image_url:
            logger.error("[ImageGen] Falha na geração (task_id=%s)", task_id)
            return None
        return image_url