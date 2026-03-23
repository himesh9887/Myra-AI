from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from engine.agent_manager import AgentManager


@dataclass(frozen=True)
class PlannedStep:
    step: str
    agent: str
    action: str
    payload: str
    meta: dict


class TaskPlanner:
    def __init__(self, base_dir=None, agent_manager=None, memory=None):
        root = Path(base_dir) if base_dir else Path(__file__).resolve().parent.parent
        self.base_dir = root
        self.history_path = self.base_dir / "memory" / "task_history.json"
        self.agent_manager = agent_manager or AgentManager(root)
        self.memory = memory
        self._last_goal = ""
        self._last_agent = ""

    def configure_agents(self, **agents):
        self.agent_manager.configure_agents(**agents)

    def latest_snapshot(self) -> dict:
        return {
            "goal": self._last_goal or "Standby",
            "agent": self._last_agent or "idle",
        }

    def handle(self, command):
        raw = " ".join(str(command).strip().split())
        normalized = raw.lower()
        if not normalized:
            return False, ""

        if normalized.startswith("plan "):
            goal = raw[5:].strip()
            return True, self._format_plan(goal)

        if not self._looks_like_goal(normalized):
            return False, ""

        return True, self.execute_task(raw)

    def plan_task(self, goal):
        objective = " ".join(str(goal).strip().split())
        if not objective:
            return {"goal": "", "steps": []}
        return {"goal": objective, "steps": self.create_steps(objective)}

    def create_steps(self, goal):
        lowered = goal.lower()

        if self._is_research_goal(lowered):
            topic = self._clean_goal(goal, ["research", "research about", "find information about", "analyze"])
            return [
                PlannedStep("Search the web for the topic", "browser", "search_google", topic, {}),
                PlannedStep("Collect information from the internet", "research", "collect_information", topic, {}),
                PlannedStep("Summarize findings clearly", "research", "summarize_results", topic, {}),
            ]

        if self._is_download_goal(lowered):
            topic = self._clean_goal(goal, ["download"])
            return [
                PlannedStep("Search Google for trusted sources", "browser", "search_google", f"{topic} download", {}),
                PlannedStep("Open a likely source website", "browser", "open_website", "google.com", {}),
                PlannedStep("Locate the download flow", "download", "download_search_result", topic, {}),
                PlannedStep("Attempt the file download", "download", "download_search_result", topic, {}),
            ]

        if self._is_automation_goal(lowered):
            return [
                PlannedStep("Execute the automation sequence", "automation", "handle", goal, {}),
            ]

        if self._is_whatsapp_goal(lowered):
            return [
                PlannedStep("Execute the communication task", "whatsapp", "handle", goal, {}),
            ]

        if self._is_multi_goal(lowered):
            return self._steps_from_segments(goal)

        step_text, agent, action, payload, meta = self._default_agent_step(goal)
        return [PlannedStep(step_text, agent, action, payload, meta)]

    def execute_task(self, goal):
        plan = self.plan_task(goal)
        self._last_goal = plan["goal"]
        results = []
        status = "completed"

        for step in plan["steps"]:
            self._last_agent = step.agent
            payload = {
                "agent": step.agent,
                "action": step.action,
                "payload": step.payload,
                "meta": dict(step.meta),
            }
            result = self.agent_manager.execute(payload) or f"Boss, {step.step.lower()} abhi complete nahi ho paaya."
            results.append(
                {
                    "step": step.step,
                    "agent": step.agent,
                    "action": step.action,
                    "payload": step.payload,
                    "result": result,
                }
            )
            lowered = str(result).lower()
            if any(token in lowered for token in ["could not", "nahi", "error", "issue", "partial", "not available"]):
                status = "partial"

        history_entry = {
            "goal": plan["goal"],
            "status": status,
            "steps": results,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._append_history(history_entry)
        return self._format_execution_result(history_entry)

    def _format_plan(self, goal):
        plan = self.plan_task(goal)
        if not plan["goal"]:
            return "Boss, goal thoda blur hai... ek line me bol kya karna hai."

        lines = [f"Acha Boss, {plan['goal']} ke liye plan ye raha:"]
        for index, step in enumerate(plan["steps"], start=1):
            lines.append(f"{index}. {step.step} via {step.agent.title()}Agent")
        return " ".join(lines)

    def _format_execution_result(self, history_entry):
        lines = [f"Haan Boss, {history_entry['goal']} pe kaam chalu hai."]
        if history_entry["steps"]:
            lines.append(history_entry["steps"][-1]["result"])
        lines.append("Ho gaya Boss." if history_entry["status"] == "completed" else "Boss, kaafi part ho gaya... thoda scene abhi pending hai.")
        return " ".join(lines)

    def _steps_from_segments(self, goal):
        parts = [item.strip() for item in re.split(r"\b(?:and then|then|and)\b", goal, flags=re.IGNORECASE) if item.strip()]
        steps = []
        for part in parts:
            step_text, agent, action, payload, meta = self._default_agent_step(part)
            steps.append(PlannedStep(step_text, agent, action, payload, meta))
        return steps

    def _default_agent_step(self, goal):
        agent_name, _ = self.agent_manager.route(goal)
        if agent_name == "browser":
            return ("Open the browser task", "browser", "handle", goal, {})
        if agent_name == "research":
            return ("Research the requested topic", "research", "research", goal, {})
        if agent_name == "download":
            return ("Run the download workflow", "download", "handle", goal, {})
        if agent_name == "whatsapp":
            return ("Execute the WhatsApp task", "whatsapp", "handle", goal, {})
        if agent_name == "file":
            return ("Handle the file operation", "file", "handle", goal, {})
        if agent_name == "youtube":
            return ("Handle the media request", "youtube", "handle", goal, {})
        if agent_name == "system":
            return ("Execute the system action", "system", "handle", goal, {})
        if agent_name == "automation":
            return ("Execute the desktop automation", "automation", "handle", goal, {})
        if agent_name == "app":
            return ("Open or close the application", "app", "handle", goal, {})
        return ("Search the web for the goal", "browser", "search_google", goal, {})

    def _looks_like_goal(self, normalized):
        return any(
            [
                self._is_research_goal(normalized),
                self._is_download_goal(normalized),
                self._is_whatsapp_goal(normalized),
                self._is_automation_goal(normalized),
                self._is_multi_goal(normalized),
            ]
        )

    def _is_research_goal(self, normalized):
        tokens = ["research ", "best ", "compare ", "find information", "analyze ", "summary of "]
        return any(token in normalized for token in tokens)

    def _is_download_goal(self, normalized):
        return normalized.startswith("download ")

    def _is_whatsapp_goal(self, normalized):
        tokens = ["send message", "send file", "send image", "send voice", "voice message", "voice note", "call "]
        return any(token in normalized for token in tokens)

    def _is_automation_goal(self, normalized):
        tokens = [
            "move mouse",
            "drag mouse",
            "click",
            "type text",
            "press key",
            "press hotkey",
            "shortcut",
            "macro",
            "scroll ",
        ]
        return any(token in normalized for token in tokens)

    def _is_multi_goal(self, normalized):
        return any(token in normalized for token in [" and then ", " then ", " and "])

    def _clean_goal(self, goal, prefixes):
        cleaned = str(goal).strip()
        for prefix in prefixes:
            cleaned = re.sub(rf"^\s*{re.escape(prefix)}\s+", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    def _append_history(self, entry):
        if self.memory and hasattr(self.memory, "log_task"):
            self.memory.log_task(
                entry.get("goal", ""),
                entry.get("steps", []),
                entry.get("steps", [{}])[-1].get("result", ""),
                status=entry.get("status", "completed"),
                agent=self._last_agent,
            )
            return
        history = self._load_history()
        history.append(entry)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.write_text(json.dumps(history[-50:], indent=2, ensure_ascii=True), encoding="utf-8")

    def _load_history(self):
        if not self.history_path.exists():
            return []
        try:
            payload = json.loads(self.history_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return []
        return payload if isinstance(payload, list) else []
