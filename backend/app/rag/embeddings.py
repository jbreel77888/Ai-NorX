"""
Chunking + Embeddings pipeline.
- Text chunking (recursive character-based)
- Embeddings via HuggingFace BGE-M3 (free)
- Vector storage in pgvector
"""
import logging
import hashlib
from typing import List, Dict, Any
import asyncio

from app.core.config import settings
from app.llm import llm_gateway

logger = logging.getLogger(__name__)

# Chunking parameters
CHUNK_SIZE = 500  # characters
CHUNK_OVERLAP = 50  # characters overlap between chunks
MIN_CHUNK_SIZE = 50  # minimum chunk size


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split text into overlapping chunks.

    Uses paragraph boundaries when possible, falls back to character-based.
    """
    if not text or not text.strip():
        return []

    # Split by paragraphs first
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        # If paragraph is very long, split it further
        if len(para) > chunk_size:
            # If current chunk has content, save it
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""

            # Split long paragraph by sentences
            sentences = _split_sentences(para)
            for sentence in sentences:
                if len(current_chunk) + len(sentence) + 1 <= chunk_size:
                    current_chunk = (current_chunk + " " + sentence).strip() if current_chunk else sentence
                else:
                    if current_chunk and len(current_chunk) >= MIN_CHUNK_SIZE:
                        chunks.append(current_chunk)
                    current_chunk = sentence

                    # If sentence itself is too long, hard-split
                    while len(current_chunk) > chunk_size:
                        chunks.append(current_chunk[:chunk_size])
                        current_chunk = current_chunk[chunk_size - overlap:]

        # If adding this paragraph exceeds chunk size, save current and start new
        elif len(current_chunk) + len(para) + 2 > chunk_size:
            if current_chunk and len(current_chunk) >= MIN_CHUNK_SIZE:
                chunks.append(current_chunk)
            current_chunk = para
        else:
            current_chunk = (current_chunk + "\n\n" + para).strip() if current_chunk else para

    # Don't forget the last chunk
    if current_chunk and len(current_chunk) >= MIN_CHUNK_SIZE:
        chunks.append(current_chunk)

    return chunks


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences (Arabic + English aware)."""
    import re
    # Split on . ! ? ؟ . followed by space or end
    sentences = re.split(r'(?<=[.!?؟\n])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def compute_hash(text: str) -> str:
    """Compute SHA-256 hash of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def embed_text(text: str) -> List[float]:
    """Generate embedding for a single text."""
    try:
        return await llm_gateway.embed(text)
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        # Return zero vector as fallback (1024 dims for BGE-M3)
        return [0.0] * 1024


async def embed_batch(texts: List[str], batch_size: int = 8) -> List[List[float]]:
    """Generate embeddings for multiple texts (batched)."""
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        # Process batch concurrently
        tasks = [embed_text(t) for t in batch]
        batch_embeddings = await asyncio.gather(*tasks, return_exceptions=True)

        for emb in batch_embeddings:
            if isinstance(emb, Exception):
                logger.warning(f"Embedding error: {emb}")
                all_embeddings.append([0.0] * 1024)
            else:
                all_embeddings.append(emb)

    return all_embeddings


async def process_document(
    text: str,
    tenant_id: Any,
    document_id: Any,
    knowledge_base_id: Any,
    db_session=None,
) -> Dict[str, Any]:
    """
    Process a document: chunk + embed + store in DB.

    Returns dict with: chunk_count, embedding_dim, processing_time_ms
    """
    import time
    start_time = time.time()

    from app.db.models import DocumentChunk
    from sqlalchemy.ext.asyncio import AsyncSession

    # 1. Chunk the text
    chunks = chunk_text(text)
    if not chunks:
        return {
            "chunk_count": 0,
            "embedding_dim": 0,
            "processing_time_ms": int((time.time() - start_time) * 1000),
        }

    logger.info(f"📄 Document split into {len(chunks)} chunks")

    # 2. Generate embeddings for all chunks
    embeddings = await embed_batch(chunks)
    logger.info(f"🧠 Generated {len(embeddings)} embeddings")

    # 3. Store chunks in DB
    if db_session:
        for i, chunk_text_str in enumerate(chunks):
            embedding = embeddings[i] if i < len(embeddings) else [0.0] * 1024
            chunk = DocumentChunk(
                tenant_id=tenant_id,
                document_id=document_id,
                knowledge_base_id=knowledge_base_id,
                chunk_index=i,
                text=chunk_text_str,
                embedding=embedding,
                chunk_metadata={
                    "char_count": len(chunk_text_str),
                    "hash": compute_hash(chunk_text_str),
                },
            )
            db_session.add(chunk)

        await db_session.flush()

    return {
        "chunk_count": len(chunks),
        "embedding_dim": len(embeddings[0]) if embeddings else 0,
        "processing_time_ms": int((time.time() - start_time) * 1000),
    }
