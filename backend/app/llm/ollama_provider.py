import re

import httpx
import ollama

from app.llm.base import ChatMessage, LLMModelNotFoundError, LLMProviderError, LLMResponse

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


class OllamaProvider:
    """Local models via Ollama: free and private, no customer key needed."""

    name = "ollama"

    def __init__(self, base_url: str, timeout: float):
        self._client = ollama.Client(host=base_url, timeout=timeout)

    def list_models(self) -> list[str]:
        try:
            return [model.model for model in self._client.list().models]
        except (httpx.HTTPError, ConnectionError) as exc:
            raise LLMProviderError("Could not reach the Ollama server") from exc

    def generate(self, system: str, messages: list[ChatMessage], model: str, max_tokens: int) -> LLMResponse:
        chat = [{"role": "system", "content": system}] + [{"role": m.role, "content": m.content} for m in messages]
        try:
            try:
                # Reasoning models (qwen3, deepseek-r1) think for a long time on CPU; RAG answers don't need it.
                response = self._chat(model, chat, max_tokens, think=False)
            except ollama.ResponseError as exc:
                if "think" not in str(exc).lower():
                    raise
                response = self._chat(model, chat, max_tokens, think=None)
        except ollama.ResponseError as exc:
            if exc.status_code == 404:
                raise LLMModelNotFoundError(f"Ollama model '{model}' is not pulled") from exc
            raise LLMProviderError(f"Ollama error: {exc.error}") from exc
        except (httpx.HTTPError, ConnectionError) as exc:
            raise LLMProviderError("Could not reach the Ollama server") from exc

        return LLMResponse(
            text=_THINK_BLOCK.sub("", response.message.content or "").strip(),
            model=model,
            input_tokens=response.prompt_eval_count,
            output_tokens=response.eval_count,
            truncated=response.done_reason == "length",
        )

    def _chat(self, model, messages, max_tokens, think):
        kwargs = {"think": think} if think is not None else {}
        return self._client.chat(model=model, messages=messages, options={"num_predict": max_tokens}, **kwargs)
