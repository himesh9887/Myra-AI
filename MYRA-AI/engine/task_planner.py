import re

from engine.ai_brain import ask_ai


class TaskPlanner:
    def handle(self, command):
        raw = str(command).strip()
        normalized = raw.lower()

        if normalized.startswith("plan "):
            return True, self.plan_task(raw[5:].strip())

        if normalized.startswith("how to ") or "best " in normalized:
            return True, self.plan_task(raw)

        return False, ""

    def plan_task(self, task):
        objective = str(task).strip()
        if not objective:
            return "Sir ji, task objective clear nahi hai."

        prompt = (
            "Break this user task into 4 concise actionable desktop-assistant steps. "
            "Keep it practical and tool-oriented. Task: "
            f"{objective}"
        )
        plan = ask_ai(prompt)
        if plan.lower().startswith("ai service temporarily unavailable") or plan.lower().startswith("ai error"):
            return self._fallback_plan(objective)
        return f"Sir ji, task plan: {plan}"

    def _fallback_plan(self, task):
        if "download" in task.lower():
            return (
                "Sir ji, fallback plan: 1. search relevant sources. "
                "2. verify best result. 3. open download page. 4. save file locally."
            )
        return (
            "Sir ji, fallback plan: 1. understand the task. "
            "2. gather required info. 3. perform the action. 4. verify the result."
        )
