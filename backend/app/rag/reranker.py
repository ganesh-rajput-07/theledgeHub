from functools import lru_cache

from app.core.config import get_settings


class CrossEncoderReranker:
    """Re-scores (question, passage) pairs together. Much better than embedding similarity at telling the
    page that *answers* a question from pages that merely share its words. Runs locally on CPU."""

    def __init__(self, model_name: str):
        from sentence_transformers import CrossEncoder

        self.model_name = model_name
        self._model = CrossEncoder(model_name, device="cpu")

    def scores(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        return [float(s) for s in self._model.predict([(query, p) for p in passages], show_progress_bar=False)]


@lru_cache
def get_reranker() -> CrossEncoderReranker:
    return CrossEncoderReranker(get_settings().reranker_model)
