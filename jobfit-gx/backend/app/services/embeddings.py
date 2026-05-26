from functools import lru_cache

import chromadb
from chromadb.api import ClientAPI
from sentence_transformers import SentenceTransformer

from app.config import get_settings
from app.models import CVChunk

COLLECTION_NAME = "jobfit_cv_chunks"


class EmbeddingService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._model: SentenceTransformer | None = None
        self._client: ClientAPI | None = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.settings.embedding_model)
        return self._model

    @property
    def client(self) -> ClientAPI:
        if self._client is None:
            self._client = chromadb.HttpClient(host=self.settings.chroma_host, port=self.settings.chroma_port)
        return self._client

    def health(self) -> str:
        try:
            self.client.heartbeat()
            return "ok"
        except Exception:
            return "unreachable"

    def model_health(self) -> str:
        try:
            _ = self.model
            return "ok"
        except Exception:
            return "unavailable"

    def add_chunks(self, chunks: list[CVChunk]) -> None:
        if not chunks:
            return
        collection = self.client.get_or_create_collection(COLLECTION_NAME)
        texts = [chunk.text for chunk in chunks]
        embeddings = self.model.encode(texts, normalize_embeddings=True).tolist()
        collection.add(
            ids=[chunk.id for chunk in chunks],
            embeddings=embeddings,
            documents=texts,
            metadatas=[{"cv_id": chunk.cv_id, "section": chunk.section} for chunk in chunks],
        )
        for chunk in chunks:
            chunk.embedding_id = chunk.id

    def delete_cv(self, cv_id: str) -> None:
        try:
            collection = self.client.get_or_create_collection(COLLECTION_NAME)
            collection.delete(where={"cv_id": cv_id})
        except Exception:
            return

    def query_cv(self, cv_id: str, query: str, limit: int = 6) -> list[str]:
        collection = self.client.get_or_create_collection(COLLECTION_NAME)
        embedding = self.model.encode([query], normalize_embeddings=True).tolist()[0]
        results = collection.query(query_embeddings=[embedding], n_results=limit, where={"cv_id": cv_id})
        return [doc for doc in (results.get("documents") or [[]])[0] if doc]


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()

