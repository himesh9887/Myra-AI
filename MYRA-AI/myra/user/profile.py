from __future__ import annotations

import re
from typing import Any

from pymongo import ReturnDocument

from myra.core.database import MongoDatabase
from myra.core.time import utc_now
from myra.models.profile import UserProfile


class UserProfileService:
    """Maintains a personalized profile that evolves from conversation."""

    def __init__(self, db: MongoDatabase) -> None:
        self._collection = db.db["profiles"]

    async def get_profile(self, user_id: str) -> UserProfile:
        document = await self._collection.find_one({"user_id": user_id})
        if not document:
            return UserProfile(user_id=user_id)
        return self._to_profile(document)

    async def update_from_message(self, user_id: str, message: str) -> UserProfile:
        extracted = self._extract_profile_data(message)
        current = await self.get_profile(user_id)

        payload = {
            "user_id": user_id,
            "name": extracted.get("name") or current.name,
            "preferences": self._merge_unique(current.preferences, extracted.get("preferences", [])),
            "habits": self._merge_unique(current.habits, extracted.get("habits", [])),
            "goals": self._merge_unique(current.goals, extracted.get("goals", [])),
            "facts": {**current.facts, **extracted.get("facts", {})},
            "updated_at": utc_now(),
        }

        document = await self._collection.find_one_and_update(
            {"user_id": user_id},
            {"$set": payload},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return self._to_profile(document)

    @staticmethod
    def _extract_profile_data(message: str) -> dict[str, Any]:
        data: dict[str, Any] = {
            "preferences": [],
            "habits": [],
            "goals": [],
            "facts": {},
        }

        name_patterns = [
            r"(?:my name is|i am|i'm)\s+([A-Za-z][A-Za-z\s]{0,30})",
            r"mera naam\s+([A-Za-z][A-Za-z\s]{0,30})\s+hai",
        ]
        for pattern in name_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                data["name"] = " ".join(match.group(1).split()).title()
                break

        preference_patterns = [
            r"(?:i like|i love)\s+(.+)",
            r"mujhe\s+(.+?)\s+pasand hai",
        ]
        for pattern in preference_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                value = UserProfileService._clean_fact(match.group(1))
                if value:
                    data["preferences"].append(value)
                break

        habit_patterns = [
            r"(?:i usually|i often|every day i)\s+(.+)",
            r"(?:main|mai)\s+roz\s+(.+)",
        ]
        for pattern in habit_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                value = UserProfileService._clean_fact(match.group(1))
                if value:
                    data["habits"].append(value)
                break

        goal_patterns = [
            r"(?:my goal is|i want to|i need to)\s+(.+)",
            r"(?:mera goal hai|mujhe|main)\s+(.+?)\s+(?:karna hai|achieve karna hai)",
        ]
        for pattern in goal_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                value = UserProfileService._clean_fact(match.group(1))
                if value:
                    data["goals"].append(value)
                break

        if data.get("name"):
            data["facts"]["preferred_name"] = data["name"]
        if data["preferences"]:
            data["facts"]["last_preference"] = data["preferences"][-1]
        if data["goals"]:
            data["facts"]["current_goal"] = data["goals"][-1]

        return data

    @staticmethod
    def _clean_fact(value: str) -> str:
        cleaned = re.sub(r"[.?!]+$", "", value).strip()
        return " ".join(cleaned.split())

    @staticmethod
    def _merge_unique(current: list[str], new_values: list[str]) -> list[str]:
        merged: list[str] = []
        for value in [*current, *new_values]:
            if value and value not in merged:
                merged.append(value)
        return merged

    @staticmethod
    def _to_profile(document: dict[str, Any]) -> UserProfile:
        return UserProfile(
            user_id=document["user_id"],
            name=document.get("name"),
            preferences=document.get("preferences", []),
            habits=document.get("habits", []),
            goals=document.get("goals", []),
            facts=document.get("facts", {}),
            updated_at=document.get("updated_at"),
        )

