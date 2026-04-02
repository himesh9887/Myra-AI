from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from myra.core.container import ServiceContainer
from myra.models.chat import ChatRequest, ChatResponse
from myra.models.memory import MemoryResponse
from myra.models.profile import UserProfile
from myra.models.task import TaskCreateRequest, TaskResponse

router = APIRouter()


def get_services(request: Request) -> ServiceContainer:
    return request.app.state.services


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    services = get_services(request)
    return await services.chat_service.handle_chat(payload)


@router.get("/memory", response_model=MemoryResponse)
async def get_memory(
    request: Request,
    user_id: str = Query(...),
    session_id: str | None = Query(default=None),
    query: str | None = Query(default=None),
) -> MemoryResponse:
    services = get_services(request)
    if session_id:
        short_term = await services.short_term.get_session(user_id, session_id)
    else:
        short_term = await services.short_term.get_recent_for_user(user_id, limit=10)
    recent = await services.long_term.get_recent(user_id, limit=10)
    relevant = await services.long_term.retrieve_relevant(user_id, query, limit=5) if query else []
    return MemoryResponse(user_id=user_id, short_term=short_term, recent=recent, relevant=relevant)


@router.post("/task", response_model=TaskResponse)
async def create_task(payload: TaskCreateRequest, request: Request) -> TaskResponse:
    services = get_services(request)

    if payload.message:
        parsed_task = services.task_parser.parse(payload.message)
        if parsed_task is None:
            raise HTTPException(status_code=400, detail="Could not extract a task from the provided message.")
        task, created = await services.task_service.create_from_parsed(
            user_id=payload.user_id,
            parsed_task=parsed_task,
            raw_text=payload.message,
            reminder_minutes_before=payload.reminder_minutes_before,
            source="api",
        )
        return TaskResponse(task=task, created=created)

    if not payload.task_type or not payload.title or not payload.start_at:
        raise HTTPException(
            status_code=400,
            detail="Provide either a natural language message or structured task_type, title, and start_at values.",
        )

    task, created = await services.task_service.create_structured(
        user_id=payload.user_id,
        task_type=payload.task_type,
        title=payload.title,
        start_at=payload.start_at,
        end_at=payload.end_at,
        raw_text=payload.message,
        reminder_minutes_before=payload.reminder_minutes_before,
        source="api",
    )
    return TaskResponse(task=task, created=created)


@router.get("/profile", response_model=UserProfile)
async def get_profile(request: Request, user_id: str = Query(...)) -> UserProfile:
    services = get_services(request)
    return await services.profile_service.get_profile(user_id)
