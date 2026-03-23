from __future__ import annotations

from datetime import datetime


class BehaviorEngine:
    def __init__(self, memory):
        self.memory = memory

    def record_activity(self, snapshot):
        if not isinstance(snapshot, dict):
            return {}

        active_app = str(snapshot.get("active_app", "")).strip().lower()
        category = str(snapshot.get("category", "")).strip().lower()
        delta_seconds = int(snapshot.get("delta_seconds", 0) or 0)
        if not active_app or delta_seconds <= 0:
            return self.summary()

        block = self._time_block()
        minutes = round(delta_seconds / 60, 2)
        profile = self.memory.behavior_profile()

        app_minutes = dict(profile.get("app_minutes", {}))
        app_minutes[active_app] = round(float(app_minutes.get(active_app, 0)) + minutes, 2)

        study_windows = dict(profile.get("study_windows", {}))
        coding_windows = dict(profile.get("coding_windows", {}))
        if category in {"study", "productive", "coding"}:
            study_windows[block] = int(study_windows.get(block, 0)) + delta_seconds
        if category == "coding" or active_app in {"vscode", "cursor", "pycharm", "github"}:
            coding_windows[block] = int(coding_windows.get(block, 0)) + delta_seconds

        night_count = int(profile.get("night_activity_count", 0))
        if datetime.now().hour >= 22:
            night_count += 1

        preferred_study_time = self._dominant_window(study_windows)
        coding_schedule = self._dominant_window(coding_windows)
        frequent_apps = [name for name, _ in sorted(app_minutes.items(), key=lambda item: item[1], reverse=True)[:5]]
        sleep_time = "around 11:30 PM" if night_count >= 8 else "around 10:30 PM"

        return self.memory.update_behavior_profile(
            {
                "app_minutes": app_minutes,
                "study_windows": study_windows,
                "coding_windows": coding_windows,
                "preferred_study_time": preferred_study_time,
                "coding_schedule": coding_schedule,
                "frequent_apps": frequent_apps,
                "sleep_time": sleep_time,
                "night_activity_count": night_count,
            }
        )

    def record_study_progress(self, hours):
        try:
            duration_seconds = int(float(hours) * 3600)
        except (TypeError, ValueError):
            return self.summary()
        payload = {
            "active_app": "study",
            "category": "study",
            "delta_seconds": max(0, duration_seconds),
        }
        return self.record_activity(payload)

    def summary(self):
        profile = self.memory.behavior_profile()
        if not profile.get("frequent_apps"):
            profile["frequent_apps"] = self.memory.top_apps(limit=5)
        return profile

    def study_mode_prompt(self, name="Boss"):
        preferred = str(self.summary().get("preferred_study_time", "")).strip().lower()
        if not preferred:
            return ""
        labels = {
            "morning": "subah",
            "afternoon": "dopahar",
            "evening": "shaam",
            "night": "raat",
        }
        label = labels.get(preferred, preferred)
        return f"Boss, mujhe lagta hai tum usually {label} me study karte ho. Kya mai {label} study mode start karu?"

    def _dominant_window(self, buckets):
        if not buckets:
            return ""
        return max(buckets, key=buckets.get)

    def _time_block(self):
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "morning"
        if 12 <= hour < 17:
            return "afternoon"
        if 17 <= hour < 21:
            return "evening"
        return "night"
