from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from myra.api.routes import router
from myra.core.config import get_settings
from myra.core.container import ServiceContainer
from myra.core.database import MongoDatabase
from myra.intelligence.decision_engine import DecisionEngine
from myra.memory.long_term import LongTermMemoryStore
from myra.memory.short_term import ShortTermMemoryStore
from myra.services.chat_service import ChatService
from myra.tasks.parser import TaskParser
from myra.tasks.scheduler import TaskSchedulerService, TaskService
from myra.user.profile import UserProfileService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    database = MongoDatabase(settings)
    await database.connect()

    short_term = ShortTermMemoryStore(settings.short_term_memory_limit)
    long_term = LongTermMemoryStore(database, settings)
    profile_service = UserProfileService(database)
    task_parser = TaskParser(settings)
    task_service = TaskService(database, settings)
    scheduler = TaskSchedulerService(task_service, settings)
    decision_engine = DecisionEngine(settings)
    chat_service = ChatService(
        settings=settings,
        short_term=short_term,
        long_term=long_term,
        profile_service=profile_service,
        task_parser=task_parser,
        task_service=task_service,
        decision_engine=decision_engine,
    )

    app.state.services = ServiceContainer(
        short_term=short_term,
        long_term=long_term,
        profile_service=profile_service,
        task_parser=task_parser,
        task_service=task_service,
        scheduler=scheduler,
        decision_engine=decision_engine,
        chat_service=chat_service,
    )

    await scheduler.start()
    yield
    await scheduler.shutdown()
    await database.disconnect()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix=settings.api_prefix)
    return app


app = create_app()

