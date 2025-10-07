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


# Conjuntos de razões aceitas por modelo, conforme documentação Runway
_RATIOS_GEN4 = {
    "1920:1080",
    "1080:1920",
    "1024:1024",
    "1360:768",
    "1080:1080",
    "1168:880",
    "1440:1080",
    "1080:1440",
    "1808:768",
    "2112:912",
    "1280:720",
    "720:1280",
    "720:720",
    "960:720",
    "720:960",
    "1680:720",
}

_RATIOS_GEMINI = {
    "1344:768",
    "768:1344",
    "1024:1024",
    "1184:864",
    "864:1184",
    "1536:672",
}


def _coerce_ratio_for_model(model: str, desired_ratio: str) -> str:
    """
    Ajusta a razão desejada para um valor válido do modelo.
    - gen4_image e gen4_image_turbo usam _RATIOS_GEN4
    - gemini_2.5_flash usa _RATIOS_GEMINI
    """
    group = "gen4" if model in {"gen4_image", "gen4_image_turbo"} else "gemini"
    allowed = _RATIOS_GEN4 if group == "gen4" else _RATIOS_GEMINI
    if desired_ratio in allowed:
        return desired_ratio
    # Heurística simples: escolher paisagem/retrato/quadrado equivalente
    if desired_ratio == "1024:1024":
        return "1024:1024" if "1024:1024" in allowed else next(iter(allowed))
    # paisagem
    landscape_pref = [r for r in allowed if int(r.split(":")[0]) > int(r.split(":")[1])]
    # retrato
    portrait_pref = [r for r in allowed if int(r.split(":")[0]) < int(r.split(":")[1])]
    # quadrado
    square_pref = [r for r in allowed if int(r.split(":")[0]) == int(r.split(":")[1])]

    try:
        a, b = desired_ratio.split(":")
        a_i, b_i = int(a), int(b)
    except Exception:
        a_i, b_i = 1, 1

    if a_i == b_i and square_pref:
        return square_pref[0]
    if a_i > b_i and landscape_pref:
        return landscape_pref[0]
    if a_i < b_i and portrait_pref:
        return portrait_pref[0]
    # Fallback: primeiro permitido
    return next(iter(allowed))


