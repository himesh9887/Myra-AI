import re


class SchedulerEngine:
    def __init__(self, memory):
        self.memory = memory
        self._callback = None

    def start(self, callback):
        self._callback = callback

    def handle(self, command):
        match = re.search(r"schedule\s+(.+?)\s+at\s+(\d{1,2}:\d{2})", command, re.IGNORECASE)
        if not match:
            return False, ""

        scheduled_command = match.group(1).strip()
        when = match.group(2).strip()
        self.memory.add_reminder(f"{scheduled_command} at {when}")
        return True, f"Sir ji, '{scheduled_command}' ko {when} ke liye schedule kar diya hai."
