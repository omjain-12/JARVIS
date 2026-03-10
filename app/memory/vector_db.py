"""Vector Database — Azure AI Search integration for semantic knowledge retrieval."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("vector_db")


class VectorDB:
    """Azure AI Search vector database client."""

    def __init__(self):
        self.endpoint = settings.azure_search.endpoint
        self.api_key = settings.azure_search.api_key
        self.index_name = settings.azure_search.index_name
        self._client = None
        self._index_client = None

    def _get_search_client(self):
        """Lazy-initialize the Azure Search client."""
        if self._client is None:
            from azure.search.documents import SearchClient
            from azure.core.credentials import AzureKeyCredential

            if not self.endpoint or not self.api_key:
                raise RuntimeError(
                    "Azure AI Search credentials not configured. "
                    "Set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY."
                )

            self._client = SearchClient(
                endpoint=self.endpoint,
                index_name=self.index_name,
                credential=AzureKeyCredential(self.api_key),
            )
        return self._client

    def _get_index_client(self):
        """Lazy-initialize the Azure Search Index client."""
        if self._index_client is None:
            from azure.search.documents.indexes import SearchIndexClient
            from azure.core.credentials import AzureKeyCredential

            if not self.endpoint or not self.api_key:
                raise RuntimeError(
                    "Azure AI Search credentials not configured. "
                    "Set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY."
                )

            self._index_client = SearchIndexClient(
                endpoint=self.endpoint,
                credential=AzureKeyCredential(self.api_key),
            )
        return self._index_client

    async def create_index(self):
        """Create the knowledge search index in Azure AI Search if it doesn't exist."""
        try:
            from azure.search.documents.indexes.models import (
                SearchIndex,
                SearchField,
                SearchFieldDataType,
                SimpleField,
                SearchableField,
                VectorSearch,
                HnswAlgorithmConfiguration,
                HnswParameters,
                VectorSearchProfile,
                SearchField as VectorField,
            )

            index_client = self._get_index_client()

            fields = [
                SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
                SimpleField(name="document_id", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="user_id", type=SearchFieldDataType.String, filterable=True),
                SearchableField(name="content", type=SearchFieldDataType.String),
                SimpleField(name="topic", type=SearchFieldDataType.String, filterable=True, facetable=True),
                SimpleField(name="source_filename", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="chunk_index", type=SearchFieldDataType.Int32, sortable=True),
                SimpleField(name="page_number", type=SearchFieldDataType.Int32, sortable=True),
                SimpleField(name="section_heading", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="created_at", type=SearchFieldDataType.String, sortable=True),
                SearchField(
                    name="embedding",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True,
                    vector_search_dimensions=settings.azure_openai.embedding_dimensions,
                    vector_search_profile_name="default-vector-profile",
                ),
            ]

            vector_search = VectorSearch(
                algorithms=[
                    HnswAlgorithmConfiguration(
                        name="default-hnsw",
                        parameters=HnswParameters(m=4, ef_construction=400, ef_search=500),
                    ),
                ],
                profiles=[
                    VectorSearchProfile(name="default-vector-profile", algorithm_configuration_name="default-hnsw"),
                ],
            )

            index = SearchIndex(name=self.index_name, fields=fields, vector_search=vector_search)
            index_client.create_or_update_index(index)
            logger.info(f"Search index '{self.index_name}' created/updated successfully", event_type="index_created")

        except Exception as e:
            logger.error(f"Failed to create search index: {e}", exc_info=True)

    async def store_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """Store document chunks with embeddings in the search index."""
        client = self._get_search_client()

        try:
            documents = []
            for chunk in chunks:
                doc = {
                    "id": str(uuid.uuid4()),
                    "document_id": chunk.get("document_id", ""),
                    "user_id": chunk.get("user_id", ""),
                    "content": chunk.get("content", ""),
                    "embedding": chunk.get("embedding", []),
                    "topic": chunk.get("topic", "general"),
                    "source_filename": chunk.get("source_filename", ""),
                    "chunk_index": chunk.get("chunk_index", 0),
                    "page_number": chunk.get("page_number", 0),
                    "section_heading": chunk.get("section_heading", ""),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                documents.append(doc)

            # Upload in batches of 100
            batch_size = 100
            indexed_count = 0
            for i in range(0, len(documents), batch_size):
                batch = documents[i : i + batch_size]
                result = client.upload_documents(documents=batch)
                indexed_count += sum(1 for r in result if r.succeeded)

            logger.info(
                f"Indexed {indexed_count}/{len(chunks)} chunks",
                event_type="chunks_indexed",
                metadata={"total": len(chunks), "indexed": indexed_count},
            )
            return indexed_count

        except Exception as e:
            logger.error(f"Failed to store chunks in Azure Search: {e}", exc_info=True)
            raise

    async def search(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        user_id: str = "",
        top_k: int = 7,
        topic_filter: str = "",
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search (keyword + vector) against the knowledge index."""
        client = self._get_search_client()

        try:
            from azure.search.documents.models import VectorizedQuery

            # Build filter
            filters = []
            if user_id:
                filters.append(f"user_id eq '{user_id}'")
            if topic_filter:
                filters.append(f"topic eq '{topic_filter}'")
            filter_str = " and ".join(filters) if filters else None

            # Build vector query
            vector_queries = []
            if query_embedding:
                vector_queries.append(
                    VectorizedQuery(
                        vector=query_embedding,
                        k_nearest_neighbors=top_k,
                        fields="embedding",
                    )
                )

            results = client.search(
                search_text=query,
                vector_queries=vector_queries if vector_queries else None,
                filter=filter_str,
                top=top_k,
                select=["id", "document_id", "content", "topic", "source_filename",
                        "chunk_index", "page_number", "section_heading"],
            )

            search_results = []
            for result in results:
                search_results.append({
                    "id": result["id"],
                    "document_id": result.get("document_id", ""),
                    "content": result.get("content", ""),
                    "topic": result.get("topic", ""),
                    "source_filename": result.get("source_filename", ""),
                    "chunk_index": result.get("chunk_index", 0),
                    "page_number": result.get("page_number", 0),
                    "section_heading": result.get("section_heading", ""),
                    "score": result.get("@search.score", 0.0),
                })

            logger.info(
                f"Search returned {len(search_results)} results",
                event_type="vector_search",
                metadata={"query_preview": query[:100], "results": len(search_results)},
            )
            return search_results

        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            raise

    async def delete_document_chunks(self, document_id: str):
        """Delete all chunks belonging to a specific document."""
        client = self._get_search_client()

        try:
            # Search for all chunks of this document
            results = client.search(
                search_text="*",
                filter=f"document_id eq '{document_id}'",
                select=["id"],
                top=10000,
            )
            doc_ids = [{"id": r["id"]} for r in results]
            if doc_ids:
                client.delete_documents(documents=doc_ids)
                logger.info(f"Deleted {len(doc_ids)} chunks for document {document_id}")
        except Exception as e:
            logger.error(f"Failed to delete chunks: {e}", exc_info=True)
