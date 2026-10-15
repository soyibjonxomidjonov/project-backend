import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User
from app.schemas.ai import ChatRequest, ChatResponse, SessionListResponse, SessionResponse
from app.models.entity import Entity
from app.schemas.entity import EntityStatsResponse
from app.services.ai_tools import TOOLS, execute_tool
from app.services.llm import chat_completion
from app.services.prompts import SYSTEM_ACTIONS, SYSTEM_ANALYTICS, SYSTEM_CHAT, SYSTEM_KNOWLEDGE
from app.services.rag import search_similar

router = APIRouter(prefix="/ai", tags=["ai"])


async def _get_or_create_session(
    db: AsyncSession, user: User, session_id: uuid.UUID | None, assistant: str
) -> ChatSession:
    if session_id:
        result = await db.execute(
            select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id)
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(404, "Session not found")
        return session
    session = ChatSession(user_id=user.id, assistant=assistant)
    db.add(session)
    await db.flush()
    return session


async def _get_context_messages(db: AsyncSession, session_id: uuid.UUID, limit: int = 30) -> list[dict]:
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    msgs = list(reversed(result.scalars().all()))
    return [{"role": m.role, "content": m.content} for m in msgs]


@router.post("/chat", summary="Send message to AI assistant")
async def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_or_create_session(db, user, body.session_id, body.assistant)

    user_msg = ChatMessage(session_id=session.id, role="user", content=body.message)
    db.add(user_msg)
    await db.flush()

    context = await _get_context_messages(db, session.id)
    meta = None

    tools = None
    if body.assistant == "knowledge":
        sources = await search_similar(db, body.message)
        if sources:
            ctx_text = "\n\n---\n\n".join(
                f"[{s['document_title']}, chunk {s['chunk_index']}]\n{s['content']}" for s in sources
            )
            system_prompt = SYSTEM_KNOWLEDGE.format(context=ctx_text)
            meta = {"sources": sources}
        else:
            system_prompt = SYSTEM_KNOWLEDGE.format(context="Ma'lumot topilmadi.")
    elif body.assistant == "analytics":
        from datetime import datetime, timedelta, timezone

        from sqlalchemy import func

        conditions = []
        total = (await db.execute(select(func.count()).select_from(Entity))).scalar()
        status_q = select(Entity.status, func.count()).select_from(Entity).group_by(Entity.status)
        by_status = {r[0]: r[1] for r in (await db.execute(status_q)).all()}
        thirty = datetime.now(timezone.utc) - timedelta(days=30)
        day_q = (
            select(func.date_trunc("day", Entity.created_at).label("d"), func.count())
            .select_from(Entity)
            .where(Entity.created_at >= thirty)
            .group_by("d")
            .order_by("d")
        )
        by_day = [{"date": str(r[0]), "count": r[1]} for r in (await db.execute(day_q)).all()]
        stats_data = json.dumps(
            {"total": total, "by_status": by_status, "by_day": by_day}, ensure_ascii=False
        )
        system_prompt = SYSTEM_ANALYTICS.format(data=stats_data)
    elif body.assistant == "actions":
        system_prompt = SYSTEM_ACTIONS
        tools = TOOLS
    else:
        system_prompt = SYSTEM_CHAT

    messages = [{"role": "system", "content": system_prompt}] + context

    if body.stream:
        return StreamingResponse(
            _stream_response(db, session.id, messages),
            media_type="text/event-stream",
            headers={"X-Session-Id": str(session.id)},
        )

    try:
        response = await chat_completion(messages, stream=False, tools=tools)
        msg_obj = response.choices[0].message

        if msg_obj.tool_calls:
            # Rebuild the assistant message with only Groq-supported fields
            # (model_dump() includes `annotations`, which Groq rejects).
            messages.append({
                "role": "assistant",
                "content": msg_obj.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg_obj.tool_calls
                ],
            })
            tool_meta = []
            for tc in msg_obj.tool_calls:
                result = await execute_tool(db, tc.function.name, tc.function.arguments)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                tool_meta.append({"tool": tc.function.name, "args": tc.function.arguments, "result": result})
            meta = {"tool_calls": tool_meta}
            response = await chat_completion(messages, stream=False)
            content = response.choices[0].message.content or ""
        else:
            content = msg_obj.content or ""
    except Exception as e:
        content = f"AI xatolik: {e}"

    assistant_msg = ChatMessage(session_id=session.id, role="assistant", content=content, meta=meta)
    db.add(assistant_msg)

    if session.title is None and len(context) <= 2:
        session.title = body.message[:100]

    await db.commit()
    return ChatResponse(session_id=session.id, content=content, meta=meta)


async def _stream_response(db: AsyncSession, session_id: uuid.UUID, messages: list[dict]):
    from app.db import async_session as session_factory

    full_content = ""
    try:
        response = await chat_completion(messages, stream=True)
        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                full_content += delta.content
                yield f"data: {json.dumps({'content': delta.content})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

    if full_content:
        async with session_factory() as new_db:
            msg = ChatMessage(session_id=session_id, role="assistant", content=full_content)
            new_db.add(msg)
            await new_db.commit()

    yield "data: [DONE]\n\n"


@router.post("/insights", summary="Get AI-powered insights for entity type")
async def insights(
    type: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func

    conditions = []
    if type:
        conditions.append(Entity.type == type)

    total_q = select(func.count()).select_from(Entity)
    for c in conditions:
        total_q = total_q.where(c)
    total = (await db.execute(total_q)).scalar()

    status_q = select(Entity.status, func.count()).select_from(Entity).group_by(Entity.status)
    for c in conditions:
        status_q = status_q.where(c)
    by_status = {r[0]: r[1] for r in (await db.execute(status_q)).all()}

    thirty = datetime.now(timezone.utc) - timedelta(days=30)
    day_q = (
        select(func.date_trunc("day", Entity.created_at).label("d"), func.count())
        .select_from(Entity)
        .where(Entity.created_at >= thirty)
        .group_by("d")
        .order_by("d")
    )
    for c in conditions:
        day_q = day_q.where(c)
    by_day = [{"date": str(r[0]), "count": r[1]} for r in (await db.execute(day_q)).all()]

    stats = json.dumps({"total": total, "by_status": by_status, "by_day": by_day}, ensure_ascii=False)
    messages = [
        {"role": "system", "content": SYSTEM_ANALYTICS.format(data=stats)},
        {"role": "user", "content": "Bu ma'lumotlarni tahlil qilib, xulosa va tavsiyalar bering."},
    ]

    try:
        response = await chat_completion(messages, stream=False)
        content = response.choices[0].message.content or ""
    except Exception as e:
        content = f"AI xatolik: {e}"

    return {"insights": content, "stats": {"total": total, "by_status": by_status, "by_day": by_day}}


@router.get("/sessions", summary="List chat sessions", response_model=SessionListResponse)
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.created_at.desc())
    )
    sessions = result.scalars().all()
    return SessionListResponse(items=[SessionResponse.model_validate(s) for s in sessions])


@router.get("/sessions/{session_id}", summary="Get chat session with messages")
async def get_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(404, "Session not found")

    msgs = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
    )
    messages = msgs.scalars().all()

    return {
        "id": str(session.id),
        "assistant": session.assistant,
        "title": session.title,
        "created_at": session.created_at.isoformat(),
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "meta": m.meta,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }


@router.delete("/sessions/{session_id}", summary="Delete chat session", status_code=204)
async def delete_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(404, "Session not found")
    await db.delete(session)
    await db.commit()