class RunwayService:
    def __init__(self) -> None:
        self.api_key = settings.RUNWAY_API_KEY
        self.model = getattr(settings, "RUNWAY_MODEL", "gen4_image")
        self.base_url = (getattr(settings, "RUNWAY_BASE_URL", "https://api.runwayml.com/v1").rstrip("/"))
        # Versão de API exigida pelo Runway
        self.api_version_header = "2024-11-06"

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
            # Mantemos suporte opcional ao SDK, mas a integração padrão usa HTTP
            self._client = self._sdk_cls(api_key=self.api_key)
    async def _http_text_to_image(self, *, prompt_text: str, ratio: str, model: str, reference_images: Optional[List[Dict[str, str]]]) -> str:
        """
        Chama POST /v1/text_to_image da API do Runway e retorna o id da task.
        """
        url = f"{self.base_url}/text_to_image"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Runway-Version": self.api_version_header,
        }

        payload: Dict[str, Any] = {
            "promptText": prompt_text,
            "ratio": ratio,
            "model": model,
        }
        if reference_images:
            # Envia exatamente como recebido (sem conversão para data URI)
            payload["referenceImages"] = reference_images

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 429:
                raise RuntimeError("Rate limit excedido na API do Runway (429). Tente novamente em instantes.")
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                # Propaga erro legível
                detail = None
                try:
                    detail = resp.json()
                except Exception:
                    detail = resp.text
                raise RuntimeError(f"Runway text_to_image falhou ({resp.status_code}): {detail}") from e

            data = resp.json() or {}
            task_id = data.get("id") or data.get("taskId") or data.get("task_id")
            if not isinstance(task_id, str):
                raise RuntimeError("Resposta do Runway sem 'id' da task.")
            return task_id

    async def imagine(
        self,
        *,
        prompt: str,
        aspect_ratio: Optional[str] = None,
        exact_ratio: Optional[str] = None,
        s3_url: Optional[str] = None,
        style_ref_url: Optional[str] = None,
        reference_images: Optional[List[Dict[str, str]]] = None,
        model_override: Optional[str] = None,
    ) -> str:
        """
        Dispara geração com Runway e retorna um task_id interno para acompanhamento.
        - Se `s3_url` e/ou `style_ref_url` vierem, baixa as imagens e inclui como referências.
        - `reference_images`: lista [{"uri": data_uri, "tag": "ref"}, ...].
        """
        # Escolhe modelo
        chosen_model = (model_override or self.model).strip()

        # Ratio: se vier exact_ratio, usa exatamente como recebido; caso contrário, mapeia e coerce
        if exact_ratio and exact_ratio.strip():
            ratio = exact_ratio.strip()
        else:
            desired_ratio = _map_aspect_ratio_to_runway_ratio(aspect_ratio)
            ratio = _coerce_ratio_for_model(chosen_model, desired_ratio)

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

        # gen4_image_turbo exige ao menos 1 imagem de referência
        if chosen_model == "gen4_image_turbo" and not refs:
            raise RuntimeError("O modelo gen4_image_turbo exige ao menos uma imagem de referência.")

        # Dispara task via HTTP oficial do Runway
        task_id = await self._http_text_to_image(prompt_text=prompt, ratio=ratio, model=chosen_model, reference_images=refs)

        # Armazena estado inicial localmente para o endpoint /progress
        _TASKS[task_id] = {"status": "PENDING", "progress": 0}
        logger.info("Runway task iniciada: %s", task_id)
        return task_id

    async def fetch_status(self, task_id: str) -> Dict[str, Any] | None:
        """
        Consulta GET /v1/tasks/{id} no Runway e adapta para o contrato interno.
        """
        url = f"{self.base_url}/tasks/{task_id}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Runway-Version": self.api_version_header,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 404:
                    return None
                if resp.status_code == 429:
                    # Considera como throttled
                    data = {"status": "THROTTLED", "percentage": 0}
                else:
                    resp.raise_for_status()
                    data = resp.json() or {}
        except httpx.HTTPStatusError as e:
            logger.warning("Falha ao consultar status da task %s: %s", task_id, e)
            return _TASKS.get(task_id)
        except Exception as e:  # pragma: no cover
            logger.warning("Erro de rede ao consultar task %s: %s", task_id, e)
            return _TASKS.get(task_id)

        # Normaliza
        status_val = data.get("status")
        progress_val = data.get("progress", 0)
        percentage = 0
        try:
            # API retorna [0..1]; convertendo para 0..100 inteiro
            if isinstance(progress_val, (int, float)):
                percentage = int(float(progress_val) * 100)
        except Exception:
            percentage = 0

        image_urls: List[str] = []
        if (data.get("status") == "SUCCEEDED") and isinstance(data.get("output"), list):
            image_urls = [u for u in data["output"] if isinstance(u, str)]

        adapted = {"status": status_val, "percentage": percentage}
        if image_urls:
            adapted["image_urls"] = image_urls

        # Atualiza cache em memória para fallback
        try:
            # status RUNNING -> progresso mínimo 1; PENDING -> 0
            local_progress = 0
            st_lower = (str(status_val).lower()) if status_val else ""
            if st_lower == "running":
                local_progress = max(percentage, 1)
            elif st_lower == "succeeded":
                local_progress = 100
            _TASKS[task_id] = {
                "status": status_val or "PENDING",
                "progress": local_progress,
                **({"image_urls": image_urls} if image_urls else {}),
            }
        except Exception:
            pass

        return adapted

    async def monitor_until_ready(
        self,
        task_id: str,
        *,
        max_attempts: int = 120,
        interval_s: float = 5.0,
    ) -> List[str] | None:
        """
        Aguarda a conclusão consultando GET /tasks/{id} em intervalos (~5s sugeridos pela API).
        """
        for _ in range(max_attempts):
            status = await self.fetch_status(task_id)
            if not status:
                await asyncio.sleep(interval_s)
                continue
            st_lower = (str(status.get("status") or "")).lower()
            if st_lower == "succeeded":
                return status.get("image_urls") or []
            if st_lower == "failed":
                return []
            await asyncio.sleep(interval_s)
        return []
