from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from myra.core.config import Settings


class MongoDatabase:
    """Handles MongoDB connection lifecycle and indexes."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.client: AsyncIOMotorClient | None = None
        self.database: AsyncIOMotorDatabase | None = None

    async def connect(self) -> None:
        self.client = AsyncIOMotorClient(self._settings.mongodb_uri)
        self.database = self.client[self._settings.mongodb_database]
        await self.ensure_indexes()

    async def disconnect(self) -> None:
        if self.client is not None:
            self.client.close()
        self.client = None
        self.database = None

    async def ensure_indexes(self) -> None:
        if self.database is None:
            raise RuntimeError("Database is not connected")

        memories = self.database["memories"]
        profiles = self.database["profiles"]
        tasks = self.database["tasks"]
        notifications = self.database["notifications"]

        await memories.create_index([("user_id", ASCENDING), ("timestamp", DESCENDING)])
        await memories.create_index([("user_id", ASCENDING), ("session_id", ASCENDING)])
        await memories.create_index([("user_id", ASCENDING), ("keywords", ASCENDING)])

        await profiles.create_index("user_id", unique=True)

        await tasks.create_index([("user_id", ASCENDING), ("start_at", ASCENDING)])
        await tasks.create_index([("user_id", ASCENDING), ("status", ASCENDING)])
        await tasks.create_index([("reminder_at", ASCENDING), ("status", ASCENDING)])

        await notifications.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        await notifications.create_index([("task_id", ASCENDING), ("created_at", DESCENDING)])

    @property
    def db(self) -> AsyncIOMotorDatabase:
        if self.database is None:
            raise RuntimeError("Database is not connected")
        return self.database

