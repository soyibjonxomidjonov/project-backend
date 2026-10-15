from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk
from app.services.embeddings import embed_query


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

    distance_expr = DocumentChunk.embedding.cosine_distance(query_vec).label("distance")
    stmt = (
        select(
            DocumentChunk.content,
            DocumentChunk.chunk_index,
            Document.title.label("doc_title"),
            distance_expr,
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .order_by("distance")
        .limit(top_k)
    )
    result = await db.execute(stmt)

    return [
        {
            "content": row.content,
            "document_title": row.doc_title,
            "chunk_index": row.chunk_index,
            "similarity": round(1 - row.distance, 4),
        }
        for row in result.all()
        if (1 - row.distance) >= min_similarity
    ]
