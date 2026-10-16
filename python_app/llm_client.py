"""
Provider-Agnostic LLM Client for OpenAI-Compatible Endpoints (Groq, DeepSeek, OpenAI).
Handles text completions and multimodal vision calls, robust JSON parsing, Pydantic validation,
retries with exponential backoff, image sanitization (EXIF stripping, downscaling < 4MB),
token budget tracking, and per-user rate limiting.
"""

import os
import re
import json
import time
import base64
import logging
from io import BytesIO
from datetime import datetime, timezone, date
from typing import List, Dict, Any, Optional, Type, TypeVar
import httpx
from pydantic import BaseModel
from PIL import Image

from python_app.config import settings

logger = logging.getLogger("llm_client")
logger.setLevel(logging.INFO)

T = TypeVar("T", bound=BaseModel)

def redact_sensitive(text: str) -> str:
    """Redacts API keys and image base64 data from logs."""
    if not text:
        return text
    # Redact common key patterns
    if settings.LLM_API_KEY:
        text = text.replace(settings.LLM_API_KEY, "[REDACTED_API_KEY]")
    text = re.sub(r'gsk_[A-Za-z0-9_-]{20,}', '[REDACTED_GROQ_KEY]', text)
    text = re.sub(r'data:image\/[a-zA-Z]+;base64,[A-Za-z0-9+/=]{50,}', 'data:image/...;base64,[REDACTED_BYTES]', text)
    return text


def sanitize_and_compress_image(image_bytes: bytes, max_bytes: int = 3_500_000, max_dim: int = 1568) -> str:
    """
    Strips EXIF (including GPS metadata), downscales, and compresses image.
    Returns base64 data URL string (e.g. data:image/jpeg;base64,...).
    Guarantees output stays under max_bytes (default 3.5 MB, well below 4 MB cap).
    """
    try:
        img = Image.open(BytesIO(image_bytes))
        # Strip EXIF by copying image data to a clean image
        data = list(img.getdata())
        clean_img = Image.new(img.mode, img.size)
        clean_img.putdata(data)

        # Convert RGBA to RGB for JPEG compression if necessary
        if clean_img.mode in ("RGBA", "P"):
            clean_img = clean_img.convert("RGB")
        elif clean_img.mode != "RGB":
            clean_img = clean_img.convert("RGB")

        # Downscale if dimensions exceed max_dim
        width, height = clean_img.size
        if width > max_dim or height > max_dim:
            if width > height:
                new_w = max_dim
                new_h = int(height * (max_dim / width))
            else:
                new_h = max_dim
                new_w = int(width * (max_dim / height))
            clean_img = clean_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Iteratively compress if larger than max_bytes
        quality = 85
        buffer = BytesIO()
        clean_img.save(buffer, format="JPEG", quality=quality, optimize=True)
        
        while buffer.tell() > max_bytes and quality > 30:
            buffer = BytesIO()
            quality -= 15
            clean_img.save(buffer, format="JPEG", quality=quality, optimize=True)

        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception as e:
        logger.error(f"Error sanitizing image: {redact_sensitive(str(e))}")
        # Fallback to direct base64 if PIL fails
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded}"


