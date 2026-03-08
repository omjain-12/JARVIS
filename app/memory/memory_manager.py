"""
Memory Manager — unified interface for both structured and vector memory systems.

The Memory Manager provides a single entry point for all memory operations.
It coordinates between the structured database (SQLAlchemy) and the vector
database (Azure AI Search) to assemble complete context packages for agents.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.memory.structured_db import StructuredDB
from app.memory.vector_db import VectorDB
from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("memory_manager")


class MemoryManager:
    """
    Unified memory interface that coordinates:
    - Structured DB (tasks, reminders, habits, documents, etc.)
    - Vector DB (knowledge chunks, semantic search)
    - Embedding generation via Azure OpenAI
    """

    def __init__(self):
        self.structured_db = StructuredDB()
        self.vector_db = VectorDB()
        self._embedding_client = None

    async def initialize(self):
        """Initialize both memory systems."""
        await self.structured_db.initialize()
        await self.vector_db.create_index()
        logger.info("Memory Manager initialized", event_type="memory_init")

    async def close(self):
        """Shutdown memory systems."""
        await self.structured_db.close()

    # ── Embedding Generation ──

    def _get_embedding_client(self):
        """Lazy-initialize the Azure OpenAI embedding client."""
        if self._embedding_client is None:
            from openai import AzureOpenAI
            from app.utils.azure_llm import _normalize_azure_endpoint

            self._embedding_client = AzureOpenAI(
                azure_endpoint=_normalize_azure_endpoint(settings.azure_openai.endpoint),
                api_key=settings.azure_openai.api_key,
                api_version=settings.azure_openai.api_version,
            )
        return self._embedding_client

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate an embedding vector for the given text using Azure OpenAI.

        Args:
            text: The text to embed.

        Returns:
            A list of floats representing the embedding vector.
        """
        client = self._get_embedding_client()

        start = time.time()
        response = client.embeddings.create(
            input=text,
            model=settings.azure_openai.embedding_deployment,
            dimensions=settings.azure_openai.embedding_dimensions,
        )
        latency = (time.time() - start) * 1000
        embedding = response.data[0].embedding

        logger.log_llm_call(
            model=settings.azure_openai.embedding_deployment,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=0,
            latency_ms=latency,
        )
        return embedding

    # ── Document Chunk Operations ──

    async def store_document_chunks(
        self,
        chunks: List[Dict[str, Any]],
        document_id: str,
        user_id: str,
        source_filename: str,
    ) -> int:
        """
        Generate embeddings for chunks and store them in the vector database.

        Args:
            chunks: List of dicts with 'content' and optional metadata.
            document_id: The parent document ID.
            user_id: The owning user ID.
            source_filename: Original filename.

        Returns:
            Number of chunks successfully stored.
        """
        enriched_chunks = []
        for i, chunk in enumerate(chunks):
            content = chunk.get("content", "")
            if not content.strip():
                continue

            embedding = await self.generate_embedding(content)

            enriched_chunks.append({
                "content": content,
                "embedding": embedding,
                "document_id": document_id,
                "user_id": user_id,
                "source_filename": source_filename,
                "chunk_index": i,
                "topic": chunk.get("topic", "general"),
                "page_number": chunk.get("page_number", 0),
                "section_heading": chunk.get("section_heading", ""),
            })

        count = await self.vector_db.store_chunks(enriched_chunks)
        logger.info(
            f"Stored {count} chunks for document {document_id}",
            event_type="chunks_stored",
            metadata={"document_id": document_id, "count": count},
        )
        return count

    async def search_knowledge(
        self,
        query: str,
        user_id: str,
        top_k: int = 0,
        topic_filter: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Search the vector database for relevant knowledge chunks.

        Args:
            query: Natural language query.
            user_id: Scope results to this user.
            top_k: Number of results (defaults to config value).
            topic_filter: Optional topic filter.

        Returns:
            List of matching chunks with content and metadata.
        """
        if not top_k:
            top_k = settings.app.top_k_results

        query_embedding = await self.generate_embedding(query)

        results = await self.vector_db.search(
            query=query,
            query_embedding=query_embedding,
            user_id=user_id,
            top_k=top_k,
            topic_filter=topic_filter,
        )

        logger.info(
            f"Knowledge search returned {len(results)} results",
            event_type="knowledge_search",
            metadata={"query_preview": query[:100], "results": len(results)},
        )
        return results

    # ── Context Assembly ──

    async def assemble_context(self, user_id: str, query: str = "") -> Dict[str, Any]:
        """
        Assemble a comprehensive context package for the agents.
        Combines structured data and vector search results.

        Args:
            user_id: The user to scope data to.
            query: Optional query for relevance-based vector retrieval.

        Returns:
            A context dict matching the MemoryContext state shape.
        """
        # Structured data retrieval
        tasks = await self.structured_db.get_tasks(user_id)
        reminders = await self.structured_db.get_reminders(user_id)
        habits = await self.structured_db.get_habits(user_id)
        contacts = await self.structured_db.get_contacts(user_id)
        calendar = await self.structured_db.get_calendar_events(user_id)
        preferences = await self.structured_db.get_preferences(user_id)
        goals = await self.structured_db.get_goals(user_id)
        documents = await self.structured_db.get_documents(user_id)

        # Vector retrieval
        knowledge_chunks = []
        if query:
            knowledge_chunks = await self.search_knowledge(query, user_id)

        # Retrieve stored behavior patterns from vector DB
        behavior_patterns = []
        try:
            behavior_patterns = await self.search_knowledge(
                query="behavior_pattern",
                user_id=user_id,
                top_k=20,
                topic_filter="behavior_pattern",
            )
        except Exception as e:
            logger.warning(f"Failed to retrieve behavior patterns: {e}")

        # Extract learned facts from user preferences
        learned_facts = []
        if preferences:
            prefs_dict = preferences[0] if isinstance(preferences, list) and preferences else {}
            if isinstance(prefs_dict, dict):
                learned_facts = list(prefs_dict.get("learned_facts", []))

        conversation_history = await self.structured_db.get_conversation_history(user_id, limit=10)

        # Build summary
        parts = []
        if tasks:
            parts.append(f"{len(tasks)} active tasks")
        if reminders:
            parts.append(f"{len(reminders)} pending reminders")
        if habits:
            parts.append(f"{len(habits)} tracked habits")
        if knowledge_chunks:
            parts.append(f"{len(knowledge_chunks)} relevant knowledge chunks")
        if documents:
            parts.append(f"{len(documents)} documents")
        if behavior_patterns:
            parts.append(f"{len(behavior_patterns)} behavior patterns")
        if learned_facts:
            parts.append(f"{len(learned_facts)} learned facts")

        retrieval_summary = "Context: " + ", ".join(parts) if parts else "No context available"

        context = {
            "structured_memory": {
                "tasks": tasks,
                "reminders": reminders,
                "habits": habits,
                "contacts": contacts,
                "calendar": calendar,
                "preferences": preferences,
                "goals": goals,
                "documents": documents,
                "learned_facts": learned_facts,
            },
            "vector_memory": {
                "notes": [],
                "conversation_history": conversation_history,
                "behavior_patterns": behavior_patterns,
                "past_decisions": [],
                "knowledge_chunks": knowledge_chunks,
            },
            "retrieval_summary": retrieval_summary,
        }

        logger.info(
            "Context assembled",
            event_type="context_assembled",
            metadata={"summary": retrieval_summary},
        )
        return context

    # ── Convenience: Structured DB passthrough methods ──

    async def create_user(self, name: str, email: str, password_hash: str) -> Dict[str, Any]:
        return await self.structured_db.create_user(name, email, password_hash)

    async def get_user_by_email(self, email: str):
        return await self.structured_db.get_user_by_email(email)

    async def get_user_by_id(self, user_id: str):
        return await self.structured_db.get_user_by_id(user_id)

    async def create_document(self, user_id: str, filename: str, file_type: str, blob_url: str = ""):
        return await self.structured_db.create_document(user_id, filename, file_type, blob_url)

    async def update_document_status(self, document_id: str, status: str, chunk_count: int = 0):
        return await self.structured_db.update_document_status(document_id, status, chunk_count)

    async def get_documents(self, user_id: str):
        return await self.structured_db.get_documents(user_id)

    async def get_document(self, document_id: str):
        return await self.structured_db.get_document(document_id)

    async def create_task(self, user_id: str, title: str, **kwargs):
        return await self.structured_db.create_task(user_id, title, **kwargs)

    async def get_tasks(self, user_id: str, status: str = ""):
        return await self.structured_db.get_tasks(user_id, status)

    async def create_reminder(self, user_id: str, title: str, message: str, remind_at):
        return await self.structured_db.create_reminder(user_id, title, message, remind_at)

    async def get_reminders(self, user_id: str):
        return await self.structured_db.get_reminders(user_id)

    async def create_habit(self, user_id: str, name: str, **kwargs):
        return await self.structured_db.create_habit(user_id, name, **kwargs)

    async def log_habit(self, habit_id: str, notes: str = ""):
        return await self.structured_db.log_habit(habit_id, notes)

    async def get_habits(self, user_id: str):
        return await self.structured_db.get_habits(user_id)

    async def save_conversation(self, user_id: str, session_id: str, role: str, content: str, metadata: dict = None):
        return await self.structured_db.save_conversation(user_id, session_id, role, content, metadata)

    async def update_user_preferences(self, user_id: str, preferences: Dict[str, Any]):
        return await self.structured_db.update_user_preferences(user_id, preferences)

    # ── Unified API ──

    async def get_user_context(self, user_id: str, query: str = "") -> Dict[str, Any]:
        """
        Retrieve the full user context for agents.

        Combines structured data (tasks, reminders, habits, etc.) and
        vector search results into a single context package.

        Args:
            user_id: The user to scope data to.
            query: Optional query for relevance-based vector retrieval.

        Returns:
            A context dict matching the MemoryContext state shape.
        """
        return await self.assemble_context(user_id, query)

    async def store_memory(
        self,
        user_id: str,
        content: str,
        memory_type: str = "knowledge",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Store a memory entry in the appropriate backend.

        For 'knowledge' type, content is embedded and stored in the vector DB.
        For structured types ('task', 'reminder', 'habit'), delegates to the
        structured DB.

        Args:
            user_id: Owning user ID.
            content: The text content to store.
            memory_type: 'knowledge' | 'task' | 'reminder' | 'habit'.
            metadata: Additional metadata (title, remind_at, etc.).

        Returns:
            A dict with the storage result.
        """
        metadata = metadata or {}

        if memory_type == "knowledge":
            chunk = {"content": content, "topic": metadata.get("topic", "general")}
            count = await self.store_document_chunks(
                chunks=[chunk],
                document_id=metadata.get("document_id", f"mem_{user_id}"),
                user_id=user_id,
                source_filename=metadata.get("source", "user_memory"),
            )
            return {"status": "ok", "stored": count, "type": "knowledge"}

        if memory_type == "task":
            result = await self.structured_db.create_task(
                user_id, title=metadata.get("title", content), description=content,
            )
            return {"status": "ok", "type": "task", "record": result}

        if memory_type == "reminder":
            result = await self.structured_db.create_reminder(
                user_id,
                title=metadata.get("title", content),
                message=content,
                remind_at=metadata.get("remind_at"),
            )
            return {"status": "ok", "type": "reminder", "record": result}

        if memory_type == "habit":
            result = await self.structured_db.create_habit(
                user_id, name=metadata.get("name", content),
            )
            return {"status": "ok", "type": "habit", "record": result}

        return {"status": "error", "message": f"Unknown memory_type: {memory_type}"}

    async def store_behavior_pattern(
        self,
        user_id: str,
        pattern_type: str,
        pattern_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Persist a detected behavior pattern to the vector store.

        Args:
            user_id: Owning user ID.
            pattern_type: Category (e.g. 'time_preference', 'habit_streak', 'missed_reminder').
            pattern_data: Arbitrary dict describing the pattern.

        Returns:
            A dict with the storage result.
        """
        import json as _json

        content = f"[{pattern_type}] {_json.dumps(pattern_data, default=str)}"
        chunk = {"content": content, "topic": "behavior_pattern"}
        count = await self.store_document_chunks(
            chunks=[chunk],
            document_id=f"pattern_{user_id}_{pattern_type}",
            user_id=user_id,
            source_filename="behavior_pattern",
        )
        logger.info(
            f"Stored behavior pattern: {pattern_type}",
            event_type="behavior_pattern_stored",
            metadata={"user_id": user_id, "pattern_type": pattern_type},
        )
        return {"status": "ok", "stored": count, "pattern_type": pattern_type}

    async def get_conversation_history(self, user_id: str, limit: int = 20):
        return await self.structured_db.get_conversation_history(user_id, limit)

    async def store_user_fact(
        self,
        user_id: str,
        summary: str,
        key: str,
        value: str,
        topic: str,
        confidence: float,
    ) -> Dict[str, Any]:
        """Persist a learned user fact into both structured and vector memory."""
        if not user_id:
            return {"status": "error", "message": "user_id is required"}
        if not summary.strip():
            return {"status": "error", "message": "summary is required"}

        # 1) Structured memory write (users.preferences JSON)
        user = await self.get_user_by_id(user_id)
        existing_preferences = {}
        if user and isinstance(user.get("preferences"), dict):
            existing_preferences = dict(user.get("preferences") or {})

        learned_facts = list(existing_preferences.get("learned_facts", []))
        normalized_summary = summary.strip().lower()
        duplicate = any(
            str(f.get("summary", "")).strip().lower() == normalized_summary
            for f in learned_facts
            if isinstance(f, dict)
        )

        if not duplicate:
            learned_facts.append(
                {
                    "summary": summary.strip(),
                    "key": key.strip() or "fact",
                    "value": value.strip(),
                    "topic": topic,
                    "confidence": float(confidence),
                    "source": "learning_layer",
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        existing_preferences["learned_facts"] = learned_facts[-200:]

        profile = existing_preferences.get("profile", {})
        if not isinstance(profile, dict):
            profile = {}
        if key and value and topic in {"profile", "personal_info", "preference"}:
            profile[key] = value
        existing_preferences["profile"] = profile

        structured_status = "skipped_user_not_found"
        if user:
            await self.update_user_preferences(user_id, existing_preferences)
            structured_status = "updated"

        # 2) Vector memory write (searchable knowledge)
        vector_result = await self.store_memory(
            user_id=user_id,
            content=summary.strip(),
            memory_type="knowledge",
            metadata={
                "topic": topic or "personal_info",
                "source": "learning_layer",
                "document_id": f"user_profile_{user_id}",
            },
        )

        return {
            "status": "ok",
            "structured": structured_status,
            "vector": vector_result,
            "duplicate": duplicate,
        }
