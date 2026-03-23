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
                return True, "Boss, note thoda clear bol na."
            return True, "Theek hai Boss, note yaad rakh liya."

        if "show notes" in normalized or "show tasks" in normalized:
            notes = self.memory.notes()
            if not notes:
                return True, "Boss, abhi koi saved notes nahi hain."
            preview = ", ".join(item.get("text", "") for item in notes[:3] if item.get("text"))
            return True, f"Boss, saved notes ye hain: {preview}"

        reminder_match = re.search(r"(?:add task|add reminder)\s+(.+)", command, re.IGNORECASE)
        if reminder_match:
            text = reminder_match.group(1).strip()
            if not self.memory.add_reminder(text):
                return True, "Boss, reminder thoda clear bol."
            return True, "Ho gaya Boss, reminder save kar diya."

        if "show reminders" in normalized or "show schedule" in normalized:
            reminders = self.memory.reminders()
            if not reminders:
                return True, "Boss, abhi koi reminders saved nahi hain."
            preview = ", ".join(item.get("text", "") for item in reminders[:3] if item.get("text"))
            return True, f"Boss, reminders ye rahe: {preview}"

        if "organize downloads" in normalized:
            return True, self.organize_downloads()

        return False, ""

    def organize_downloads(self):
        downloads = Path.home() / "Downloads"
        if not downloads.exists():
            return "Boss, Downloads folder mil nahi raha."

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
            return "Boss, Downloads me organize karne layak files nahi mili."
        return f"Ho gaya Boss, Downloads organize ho gaye. {moved} files move hui hain."
