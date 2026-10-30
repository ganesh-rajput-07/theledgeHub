from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings


class EmbeddingProvider(Protocol):
    """Provider-independent embedding interface. Queries and documents are embedded separately
    because some models (e5, bge) expect different prefixes for each."""

    model_name: str
    dimension: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class LocalEmbeddingProvider:
    """Sentence Transformers on CPU: free, private, and no customer API key needed."""

    def __init__(self, model_name: str, batch_size: int = 32):
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.batch_size = batch_size
        self._model = SentenceTransformer(model_name, device="cpu")
        self.dimension = self._model.get_embedding_dimension()

    def _encode(self, texts: list[str]) -> list[list[float]]:
        # Normalized vectors make cosine distance well-behaved and comparable across queries.
        vectors = self._model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts) if texts else []

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text])[0]


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    provider = LocalEmbeddingProvider(settings.embedding_model)
    if provider.dimension != settings.embedding_dimension:
        raise RuntimeError(
            f"{settings.embedding_model} produces {provider.dimension}-d vectors but the database column "
            f"is VECTOR({settings.embedding_dimension}); changing models needs a re-embedding migration"
        )
    return provider
