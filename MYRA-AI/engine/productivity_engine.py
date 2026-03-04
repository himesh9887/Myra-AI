import re
import shutil
from pathlib import Path


class ProductivityEngine:
    def __init__(self, base_dir, memory):
        self.base_dir = Path(base_dir)
        self.memory = memory

    def handle(self, command):
        normalized = command.lower().strip()

        note_match = re.search(r"(?:save note|note down|remember note)\s+(.+)", command, re.IGNORECASE)
        if note_match:
            text = note_match.group(1).strip()
            if not self.memory.save_note(text):
                return True, "Sir ji, note text clear nahi hai."
            return True, "Sir ji, note memory me save ho gaya hai."

        if "show notes" in normalized or "show tasks" in normalized:
            notes = self.memory.notes()
            if not notes:
                return True, "Sir ji, abhi koi saved notes nahi hain."
            preview = ", ".join(item.get("text", "") for item in notes[:3] if item.get("text"))
            return True, f"Sir ji, saved notes: {preview}"

        reminder_match = re.search(r"(?:add task|add reminder)\s+(.+)", command, re.IGNORECASE)
        if reminder_match:
            text = reminder_match.group(1).strip()
            if not self.memory.add_reminder(text):
                return True, "Sir ji, reminder text clear nahi hai."
            return True, "Sir ji, reminder save ho gaya hai."

        if "show reminders" in normalized or "show schedule" in normalized:
            reminders = self.memory.reminders()
            if not reminders:
                return True, "Sir ji, abhi koi reminders saved nahi hain."
            preview = ", ".join(item.get("text", "") for item in reminders[:3] if item.get("text"))
            return True, f"Sir ji, reminders: {preview}"

        if "organize downloads" in normalized:
            return True, self.organize_downloads()

        return False, ""

    def organize_downloads(self):
        downloads = Path.home() / "Downloads"
        if not downloads.exists():
            return "Sir ji, Downloads folder available nahi hai."

        buckets = {
            "Images": {".png", ".jpg", ".jpeg", ".gif", ".webp"},
            "Videos": {".mp4", ".mkv", ".mov", ".avi"},
            "Documents": {".pdf", ".doc", ".docx", ".txt", ".ppt", ".pptx", ".xls", ".xlsx"},
            "Archives": {".zip", ".rar", ".7z"},
            "Installers": {".exe", ".msi"},
        }

        moved = 0
        for item in downloads.iterdir():
            if not item.is_file():
                continue

            target_folder = None
            suffix = item.suffix.lower()
            for folder_name, extensions in buckets.items():
                if suffix in extensions:
                    target_folder = downloads / folder_name
                    break

            if target_folder is None:
                continue

            target_folder.mkdir(exist_ok=True)
            target_path = target_folder / item.name
            if target_path.exists():
                target_path = target_folder / f"{item.stem}_copy{item.suffix}"

            try:
                shutil.move(str(item), str(target_path))
                moved += 1
            except OSError:
                continue

        if moved == 0:
            return "Sir ji, Downloads me organize karne layak files nahi mili."
        return f"Sir ji, Downloads organize ho gaye. {moved} files move hui hain."
