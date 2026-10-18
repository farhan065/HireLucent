"""The vector store (ChromaDB): saving, searching and deleting text chunks.

Each kind of content has its own collection. The collection is always
chosen by our code, never by the AI model. Embeddings are created with the
AI access layer, so the embedding model is set in one place.
"""

from functools import lru_cache
from typing import Any

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

from app.ai import client as ai_client
from app.core.config import get_settings

JD_REFERENCES = "jd_references"
RAG_DOCUMENTS = "rag_documents"
QUESTION_BANK = "question_bank"
CV_EMBEDDINGS = "cv_embeddings"


@lru_cache
def get_client() -> ClientAPI:
    settings = get_settings()
    return chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)


def get_collection(name: str) -> Collection:
    """Open a collection, creating it on first use.

    The embedding model's name is stored with the collection. Vectors from
    different models cannot be mixed, so this records which one was used.
    """
    return get_client().get_or_create_collection(
        name=name,
        metadata={"embedding_model": get_settings().embedding_model},
        configuration={"hnsw": {"space": "cosine"}},
        embedding_function=None,
    )


def add_chunks(
    collection_name: str,
    document_id: int,
    chunks: list[str],
    metadata: dict[str, Any],
    first_index: int = 0,
) -> None:
    """Embed the chunks and store them, tagged with the document they came from.

    first_index numbers the chunks after the ones the document already has,
    when more are added to it later.
    """
    if not chunks:
        return
    get_collection(collection_name).add(
        ids=[f"doc-{document_id}-{first_index + index}" for index in range(len(chunks))],
        documents=chunks,
        embeddings=ai_client.embed_texts(chunks),
        metadatas=[{**metadata, "document_id": document_id} for _ in chunks],
    )


def delete_document(collection_name: str, document_id: int) -> None:
    """Remove every chunk that came from one document."""
    get_collection(collection_name).delete(where={"document_id": document_id})


def search(
    collection_name: str,
    query: str,
    limit: int = 4,
    where: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return the chunks closest in meaning to the query, best first."""
    result = get_collection(collection_name).query(
        query_embeddings=[ai_client.embed_query(query)],
        n_results=limit,
        where=where,
    )
    return [
        {"text": text, "metadata": metadata, "distance": distance}
        for text, metadata, distance in zip(
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
            strict=True,
        )
    ]
