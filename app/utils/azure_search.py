"""
Azure AI Search client — provides vector and hybrid search against Azure AI Search.

Used by the Retriever agent for knowledge retrieval.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from app.utils.logger import get_logger

logger = get_logger("azure_search")

_search_client = None


def get_search_client():
    """
    Return a shared Azure AI Search SearchClient instance.

    Environment / config variables used:
        AZURE_SEARCH_ENDPOINT
        AZURE_SEARCH_KEY  / AZURE_SEARCH_API_KEY
        AZURE_SEARCH_INDEX / AZURE_SEARCH_INDEX_NAME
    """
    global _search_client
    if _search_client is not None:
        return _search_client

    try:
        from azure.search.documents import SearchClient
        from azure.core.credentials import AzureKeyCredential
        from app.utils.config import settings

        endpoint = settings.azure_search.endpoint or os.getenv("AZURE_SEARCH_ENDPOINT", "")
        key = settings.azure_search.api_key or os.getenv("AZURE_SEARCH_KEY", "")
        index = settings.azure_search.index_name or os.getenv("AZURE_SEARCH_INDEX", "knowledge-index")

        if not endpoint or not key:
            logger.warning("Azure AI Search credentials not configured — search unavailable")
            return None

        _search_client = SearchClient(
            endpoint=endpoint,
            index_name=index,
            credential=AzureKeyCredential(key),
        )

        logger.info(
            "Azure AI Search client created",
            event_type="search_factory",
            metadata={"endpoint": endpoint, "index": index},
        )
        return _search_client

    except ImportError:
        logger.warning("azure-search-documents not installed")
        return None
    except Exception as e:
        logger.error(f"Failed to create Azure Search client: {e}", exc_info=True)
        return None


async def azure_search(
    query: str,
    top: int = 5,
    user_id: str = "",
) -> List[Dict[str, Any]]:
    """
    Search Azure AI Search and return results normalized to the same
    format as the local vector DB (list of dicts with id, content, score, …).

    Args:
        query: Natural-language search query.
        top: Maximum number of results to return.
        user_id: Optional user filter.

    Returns:
        List of result dicts: [{id, content, score, source_filename, …}]
    """
    client = get_search_client()
    if client is None:
        return []

    try:
        filter_expr = f"user_id eq '{user_id}'" if user_id else None

        results = client.search(
            search_text=query,
            top=top,
            filter=filter_expr,
        )

        normalized: List[Dict[str, Any]] = []
        for r in results:
            normalized.append({
                "id": r.get("id", r.get("chunk_id", "")),
                "content": r.get("content", r.get("chunk_content", "")),
                "score": r.get("@search.score", 0.0),
                "source_filename": r.get("source_filename", r.get("title", "azure_search")),
                "topic": r.get("topic", "general"),
                "user_id": r.get("user_id", user_id),
            })

        logger.info(
            f"Azure AI Search returned {len(normalized)} results",
            event_type="azure_search_results",
            metadata={"query_preview": query[:100], "results": len(normalized)},
        )
        return normalized

    except Exception as e:
        logger.error(f"Azure AI Search query failed: {e}", exc_info=True)
        return []