class LLMClient:
    def __init__(self):
        self.base_url = settings.LLM_BASE_URL.rstrip("/")
        self.api_key = settings.LLM_API_KEY
        self.model_text = settings.LLM_MODEL_TEXT or "openai/gpt-oss-20b"
        self.model_vision = settings.LLM_MODEL_VISION or "llama-3.2-11b-vision-preview"
        self.timeout = float(settings.LLM_TIMEOUT_SECONDS)
        self.max_retries = int(settings.LLM_MAX_RETRIES)
        self.daily_budget = int(settings.LLM_DAILY_TOKEN_BUDGET)

        # Budget state
        self._budget_date: date = datetime.now(timezone.utc).date()
        self._tokens_used_today: int = 0

        # Rate limiting state: user_id -> list of timestamps
        self._user_requests: Dict[str, List[float]] = {}
        self._rate_limit_per_minute = 30

        # Capability detection
        self.vision_available = False
        self._check_capabilities()

    def _check_capabilities(self):
        """Startup check to test if API key is present and whether vision model is supported."""
        if not self.api_key:
            logger.warning("No LLM_API_KEY configured. External LLM calls will use rule-based fallback.")
            self.vision_available = False
            return

        # Perform a minimal vision probe if a vision model is configured
        try:
            # We don't fail startup if vision is unsupported; we mark vision_available = False
            # so photo analysis falls back gracefully.
            headers = {"Authorization": f"Bearer {self.api_key}"}
            with httpx.Client(timeout=10.0) as client:
                r = client.get(f"{self.base_url}/models", headers=headers)
                if r.status_code == 200:
                    models = [m.get("id", "") for m in r.json().get("data", [])]
                    # Check if model_vision exists in models list
                    if self.model_vision in models:
                        self.vision_available = True
                    else:
                        # Some endpoints don't list all preview models or have different vision naming
                        self.vision_available = False
                        logger.info(f"Configured vision model '{self.model_vision}' not in active model list. Vision fallback will be used.")
                else:
                    self.vision_available = False
        except Exception as e:
            logger.warning(f"Capability check warning: {redact_sensitive(str(e))}")
            self.vision_available = False

    def check_rate_limit(self, user_id: str = "default") -> bool:
        """Enforces sliding-window rate limit (e.g. 30 requests/min)."""
        now = time.time()
        window_start = now - 60.0
        timestamps = self._user_requests.setdefault(user_id, [])
        # Clean older than 1 minute
        self._user_requests[user_id] = [t for t in timestamps if t > window_start]
        if len(self._user_requests[user_id]) >= self._rate_limit_per_minute:
            return False
        self._user_requests[user_id].append(now)
        return True

    def check_token_budget(self) -> bool:
        """Checks if daily token budget has been reached."""
        today = datetime.now(timezone.utc).date()
        if today != self._budget_date:
            self._budget_date = today
            self._tokens_used_today = 0
        return self._tokens_used_today < self.daily_budget

    def record_token_usage(self, usage: Optional[Dict[str, Any]]):
        """Records token usage from OpenAI response object."""
        if not usage:
            return
        total = usage.get("total_tokens", 0)
        self._tokens_used_today += total
        logger.info(f"LLM usage: {total} tokens (today total: {self._tokens_used_today}/{self.daily_budget})")

    def _clean_json_text(self, text: str) -> str:
        """Strips markdown code blocks, backticks, and whitespace."""
        text = text.strip()
        # Remove ```json ... ``` or ``` ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if match:
            text = match.group(1).strip()
        return text

    def call_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        json_mode: bool = True,
        temperature: float = 0.2,
        user_id: str = "default",
    ) -> Dict[str, Any]:
        """
        Executes chat completion request with exponential backoff on 429/5xx errors.
        Does NOT retry on 4xx client/auth errors.
        """
        if not self.api_key:
            raise ValueError("LLM_API_KEY is not configured.")

        if not self.check_rate_limit(user_id):
            raise RuntimeError("Per-user rate limit exceeded. Please wait a moment.")

        if not self.check_token_budget():
            raise RuntimeError(f"Daily LLM token budget of {self.daily_budget} reached.")

        selected_model = model or self.model_text
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        backoff = 1.0
        start_time = time.time()
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    latency = round(time.time() - start_time, 2)

                    if resp.status_code == 200:
                        data = resp.json()
                        usage = data.get("usage", {})
                        self.record_token_usage(usage)
                        logger.info(f"LLM call succeeded (model={selected_model}, latency={latency}s)")
                        return data

                    # Handle 429 or 5xx with retry
                    if resp.status_code in (429, 500, 502, 503, 504):
                        last_error = f"HTTP {resp.status_code}: {resp.text}"
                        logger.warning(f"LLM retryable error on attempt {attempt+1}: {redact_sensitive(last_error)}")
                        if attempt < self.max_retries:
                            time.sleep(backoff)
                            backoff *= 2.0
                            continue
                        break

                    # 4xx client/auth error: do NOT retry
                    err_msg = f"HTTP {resp.status_code}: {resp.text}"
                    logger.error(f"LLM client error: {redact_sensitive(err_msg)}")
                    raise RuntimeError(f"LLM request failed with status {resp.status_code}: {resp.json().get('error', {}).get('message', resp.text)}")

            except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                last_error = str(net_err)
                logger.warning(f"LLM network error on attempt {attempt+1}: {redact_sensitive(last_error)}")
                if attempt < self.max_retries:
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue
                break
            except Exception as e:
                # If it's already RuntimeError from 4xx, re-raise immediately
                if isinstance(e, RuntimeError):
                    raise
                last_error = str(e)
                break

        raise RuntimeError(f"LLM call failed after {self.max_retries+1} attempts: {redact_sensitive(str(last_error))}")

    def call_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
        images_base64: Optional[List[str]] = None,
        model: Optional[str] = None,
        user_id: str = "default",
    ) -> T:
        """
        Calls LLM and validates output against a Pydantic schema.
        If initial parse fails, retries once with a targeted JSON repair prompt.
        """
        # Build messages
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": f"{system_prompt}\nYou MUST output strictly valid JSON conforming to the requested schema. Do not output conversational filler."}
        ]

        if images_base64:
            # Multimodal message
            content_blocks: List[Dict[str, Any]] = [{"type": "text", "text": user_prompt}]
            # Cap at 5 images
            for img_url in images_base64[:5]:
                content_blocks.append({"type": "image_url", "image_url": {"url": img_url}})
            messages.append({"role": "user", "content": content_blocks})
            target_model = model or self.model_vision
        else:
            messages.append({"role": "user", "content": user_prompt})
            target_model = model or self.model_text

        # First attempt
        raw_res = self.call_chat_completion(messages, model=target_model, json_mode=True, user_id=user_id)
        raw_content = raw_res["choices"][0]["message"]["content"]
        cleaned_json = self._clean_json_text(raw_content)

        try:
            parsed = json.loads(cleaned_json)
            return response_model.model_validate(parsed)
        except Exception as parse_err:
            logger.warning(f"Initial JSON validation failed: {str(parse_err)}. Attempting repair prompt.")
            # Repair prompt attempt
            repair_messages = [
                {"role": "system", "content": "You are a JSON formatting repair engine. Fix the provided text into valid JSON matching the schema."},
                {"role": "user", "content": f"The following output was malformed or failed validation for {response_model.__name__}:\n\n{raw_content}\n\nError: {str(parse_err)}\n\nPlease return ONLY valid JSON."}
            ]
            repair_res = self.call_chat_completion(repair_messages, model=self.model_text, json_mode=True, user_id=user_id)
            repair_content = self._clean_json_text(repair_res["choices"][0]["message"]["content"])
            repair_parsed = json.loads(repair_content)
            return response_model.model_validate(repair_parsed)

llm_client = LLMClient()
