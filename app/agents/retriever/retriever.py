"""
Retriever Agent — responsible for memory access and context assembly.

The Retriever:
1. Receives the user query from the pipeline
2. Performs query expansion using the LLM
3. Queries both vector and structured memory
4. Assembles a ranked context package
5. Stores the context in the agent state
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List

from app.memory.memory_manager import MemoryManager
from app.state.agent_state import AgentState, add_log_entry
from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("retriever")


class RetrieverAgent:
    """
    The Retriever Agent fetches relevant context from memory systems.

    It performs:
    - Query expansion (generate alternative search terms)
    - Vector search (semantic similarity)
    - Structured data retrieval (tasks, habits, documents, etc.)
    - Context assembly and ranking
    """

    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager
        self._llm_client = None

    def _get_llm_client(self):
        """Lazy-initialize Azure OpenAI client."""
        if self._llm_client is None:
            try:
                from openai import AzureOpenAI
                self._llm_client = AzureOpenAI(
                    azure_endpoint=settings.azure_openai.endpoint,
                    api_key=settings.azure_openai.api_key,
                    api_version=settings.azure_openai.api_version,
                )
            except Exception as e:
                logger.warning(f"LLM client not available for query expansion: {e}")
                return None
        return self._llm_client

    async def expand_query(self, query: str) -> List[str]:
        """
        Use the LLM to generate expanded search queries for better retrieval.

        Given "neural networks", might produce:
        ["neural networks", "deep learning", "artificial neurons", "backpropagation"]
        """
        client = self._get_llm_client()
        if not client:
            # Fallback: just return the original query
            return [query]

        try:
            response = client.chat.completions.create(
                model=settings.azure_openai.chat_deployment,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a search query expansion assistant. "
                            "Given a user query, generate 3-5 alternative search queries that would help find relevant information. "
                            "Return ONLY a JSON array of strings. No explanation."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                temperature=0.3,
                max_tokens=200,
            )

            content = response.choices[0].message.content.strip()
            # Parse JSON array
            expanded = json.loads(content)
            if isinstance(expanded, list):
                # Always include the original query
                if query not in expanded:
                    expanded.insert(0, query)
                return expanded[:5]

        except Exception as e:
            logger.warning(f"Query expansion failed, using original query: {e}")

        return [query]

    async def retrieve(self, state: AgentState) -> AgentState:
        """
        Main retrieval pipeline — the workflow graph node function.

        Steps:
        1. Extract query from state
        2. Expand the query
        3. Search vector database with expanded queries
        4. Retrieve structured data
        5. Assemble and store context in state

        Args:
            state: The current AgentState.

        Returns:
            Updated AgentState with memory_context populated.
        """
        logger.set_context(
            request_id=state.get("system", {}).get("request_id", ""),
            user_id=state.get("system", {}).get("user_id", ""),
            agent_name="retriever",
        )
        logger.log_agent_start("retriever")
        start_time = time.time()

        user_id = state.get("system", {}).get("user_id", "")
        query = state.get("user_request", {}).get("validated_input", "")

        if not query:
            query = state.get("user_request", {}).get("raw_input", "")

        state = add_log_entry(state, "retriever", "retrieval_start", f"Query: {query[:100]}")

        # 1. Query Expansion
        expanded_queries = await self.expand_query(query)
        state = add_log_entry(state, "retriever", "query_expanded", f"Expanded to {len(expanded_queries)} queries")

        # 2. Vector Search — search with all expanded queries and deduplicate
        all_chunks = []
        seen_ids = set()

        for eq in expanded_queries:
            results = await self.memory.search_knowledge(
                query=eq,
                user_id=user_id,
                top_k=settings.app.top_k_results,
            )
            for r in results:
                chunk_id = r.get("id", "")
                if chunk_id not in seen_ids:
                    seen_ids.add(chunk_id)
                    all_chunks.append(r)

        # Sort by score (descending) and limit
        all_chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
        top_chunks = all_chunks[: settings.app.top_k_results]

        # 3. Structured Data Retrieval
        context = await self.memory.assemble_context(user_id, query)

        # Override with our expanded search results
        context["vector_memory"]["knowledge_chunks"] = top_chunks

        # 4. Update retrieval summary
        parts = []
        sm = context.get("structured_memory", {})
        if sm.get("tasks"):
            parts.append(f"{len(sm['tasks'])} tasks")
        if sm.get("reminders"):
            parts.append(f"{len(sm['reminders'])} reminders")
        if sm.get("habits"):
            parts.append(f"{len(sm['habits'])} habits")
        if sm.get("documents"):
            parts.append(f"{len(sm['documents'])} documents")
        if top_chunks:
            parts.append(f"{len(top_chunks)} relevant knowledge chunks")

        context["retrieval_summary"] = "Retrieved: " + ", ".join(parts) if parts else "No relevant context found"

        # 5. Guard context window — limit total context size
        context = self._guard_context_window(context)

        # Update state
        system = {**state.get("system", {}), "current_stage": "planning"}
        state = {**state, "memory_context": context, "system": system}
        state = add_log_entry(state, "retriever", "retrieval_complete", context["retrieval_summary"])

        duration_ms = (time.time() - start_time) * 1000
        logger.log_agent_end("retriever", context["retrieval_summary"], duration_ms)

        return state

    def _guard_context_window(self, context: Dict[str, Any], max_chars: int = 50000) -> Dict[str, Any]:
        """
        Ensure the total context size doesn't exceed the model's context window.
        Trims lower-ranked chunks if necessary.
        """
        total_chars = 0

        # Count structured memory size
        for key, value in context.get("structured_memory", {}).items():
            total_chars += len(json.dumps(value, default=str))

        # Count vector memory size and trim if needed
        chunks = context.get("vector_memory", {}).get("knowledge_chunks", [])
        kept_chunks = []
        for chunk in chunks:
            chunk_size = len(chunk.get("content", ""))
            if total_chars + chunk_size <= max_chars:
                kept_chunks.append(chunk)
                total_chars += chunk_size
            else:
                break

        context["vector_memory"]["knowledge_chunks"] = kept_chunks

        if len(kept_chunks) < len(chunks):
            logger.info(
                f"Context window guard: trimmed from {len(chunks)} to {len(kept_chunks)} chunks",
                event_type="context_trimmed",
            )

        return context
