"""
Memory Manager — unified interface for both structured and vector memory systems.

The Memory Manager provides a single entry point for all memory operations.
It coordinates between the structured database (SQLAlchemy) and the vector
database (Azure AI Search) to assemble complete context packages for agents.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from app.memory.structured_db import StructuredDB
from app.memory.vector_db import VectorDB
from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("memory_manager")


class MemoryManager:
    """
    Unified memory interface that coordinates:
    - Structured DB (tasks, reminders, habits, documents, flashcards, etc.)
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
            try:
                from openai import AzureOpenAI

                self._embedding_client = AzureOpenAI(
                    azure_endpoint=settings.azure_openai.endpoint,
                    api_key=settings.azure_openai.api_key,
                    api_version=settings.azure_openai.api_version,
                )
            except ImportError:
                logger.warning("OpenAI SDK not installed. Embeddings will use fallback.")
                return None
            except Exception as e:
                logger.error(f"Failed to create embedding client: {e}", exc_info=True)
                return None
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
        if not client:
            return self._fallback_embedding(text)

        try:
            start = time.time()
            response = client.embeddings.create(
                input=text,
                model=settings.azure_openai.embedding_deployment,
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

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}", exc_info=True)
            return self._fallback_embedding(text)

    def _fallback_embedding(self, text: str) -> List[float]:
        """Generate a simple hash-based pseudo-embedding for development."""
        import hashlib
        hash_bytes = hashlib.sha512(text.encode()).digest()
        # Expand to 1536 dimensions by repeating
        values = [b / 255.0 for b in hash_bytes]
        embedding = (values * (1536 // len(values) + 1))[:1536]
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
            },
            "vector_memory": {
                "notes": [],
                "conversation_history": conversation_history,
                "behavior_patterns": [],
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

    async def save_flashcard_set(self, user_id: str, title: str, topic: str, cards: list):
        return await self.structured_db.save_flashcard_set(user_id, title, topic, cards)

    async def get_flashcard_sets(self, user_id: str):
        return await self.structured_db.get_flashcard_sets(user_id)

    async def get_flashcards(self, set_id: str):
        return await self.structured_db.get_flashcards(set_id)

    async def save_quiz(self, user_id: str, title: str, topic: str, questions: list):
        return await self.structured_db.save_quiz(user_id, title, topic, questions)

    async def get_quizzes(self, user_id: str):
        return await self.structured_db.get_quizzes(user_id)

    async def save_study_plan(self, user_id: str, title: str, schedule: dict, **kwargs):
        return await self.structured_db.save_study_plan(user_id, title, schedule, **kwargs)

    async def get_study_plans(self, user_id: str):
        return await self.structured_db.get_study_plans(user_id)

    async def save_conversation(self, user_id: str, session_id: str, role: str, content: str, metadata: dict = None):
        return await self.structured_db.save_conversation(user_id, session_id, role, content, metadata)

    async def get_conversation_history(self, user_id: str, limit: int = 20):
        return await self.structured_db.get_conversation_history(user_id, limit)
