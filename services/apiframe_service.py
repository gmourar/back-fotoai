import asyncio
import httpx
from db.config import settings
from db.logs import logger
import re

class ApiframeService:
    def __init__(self):
        self.imagine_base = (getattr(settings, "APIFRAME_IMAGINE_BASE", None)
                             or "https://api.apiframe.ai/pro").rstrip("/")
        self.fetch_base = (getattr(settings, "APIFRAME_FETCH_BASE", None)
                           or "https://api.apiframe.pro").rstrip("/")
        self.api_key = settings.APIFRAME_API_KEY
        self.headers = {
            "Authorization": self.api_key,     # chave "crua"
            "Content-Type": "application/json",
        }

    def _inject_ar_flag(self, prompt: str, aspect_ratio: str | None) -> str:
        """
        Se 'aspect_ratio' vier (ex: '9:16'), garante que '--ar 9:16' está no prompt.
        - Se já existir alguma flag '--ar ...', não duplica.
        """
        if not aspect_ratio:
            return prompt
        # Checa se já existe '--ar <algo>'
        if re.search(r"(^|\s)--ar\s+\S+", prompt):
            return prompt
        return f"{prompt.strip()} --ar {aspect_ratio.strip()}"

    async def imagine(
        self,
        prompt: str,
        *,
        aspect_ratio: str | None = None,       # ✅ volta como conveniência
        mode: str | None = None,               # "fast" | "turbo"
        webhook_url: str | None = None,
        webhook_secret: str | None = None,
        timeout_s: int = 90
    ) -> str:
        """
        Envia job para Midjourney Pro. Campos no JSON: apenas prompt, mode, webhook_url, webhook_secret.
        AR deve estar no prompt (ex: '--ar 9:16'); aqui injetamos se vier 'aspect_ratio'.
        """
        prompt = self._inject_ar_flag(prompt, aspect_ratio)

        url = f"{self.imagine_base}/imagine"
        payload = {"prompt": prompt}
        if mode:
            payload["mode"] = mode
        if webhook_url:
            payload["webhook_url"] = webhook_url
        if webhook_secret:
            payload["webhook_secret"] = webhook_secret

        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.post(url, headers=self.headers, json=payload)
                if resp.status_code >= 400:
                    body_text = await resp.aread()
                    logger.error("Apiframe imagine erro %s: %s",
                                 resp.status_code,
                                 body_text.decode(errors="ignore"))
                    resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Apiframe imagine falhou: {e.response.status_code} {e.response.text}") from e
        except httpx.HTTPError as e:
            raise RuntimeError(f"Apiframe imagine erro de rede: {e}") from e

        task_id = data.get("task_id")
        if not task_id:
            raise RuntimeError(f"Apiframe imagine: 'task_id' ausente na resposta: {data}")
        logger.info("Apiframe task iniciada: %s", task_id)
        return task_id

    async def fetch_status(self, task_id: str, timeout_s: int = 15) -> dict | None:
        url = f"{self.fetch_base}/fetch"
        payload = {"task_id": task_id}
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.post(url, headers=self.headers, json=payload)
                if resp.status_code == 200:
                    return resp.json()
                logger.warning("Apiframe fetch %s: %s", resp.status_code, resp.text)
                return None
        except httpx.HTTPError as e:
            logger.warning("Apiframe fetch erro: %s", e)
            return None

    async def monitor_until_ready(
        self,
        task_id: str,
        *,
        max_attempts: int = 40,
        interval_s: float = 2.0
    ) -> str | None:
        for attempt in range(1, max_attempts + 1):
            status = await self.fetch_status(task_id)
            if status:
                urls = (status.get("image_urls")
                        or status.get("images")
                        or status.get("image_url"))  # às vezes vem singular
                if isinstance(urls, list) and urls:
                    logger.info("Imagem pronta: %s", urls[0])
                    return urls[0]
                if isinstance(urls, str) and urls:
                    logger.info("Imagem pronta: %s", urls)
                    return urls
                uri = status.get("uri")
                if isinstance(uri, str) and uri:
                    logger.info("Imagem pronta (uri): %s", uri)
                    return uri
            await asyncio.sleep(interval_s)
        logger.warning("Task %s não ficou pronta no tempo limite", task_id)
        return None