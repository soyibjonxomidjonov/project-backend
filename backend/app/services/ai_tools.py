import json
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity
from app.services.rag import search_similar

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_entities",
            "description": "Search entities by type and text query",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "description": "Entity type filter"},
                    "q": {"type": "string", "description": "Search query for title"},
                    "status": {"type": "string", "description": "Status filter"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_entity",
            "description": "Get a single entity by its ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Entity UUID"},
                },
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stats",
            "description": "Get entity statistics optionally filtered by type",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "description": "Entity type filter"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Search the knowledge base for relevant information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
    },
]


async def execute_tool(db: AsyncSession, tool_name: str, arguments: str) -> str:
    args = json.loads(arguments) if isinstance(arguments, str) else arguments

    if tool_name == "search_entities":
        query = select(Entity)
        if args.get("type"):
            query = query.where(Entity.type == args["type"])
        if args.get("q"):
            query = query.where(Entity.title.ilike(f"%{args['q']}%"))
        if args.get("status"):
            query = query.where(Entity.status == args["status"])
        query = query.limit(10)
        result = await db.execute(query)
        entities = result.scalars().all()
        return json.dumps(
            [{"id": str(e.id), "type": e.type, "title": e.title, "data": e.data} for e in entities],
            ensure_ascii=False,
        )

    if tool_name == "get_entity":
        result = await db.execute(select(Entity).where(Entity.id == uuid.UUID(args["id"])))
        entity = result.scalar_one_or_none()
        if entity is None:
            return json.dumps({"error": "Entity not found"})
        return json.dumps(
            {"id": str(entity.id), "type": entity.type, "title": entity.title, "data": entity.data},
            ensure_ascii=False,
        )

    if tool_name == "get_stats":
        conditions = []
        if args.get("type"):
            conditions.append(Entity.type == args["type"])
        total_q = select(func.count()).select_from(Entity)
        for c in conditions:
            total_q = total_q.where(c)
        total = (await db.execute(total_q)).scalar()

        status_q = select(Entity.status, func.count()).select_from(Entity).group_by(Entity.status)
        for c in conditions:
            status_q = status_q.where(c)
        by_status = {r[0]: r[1] for r in (await db.execute(status_q)).all()}

        return json.dumps({"total": total, "by_status": by_status}, ensure_ascii=False)

    if tool_name == "search_knowledge":
        results = await search_similar(db, args["query"])
        return json.dumps(results, ensure_ascii=False)

    return json.dumps({"error": f"Unknown tool: {tool_name}"})
