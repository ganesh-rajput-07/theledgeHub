import re

from app.llm.base import ChatMessage, LLMResponse

_FIRST_SOURCE = re.compile(r'<source id="1"[^>]*>\s*(.*?)\s*</source>', re.DOTALL)


class MockProvider:
    """Deterministic offline provider for development and tests (disabled in production).
    Quotes the start of source [1] with a citation, or answers NOT_FOUND when there are no sources."""

    name = "mock"
    MODEL = "mock-1"

    def list_models(self) -> list[str]:
        return [self.MODEL]

    def generate(self, system: str, messages: list[ChatMessage], model: str, max_tokens: int) -> LLMResponse:
        prompt = messages[-1].content
        if prompt.startswith("<conversation>"):  # follow-up rewrite: previous question + latest message
            previous = re.findall(r"^user: (.*)$", prompt, re.MULTILINE)[-1:]
            latest = prompt.rsplit("Latest message: ", 1)[-1]
            text = " ".join([*previous, latest])
            return LLMResponse(
                text=text, model=model, input_tokens=len(prompt.split()), output_tokens=len(text.split())
            )
        match = _FIRST_SOURCE.search(prompt)
        if not match:
            text = "NOT_FOUND"
        else:
            text = f"According to the documents: {match.group(1)[:200].strip()} [1]"
        return LLMResponse(text=text, model=model, input_tokens=len(prompt.split()), output_tokens=len(text.split()))
