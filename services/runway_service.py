import asyncio
import base64
import mimetypes
import uuid
from typing import Any, Dict, List, Optional

import httpx

from db.config import settings
from db.logs import logger

# Armazena estado de tarefas em memória para acompanhamento via /progress
_TASKS: Dict[str, Dict[str, Any]] = {}


def _image_bytes_to_data_uri(data: bytes, content_type: Optional[str] = None) -> str:
    ctype = content_type or "image/png"
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:{ctype};base64,{b64}"


async def _download_bytes(url: str, timeout_s: int = 30) -> tuple[bytes, Optional[str]]:
    async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        # Tenta extrair content-type do header
        content_type = resp.headers.get("content-type")
        return resp.content, content_type


def _map_aspect_ratio_to_runway_ratio(ar: Optional[str]) -> str:
    if not ar:
        return "1024:1024"
    val = ar.strip()
    if val in {"1:1", "square"}:
        return "1024:1024"
    if val in {"16:9", "landscape"}:
        return "1920:1080"
    if val in {"9:16", "portrait"}:
        return "1080:1920"
    # Fallback simples
    try:
        if ":" in val:
            a, b = val.split(":", 1)
            a_i = int(a)
            b_i = int(b)
            if a_i == b_i:
                return "1024:1024"
            if a_i > b_i:
                return "1920:1080"
            return "1080:1920"
    except Exception:
        pass
    return "1024:1024"


class RunwayService:
    def __init__(self) -> None:
        self.api_key = settings.RUNWAY_API_KEY
        self.model = getattr(settings, "RUNWAY_MODEL", "gen4_image")

        # SDK opcional (se instalado)
        try:
            from runwayml import RunwayML, TaskFailedError  # type: ignore

            self._sdk_cls = RunwayML
            self._sdk_error = TaskFailedError
        except Exception:  # pragma: no cover
            self._sdk_cls = None
            self._sdk_error = Exception

        self._client = None
        if self._sdk_cls is not None:
            self._client = self._sdk_cls(api_key=self.api_key)

    async def _run_generation_task(
        self,
        *,
        task_id: str,
        prompt_text: str,
        ratio: str,
        reference_images: Optional[List[Dict[str, str]]],
    ) -> None:
        # Executa geração em thread para não bloquear o loop async
        def _worker_sync() -> Dict[str, Any]:
            if self._client is None:
                raise RuntimeError("SDK runwayml não instalado. Adicione a dependência 'runwayml'.")
            # Usa SDK conforme docs
            task = self._client.text_to_image.create(
                model=self.model,
                ratio=ratio,
                prompt_text=prompt_text,
                reference_images=reference_images or [],
            ).wait_for_task_output()
            return task

        try:
            _TASKS[task_id] = {"status": "RUNNING", "progress": 0}
            result: Dict[str, Any] = await asyncio.to_thread(_worker_sync)

            image_urls: List[str] = []
            # Tenta extrair imagens do resultado
            try:
                output = result.get("output") or {}
                images = output.get("images") or []
                for img in images:
                    url = img.get("url") or img.get("uri")
                    if isinstance(url, str):
                        image_urls.append(url)
            except Exception:
                pass
            if not image_urls:
                for key in ("image_urls", "images", "image_url"):
                    val = result.get(key)
                    if isinstance(val, list):
                        image_urls.extend([v for v in val if isinstance(v, str)])
                    elif isinstance(val, str):
                        image_urls.append(val)

            _TASKS[task_id] = {
                "status": "SUCCEEDED",
                "progress": 100,
                "image_urls": image_urls,
                "raw": result,
            }
        except Exception as e:  # pragma: no cover
            logger.error("Runway task falhou: %s", e)
            _TASKS[task_id] = {"status": "FAILED", "progress": 0, "error": str(e)}

    async def imagine(
        self,
        *,
        prompt: str,
        aspect_ratio: Optional[str] = None,
        s3_url: Optional[str] = None,
        style_ref_url: Optional[str] = None,
        reference_images: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Dispara geração com Runway e retorna um task_id interno para acompanhamento.
        - Se `s3_url` e/ou `style_ref_url` vierem, baixa as imagens e inclui como referências.
        - `reference_images`: lista [{"uri": data_uri, "tag": "ref"}, ...].
        """
        ratio = _map_aspect_ratio_to_runway_ratio(aspect_ratio)

        refs: List[Dict[str, str]] = []
        if reference_images:
            refs = reference_images
        else:
            # Adiciona foto do usuário, se fornecida
            if s3_url:
                try:
                    bytes_img, content_type = await _download_bytes(s3_url)
                    data_uri = _image_bytes_to_data_uri(bytes_img, content_type)
                    refs.append({"uri": data_uri, "tag": "ref"})
                except Exception as e:
                    logger.warning("Falha ao baixar s3_url para referência: %s", e)

            # Adiciona referência de estilo, se fornecida
            if style_ref_url:
                try:
                    bytes_img, content_type = await _download_bytes(style_ref_url)
                    data_uri = _image_bytes_to_data_uri(bytes_img, content_type)
                    refs.append({"uri": data_uri, "tag": "ref"})
                except Exception as e:
                    logger.warning("Falha ao baixar style_ref_url para referência: %s", e)

            # Garante que o prompt referencia a tag ao menos uma vez, se houver refs
            if refs and "@ref" not in prompt:
                prompt = f"{prompt} @ref".strip()

        task_id = uuid.uuid4().hex
        _TASKS[task_id] = {"status": "PENDING", "progress": 0}

        asyncio.create_task(
            self._run_generation_task(
                task_id=task_id,
                prompt_text=prompt,
                ratio=ratio,
                reference_images=refs,
            )
        )

        logger.info("Runway task iniciada: %s", task_id)
        return task_id

    async def fetch_status(self, task_id: str) -> Dict[str, Any] | None:
        return _TASKS.get(task_id)

    async def monitor_until_ready(
        self,
        task_id: str,
        *,
        max_attempts: int = 300,
        interval_s: float = 1.0,
    ) -> List[str] | None:
        for _ in range(max_attempts):
            st = _TASKS.get(task_id)
            if st and st.get("status") == "SUCCEEDED":
                return st.get("image_urls") or []
            if st and st.get("status") == "FAILED":
                return []
            await asyncio.sleep(interval_s)
        return []
