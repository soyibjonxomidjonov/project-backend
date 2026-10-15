from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk
from app.services.embeddings import embed_query, embed_texts


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current and len(current) + len(para) + 2 > chunk_size:
            chunks.append(current.strip())
            current = current[-overlap:].strip() + "\n\n" + para
        else:
            current = current + "\n\n" + para if current else para

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else ([text.strip()] if text.strip() else [])


async def search_similar(
    db: AsyncSession, query: str, top_k: int = 5, min_similarity: float = 0.3
) -> list[dict]:
    query_vec = await embed_query(query)

    stmt = (
        select(
            DocumentChunk.content,
            DocumentChunk.chunk_index,
            DocumentChunk.document_id,
            DocumentChunk.embedding.cosine_distance(query_vec).label("distance"),
        )
        .order_by("distance")
        .limit(top_k)
    )
    result = await db.execute(stmt)
    rows = result.all()

    results = []
    doc_cache: dict = {}
    for content, chunk_index, doc_id, distance in rows:
        similarity = 1 - distance
        if similarity < min_similarity:
            continue
        if doc_id not in doc_cache:
            doc = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one()
            doc_cache[doc_id] = doc.title
        results.append(
            {
                "content": content,
                "document_title": doc_cache[doc_id],
                "chunk_index": chunk_index,
                "similarity": round(similarity, 4),
            }
        )

    return results
