"""
Demo data seeder.

Usage:
    python -m scripts.seed --type product --count 40 --topic "Elektron mahsulotlar"
    python -m scripts.seed --type product --count 40 --topic "Elektron" --knowledge
    python -m scripts.seed --type product --reset
"""

import argparse
import asyncio
import json
import sys
import uuid

from sqlalchemy import delete, select

sys.path.insert(0, ".")

from app.config import settings
from app.db import async_session
from app.models.document import Document, DocumentChunk
from app.models.entity import Entity
from app.models.user import User
from app.services.embeddings import embed_texts


async def get_or_create_seed_user() -> uuid.UUID:
    async with async_session() as db:
        email = f"seed@{settings.BASE_DOMAIN}"
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(email=email, name="Seed Bot", role="user")
            db.add(user)
            await db.commit()
            await db.refresh(user)
        return user.id


async def generate_entities_with_llm(entity_type: str, topic: str, count: int) -> list[dict]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY)

    prompt = (
        f"{count} ta '{entity_type}' turida o'zbekcha demo yozuvlar yarating. "
        f"Mavzu: {topic}. Har bir yozuv JSON formatda bo'lsin:\n"
        f'{{"title": "...", "data": {{...mavzuga mos maydonlar...}}}}\n'
        f"Faqat JSON array qaytaring, boshqa matn yo'q."
    )

    response = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        timeout=60,
    )
    text = response.choices[0].message.content or "[]"
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        text = text[start:end]
    return json.loads(text)


async def seed_entities(entity_type: str, topic: str, count: int):
    user_id = await get_or_create_seed_user()
    print(f"LLM orqali {count} ta '{entity_type}' generatsiya qilinmoqda...")

    try:
        items = await generate_entities_with_llm(entity_type, topic, count)
    except Exception as e:
        print(f"LLM xatolik: {e}")
        print("Oddiy demo ma'lumotlar yaratilmoqda...")
        items = [
            {"title": f"{topic} #{i+1}", "data": {"description": f"Demo {topic.lower()} #{i+1}"}}
            for i in range(count)
        ]

    async with async_session() as db:
        for item in items:
            entity = Entity(
                type=entity_type,
                title=item.get("title", "Untitled"),
                data=item.get("data", {}),
                owner_id=user_id,
            )
            db.add(entity)
        await db.commit()
    print(f"{len(items)} ta yozuv qo'shildi.")


async def seed_knowledge(topic: str, count: int = 5):
    user_id = await get_or_create_seed_user()
    from openai import AsyncOpenAI

    client = AsyncOpenAI(base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY)

    print(f"Knowledge bazasi uchun {count} ta matn generatsiya qilinmoqda...")

    prompt = (
        f"'{topic}' mavzusida {count} ta informativ matn yozing (har biri 200-400 so'z, o'zbek tilida). "
        f"Har bir matn alohida bo'lsin. JSON array formatda qaytaring: "
        f'[{{"title": "...", "content": "..."}}]'
    )

    response = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        timeout=120,
    )
    text = response.choices[0].message.content or "[]"
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        text = text[start:end]
    articles = json.loads(text)

    async with async_session() as db:
        for article in articles:
            title = article.get("title", "Untitled")
            content = article.get("content", "")
            if not content:
                continue

            from app.services.rag import chunk_text

            chunks = chunk_text(content)
            embeddings = await embed_texts(chunks)

            doc = Document(title=title, mime_type="text/plain", owner_id=user_id, status="ready", chunk_count=len(chunks))
            db.add(doc)
            await db.flush()

            for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                db.add(DocumentChunk(document_id=doc.id, content=chunk, chunk_index=i, embedding=emb))

        await db.commit()
    print(f"{len(articles)} ta ma'lumot matni qo'shildi.")


async def reset_type(entity_type: str):
    async with async_session() as db:
        result = await db.execute(delete(Entity).where(Entity.type == entity_type))
        await db.commit()
    print(f"'{entity_type}' turidagi barcha yozuvlar o'chirildi ({result.rowcount} ta).")


async def main():
    parser = argparse.ArgumentParser(description="Demo data seeder")
    parser.add_argument("--type", required=True, help="Entity type")
    parser.add_argument("--count", type=int, default=20, help="Number of entities")
    parser.add_argument("--topic", default="", help="Topic description for LLM")
    parser.add_argument("--knowledge", action="store_true", help="Also seed knowledge base")
    parser.add_argument("--reset", action="store_true", help="Reset entities of this type")
    args = parser.parse_args()

    if args.reset:
        await reset_type(args.type)
        return

    topic = args.topic or args.type
    await seed_entities(args.type, topic, args.count)

    if args.knowledge:
        await seed_knowledge(topic)


if __name__ == "__main__":
    asyncio.run(main())
