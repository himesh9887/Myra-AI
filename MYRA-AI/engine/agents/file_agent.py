from __future__ import annotations

from engine.file_engine import FileEngine

from .base_agent import BaseAgent


class FileAgent(BaseAgent):
    name = "file"

    def __init__(self, base_dir, files=None):
        self.files = files or FileEngine(base_dir)

    def handle(self, command: str):
        return self.files.handle(command)

    def execute(self, task):
        task = self.normalize_task(task)
        action = task.action.lower()
        payload = task.payload
        meta = task.meta

        if action == "open_file":
            return self.files.open_file(payload)
        if action == "create_file":
            return self.files.create_file(payload)
        if action == "create_folder":
            return self.files.create_folder(payload)
        if action == "delete_file":
            return self.files.delete_file(payload)
        if action == "rename_file":
            return self.files.rename_file(meta.get("old_name", ""), meta.get("new_name", payload))
        if action == "search_file":
            return self.files.search_files(payload)

        handled, message = self.handle(payload)
        return message if handled else ""
