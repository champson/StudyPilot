from __future__ import annotations

import os
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import UUID

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_redis_client
from app.llm.cost_tracker import log_model_call


class ModelRouter:
    REDIS_MODE_KEY = "system:run_mode"

    def __init__(self, config_path: str, redis_client: Any | None = None):
        self._config_path = self._resolve_config_path(config_path)
        with self._config_path.open("r", encoding="utf-8") as fh:
            self._config = yaml.safe_load(fh) or {}
        self._redis = redis_client
        self._clients: dict[str, Any] = {}

    def _resolve_config_path(self, config_path: str) -> Path:
        path = Path(config_path)
        if path.is_absolute():
            return path
        root = Path(__file__).resolve().parents[2]
        return root / path

    async def current_mode(self) -> str:
        default_mode = self._config.get("current_mode", "normal")
        if self._redis is None:
            try:
                self._redis = get_redis_client()
            except Exception:
                return default_mode
        try:
            value = await self._redis.get(self.REDIS_MODE_KEY)
        except Exception:
            return default_mode
        if not value:
            return default_mode
        if isinstance(value, bytes):
            return value.decode()
        return str(value)

    def get_config(self, agent: str, mode: str) -> dict[str, Any]:
        return self._config["agents"][agent][mode]

    def _is_anthropic(self, provider: str) -> bool:
        return provider == "anthropic"

    def _get_client(self, provider: str) -> Any:
        if provider in self._clients:
            return self._clients[provider]

        provider_cfg = self._config["providers"][provider]
        api_key = os.environ.get(provider_cfg["api_key_env"], "")
        if not api_key:
            raise RuntimeError(f"missing api key for provider {provider}")

        if self._is_anthropic(provider):
            try:
                from anthropic import AsyncAnthropic
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("anthropic SDK is not installed") from exc
            self._clients[provider] = AsyncAnthropic(api_key=api_key)
        else:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("openai SDK is not installed") from exc
            self._clients[provider] = AsyncOpenAI(
                api_key=api_key,
                base_url=provider_cfg["base_url"],
            )
        return self._clients[provider]

    @staticmethod
    def _estimate_tokens_from_messages(messages: list[dict[str, Any]]) -> int:
        text = "\n".join(str(m.get("content", "")) for m in messages)
        return max(1, len(text) // 4) if text else 0

    @staticmethod
    def _estimate_output_tokens(text: str) -> int:
        return max(1, len(text) // 4) if text else 0

    async def _record_call(
        self,
        *,
        db: AsyncSession | None,
        request_id: UUID | None,
        student_id: int | None,
        agent: str,
        mode: str,
        provider: str,
        model: str,
        latency_ms: int,
        input_tokens: int,
        output_tokens: int,
        is_fallback: bool,
        success: bool,
        error_message: str | None = None,
    ) -> None:
        if db is None or request_id is None:
            return
        await log_model_call(
            db,
            request_id=request_id,
            student_id=student_id,
            agent_name=agent,
            mode=mode,
            provider=provider,
            model=model,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            is_fallback=is_fallback,
            success=success,
            error_message=error_message,
        )

    @staticmethod
    def _extract_system_message(
        messages: list[dict[str, Any]],
    ) -> tuple[str | None, list[dict[str, Any]]]:
        system = None
        filtered = []
        for msg in messages:
            if msg.get("role") == "system":
                system = str(msg.get("content", ""))
            else:
                filtered.append(msg)
        return system, filtered

    async def _call_anthropic(
        self,
        client: Any,
        cfg: dict[str, Any],
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> tuple[str, dict[str, int]]:
        system, non_system = self._extract_system_message(messages)
        params: dict[str, Any] = {
            "model": cfg["model"],
            "messages": non_system,
            "temperature": cfg.get("temperature", 0.0),
            "max_tokens": kwargs.get("max_tokens") or 1200,
        }
        if system:
            params["system"] = system
        response = await client.messages.create(**params)
        content = response.content[0].text if response.content else ""
        input_tokens = (
            getattr(response.usage, "input_tokens", 0)
            or self._estimate_tokens_from_messages(messages)
        )
        output_tokens = (
            getattr(response.usage, "output_tokens", 0)
            or self._estimate_output_tokens(content)
        )
        return content, {"input_tokens": input_tokens, "output_tokens": output_tokens}

    async def _call_with_config(
        self,
        cfg: dict[str, Any],
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> tuple[str, dict[str, int]]:
        client = self._get_client(cfg["provider"])

        if self._is_anthropic(cfg["provider"]):
            return await self._call_anthropic(client, cfg, messages, **kwargs)

        params = {
            "model": cfg["model"],
            "messages": messages,
            "temperature": cfg.get("temperature", 0.0),
        }
        if kwargs.get("response_format") is not None:
            params["response_format"] = kwargs["response_format"]
        if kwargs.get("max_tokens") is not None:
            params["max_tokens"] = kwargs["max_tokens"]

        response = await client.chat.completions.create(**params)
        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", None) or self._estimate_tokens_from_messages(
            messages
        )
        output_tokens = getattr(usage, "completion_tokens", None) or self._estimate_output_tokens(
            content
        )
        return content, {"input_tokens": input_tokens, "output_tokens": output_tokens}

    async def invoke(
        self,
        agent: str,
        messages: list[dict[str, Any]],
        *,
        db: AsyncSession | None = None,
        request_id: UUID | None = None,
        student_id: int | None = None,
        **kwargs: Any,
    ) -> tuple[str, dict[str, Any]]:
        primary_mode = await self.current_mode()
        modes = [primary_mode]
        alternate = "best" if primary_mode == "normal" else "normal"
        if alternate not in modes:
            modes.append(alternate)

        last_exc: Exception | None = None
        for index, mode in enumerate(modes):
            cfg = self.get_config(agent, mode)
            started = perf_counter()
            try:
                content, usage = await self._call_with_config(cfg, messages, **kwargs)
                latency_ms = int((perf_counter() - started) * 1000)
                metadata = {
                    "mode": mode,
                    "provider": cfg["provider"],
                    "model": cfg["model"],
                    "is_fallback": index > 0,
                    "latency_ms": latency_ms,
                    **usage,
                }
                await self._record_call(
                    db=db,
                    request_id=request_id,
                    student_id=student_id,
                    agent=agent,
                    mode=mode,
                    provider=cfg["provider"],
                    model=cfg["model"],
                    latency_ms=latency_ms,
                    input_tokens=usage["input_tokens"],
                    output_tokens=usage["output_tokens"],
                    is_fallback=index > 0,
                    success=True,
                )
                return content, metadata
            except Exception as exc:
                last_exc = exc
                latency_ms = int((perf_counter() - started) * 1000)
                await self._record_call(
                    db=db,
                    request_id=request_id,
                    student_id=student_id,
                    agent=agent,
                    mode=mode,
                    provider=cfg["provider"],
                    model=cfg["model"],
                    latency_ms=latency_ms,
                    input_tokens=self._estimate_tokens_from_messages(messages),
                    output_tokens=0,
                    is_fallback=index > 0,
                    success=False,
                    error_message=str(exc),
                )
        assert last_exc is not None
        raise last_exc

    async def _stream_anthropic(
        self, client: Any, cfg: dict[str, Any], messages: list[dict[str, Any]], **kwargs: Any
    ):
        system, non_system = self._extract_system_message(messages)
        params: dict[str, Any] = {
            "model": cfg["model"],
            "messages": non_system,
            "temperature": cfg.get("temperature", 0.0),
            "max_tokens": kwargs.get("max_tokens") or 1200,
        }
        if system:
            params["system"] = system
        async with client.messages.stream(**params) as stream:
            async for text in stream.text_stream:
                yield text

    async def _stream_with_config(
        self, cfg: dict[str, Any], messages: list[dict[str, Any]], **kwargs: Any
    ):
        client = self._get_client(cfg["provider"])

        if self._is_anthropic(cfg["provider"]):
            async for chunk in self._stream_anthropic(client, cfg, messages, **kwargs):
                yield chunk
            return

        stream = await client.chat.completions.create(
            model=cfg["model"],
            messages=messages,
            temperature=cfg.get("temperature", 0.0),
            stream=True,
            max_tokens=kwargs.get("max_tokens"),
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                yield content

    async def invoke_stream(
        self,
        agent: str,
        messages: list[dict[str, Any]],
        *,
        db: AsyncSession | None = None,
        request_id: UUID | None = None,
        student_id: int | None = None,
        **kwargs: Any,
    ):
        primary_mode = await self.current_mode()
        modes = [primary_mode]
        alternate = "best" if primary_mode == "normal" else "normal"
        if alternate not in modes:
            modes.append(alternate)

        last_exc: Exception | None = None
        for index, mode in enumerate(modes):
            cfg = self.get_config(agent, mode)
            started = perf_counter()
            chunks: list[str] = []
            yielded = False
            try:
                async for chunk in self._stream_with_config(cfg, messages, **kwargs):
                    yielded = True
                    chunks.append(chunk)
                    yield chunk
                latency_ms = int((perf_counter() - started) * 1000)
                output_text = "".join(chunks)
                await self._record_call(
                    db=db,
                    request_id=request_id,
                    student_id=student_id,
                    agent=agent,
                    mode=mode,
                    provider=cfg["provider"],
                    model=cfg["model"],
                    latency_ms=latency_ms,
                    input_tokens=self._estimate_tokens_from_messages(messages),
                    output_tokens=self._estimate_output_tokens(output_text),
                    is_fallback=index > 0,
                    success=True,
                )
                return
            except Exception as exc:
                last_exc = exc
                latency_ms = int((perf_counter() - started) * 1000)
                await self._record_call(
                    db=db,
                    request_id=request_id,
                    student_id=student_id,
                    agent=agent,
                    mode=mode,
                    provider=cfg["provider"],
                    model=cfg["model"],
                    latency_ms=latency_ms,
                    input_tokens=self._estimate_tokens_from_messages(messages),
                    output_tokens=self._estimate_output_tokens("".join(chunks)),
                    is_fallback=index > 0,
                    success=False,
                    error_message=str(exc),
                )
                if yielded:
                    raise
        assert last_exc is not None
        raise last_exc


_router_singleton: ModelRouter | None = None


def get_model_router(redis_client: Any | None = None) -> ModelRouter:
    global _router_singleton
    if _router_singleton is None or redis_client is not None:
        _router_singleton = ModelRouter(settings.MODEL_CONFIG_PATH, redis_client=redis_client)
    return _router_singleton


def reset_model_router() -> None:
    global _router_singleton
    _router_singleton = None
