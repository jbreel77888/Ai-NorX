"""
Knowledge Search Tool - searches user's uploaded files (RAG).
Inspired by Onyx SearchTool + LibreChat file_search
"""
import logging
from typing import Any, Dict, List
from uuid import UUID
import asyncio

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseTool, ToolCategory, ToolScope, ToolResult, ToolContext
from app.db.models import Document, DocumentChunk, KnowledgeBase
from app.db.session import async_session_factory
from app.llm import llm_gateway

logger = logging.getLogger(__name__)


class KnowledgeSearchTool(BaseTool):
    """Search user's uploaded documents using semantic search."""

    name = "knowledge_search"
    display_name = "بحث في الملفات"
    description = "ابحث في الملفات والمستندات التي رفعها المستخدم. استخدم هذا عندما يسأل المستخدم عن معلومات من ملفاته أو يرفع مرفقات."
    category = ToolCategory.KNOWLEDGE
    scope = ToolScope.ALL
    timeout_seconds = 20

    def get_openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "استعلام البحث في الملفات",
                        },
                        "num_results": {
                            "type": "integer",
                            "description": "عدد النتائج (افتراضي 5)",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            },
        }

    async def execute(
        self,
        arguments: Dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        query = arguments.get("query", "").strip()
        num_results = min(arguments.get("num_results", 5), 10)

        if not query:
            return ToolResult(
                success=False,
                output="",
                error="query is required",
            )

        try:
            # Generate embedding for the query
            query_embedding = await llm_gateway.embed(query)
            if not query_embedding:
                return ToolResult(
                    success=False,
                    output="",
                    error="Failed to generate query embedding",
                )

            # Search in DB using pgvector cosine distance operator
            async with async_session_factory() as db:
                # Use raw SQL for vector search (pgvector cosine distance: <=>)
                # Distance: 0 = identical, 2 = opposite
                sql = text("""
                    SELECT
                        dc.id,
                        dc.text,
                        dc.chunk_index,
                        dc.metadata,
                        1 - (dc.embedding <=> :embedding::vector) as similarity,
                        d.name as document_name,
                        d.id as document_id
                    FROM document_chunks dc
                    JOIN documents d ON dc.document_id = d.id
                    WHERE dc.tenant_id = :tenant_id
                    ORDER BY dc.embedding <=> :embedding::vector
                    LIMIT :limit
                """)

                # Convert embedding list to PostgreSQL vector string
                embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

                result = await db.execute(
                    sql,
                    {
                        "embedding": embedding_str,
                        "tenant_id": str(context.tenant_id),
                        "limit": num_results,
                    },
                )
                rows = result.fetchall()

            if not rows:
                return ToolResult(
                    success=True,
                    output="لم يتم العثور على ملفات مطابقة. لا توجد ملفات مرفوعة أو لم تتطابق نتائج.",
                    data={"query": query, "results_count": 0},
                    citations=[],
                )

            # Format results
            output_parts = [f"تم العثور على {len(rows)} نتيجة في ملفاتك:\n"]
            citations = []

            for i, row in enumerate(rows, 1):
                similarity = float(row.similarity)
                # Only include results with similarity > 0.3 (cosine)
                if similarity < 0.3:
                    continue

                doc_name = row.document_name
                chunk_text = row.text[:500] + ("..." if len(row.text) > 500 else "")

                output_parts.append(f"### النتيجة {i} (تطابق: {similarity:.1%})")
                output_parts.append(f"**الملف:** {doc_name}")
                output_parts.append(f"**المحتوى:** {chunk_text}\n")

                citations.append({
                    "title": doc_name,
                    "url": "",  # Could be presigned URL
                    "snippet": chunk_text[:200],
                    "source": "user_file",
                    "similarity": similarity,
                    "document_id": str(row.document_id),
                })

            output = "\n".join(output_parts) if len(output_parts) > 1 else "لم يتم العثور على نتائج ذات صلة."

            return ToolResult(
                success=True,
                output=output,
                data={
                    "query": query,
                    "results_count": len(citations),
                },
                citations=citations,
            )

        except Exception as e:
            logger.error(f"Knowledge search failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                output="",
                error=f"Search failed: {e}",
            )
