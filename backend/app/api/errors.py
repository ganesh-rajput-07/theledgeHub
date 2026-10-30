from fastapi import HTTPException, status

from app.llm.base import (
    LLMAuthError,
    LLMError,
    LLMModelNotFoundError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMUnavailableError,
)


def llm_http_error(exc: LLMError) -> HTTPException:
    """Map provider failures to responses that tell the customer what to fix."""
    if isinstance(exc, LLMUnavailableError):
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc), headers={"Retry-After": "30"})
    if isinstance(exc, LLMAuthError):
        code = status.HTTP_400_BAD_REQUEST  # their key is wrong; our API auth is fine
    elif isinstance(exc, LLMRateLimitError):
        code = status.HTTP_429_TOO_MANY_REQUESTS
    elif isinstance(exc, LLMModelNotFoundError | LLMRefusalError):
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
    else:
        code = status.HTTP_502_BAD_GATEWAY
    return HTTPException(code, str(exc))
