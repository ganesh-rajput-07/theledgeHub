"""Adapters are tested against fake HTTP transports: no network, no real keys, but the real SDKs."""

import json

import httpx2
import pytest
from anthropic import DefaultHttpxClient as AnthropicHttpClient
from openai import DefaultHttpxClient as OpenAIHttpClient

from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import ChatMessage, LLMAuthError, LLMModelNotFoundError, LLMRateLimitError, LLMRefusalError
from app.llm.mock_provider import MockProvider
from app.llm.openai_provider import OpenAIProvider

MESSAGES = [ChatMessage("user", "Question?")]


def transport(handler):
    requests = []

    def record(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return handler(request)

    return httpx2.MockTransport(record), requests


def anthropic_message(text="Answer [1]", stop_reason="end_turn"):
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 120, "output_tokens": 8},
    }


def anthropic_provider(handler):
    mock, requests = transport(handler)
    return AnthropicProvider("sk-ant-test", timeout=10, http_client=AnthropicHttpClient(transport=mock)), requests


def test_anthropic_generate_sends_system_effort_and_fallbacks():
    provider, requests = anthropic_provider(lambda r: httpx2.Response(200, json=anthropic_message()))
    result = provider.generate("SYSTEM", MESSAGES, "claude-opus-5-5", 16000)

    body = json.loads(requests[0].content)
    assert body["system"] == "SYSTEM"
    assert body["messages"] == [{"role": "user", "content": "Question?"}]
    assert body["output_config"] == {"effort": "medium"}
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in requests[0].headers["anthropic-beta"]
    assert "temperature" not in body
    assert (result.text, result.input_tokens, result.output_tokens) == ("Answer [1]", 120, 8)


def test_anthropic_older_model_gets_plain_request():
    provider, requests = anthropic_provider(lambda r: httpx2.Response(200, json=anthropic_message()))
    provider.generate("S", MESSAGES, "claude-haiku-4-5", 1000)
    body = json.loads(requests[0].content)
    assert "fallbacks" not in body and "output_config" not in body


def test_anthropic_refusal_and_truncation():
    provider, _ = anthropic_provider(lambda r: httpx2.Response(200, json=anthropic_message("", "refusal")))
    with pytest.raises(LLMRefusalError):
        provider.generate("S", MESSAGES, "claude-opus-5-5", 100)

    provider, _ = anthropic_provider(lambda r: httpx2.Response(200, json=anthropic_message("Cut", "max_tokens")))
    assert provider.generate("S", MESSAGES, "claude-opus-5-5", 100).truncated


@pytest.mark.parametrize(
    ("status", "error"),
    [(401, LLMAuthError), (403, LLMAuthError), (404, LLMModelNotFoundError), (429, LLMRateLimitError)],
)
def test_anthropic_errors_are_translated(status, error):
    body = {"type": "error", "error": {"type": "x", "message": "nope"}}
    provider, _ = anthropic_provider(lambda r: httpx2.Response(status, json=body, headers={"retry-after": "0"}))
    with pytest.raises(error):
        provider.generate("S", MESSAGES, "claude-opus-5-5", 100)


def openai_provider(handler):
    mock, requests = transport(handler)
    return OpenAIProvider("sk-test", timeout=10, http_client=OpenAIHttpClient(transport=mock)), requests


def openai_response(text="Answer [1]", status="completed"):
    return {
        "id": "resp_1",
        "object": "response",
        "created_at": 0,
        "model": "gpt-test",
        "status": status,
        "output": [
            {
                "type": "message",
                "id": "m1",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ],
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
        "usage": {
            "input_tokens": 50,
            "output_tokens": 5,
            "total_tokens": 55,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }


def test_openai_generate_uses_responses_api_without_storing():
    provider, requests = openai_provider(lambda r: httpx2.Response(200, json=openai_response()))
    result = provider.generate("SYSTEM", MESSAGES, "gpt-test", 2000)
    body = json.loads(requests[0].content)
    assert requests[0].url.path.endswith("/responses")
    assert body["instructions"] == "SYSTEM" and body["store"] is False and body["max_output_tokens"] == 2000
    assert (result.text, result.input_tokens, result.output_tokens) == ("Answer [1]", 50, 5)


def test_openai_bad_key_and_model_list():
    body = {"error": {"message": "Incorrect API key", "type": "invalid_request_error"}}
    provider, _ = openai_provider(lambda r: httpx2.Response(401, json=body))
    with pytest.raises(LLMAuthError):
        provider.list_models()

    models = {"object": "list", "data": [{"id": "gpt-a", "object": "model", "created": 0, "owned_by": "o"}]}
    provider, _ = openai_provider(lambda r: httpx2.Response(200, json=models))
    assert provider.list_models() == ["gpt-a"]


def test_mock_provider_cites_first_source_or_reports_not_found():
    mock = MockProvider()
    prompt = '<sources>\n<source id="1" document="a.pdf" page="2">\nRevenue grew 14%. More text.\n</source>\n</sources>'
    assert mock.generate("S", [ChatMessage("user", prompt)], "mock-1", 100).text.endswith(
        "Revenue grew 14%. More text. [1]"
    )
    assert mock.generate("S", [ChatMessage("user", "no sources")], "mock-1", 100).text == "NOT_FOUND"


def test_mock_provider_rewrites_follow_ups():
    prompt = (
        "<conversation>\nuser: What was revenue in 2025?\nassistant: INR 190 crore [1].\n</conversation>"
        "\n\nLatest message: And 2024?"
    )
    assert MockProvider().generate("S", [ChatMessage("user", prompt)], "mock-1", 100).text == (
        "What was revenue in 2025? And 2024?"
    )
