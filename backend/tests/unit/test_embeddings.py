import numpy as np

from app.rag.embeddings import get_embedding_provider


def test_local_provider_produces_normalized_384d_vectors():
    provider = get_embedding_provider()
    vectors = provider.embed_documents(["Revenue grew 20%.", "Employees get 20 days of leave."])
    assert provider.dimension == 384
    assert len(vectors) == 2 and all(len(v) == 384 for v in vectors)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)


def test_semantically_similar_texts_score_higher():
    provider = get_embedding_provider()
    query = np.array(provider.embed_query("How much paid vacation do staff get?"))
    leave, revenue = np.array(provider.embed_documents(["Employees get 20 days of paid leave.", "Revenue grew 20%."]))
    assert query @ leave > query @ revenue


def test_empty_batch():
    assert get_embedding_provider().embed_documents([]) == []
