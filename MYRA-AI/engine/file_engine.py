from pathlib import Path
import os


class FileEngine:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)

    def handle(self, command):
        raw_command = str(command).strip()
        normalized = raw_command.lower().strip()

        open_file = self._match_payload(raw_command, "open file")
        if open_file:
            return True, self.open_file(open_file)

        create_folder = self._match_payload(normalized, "create folder")
        if create_folder:
            return True, self.create_folder(create_folder)

        create_file = self._match_payload(normalized, "create file")
        if create_file:
            return True, self.create_file(create_file)

        delete_file = self._match_payload(normalized, "delete file")
        if delete_file:
            return True, self.delete_file(delete_file)

        rename_file = self._match_rename_payload(normalized)
        if rename_file:
            old_name, new_name = rename_file
            return True, self.rename_file(old_name, new_name)

        search_file = self._match_payload(normalized, "search file")
        if search_file:
            return True, self.search_files(search_file)

        find_file = self._match_payload(normalized, "find file")
        if find_file:
            return True, self.search_files(find_file)

        return False, ""

    def create_folder(self, name):
        target = self._resolve_target(name)
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return f"Sir ji, folder create nahi ho paya. {exc}"
        return f"Sir ji, folder {target.name} create ho gaya hai."

    def create_file(self, name):
        target = self._resolve_target(name)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch(exist_ok=True)
        except OSError as exc:
            return f"Sir ji, file create nahi ho payi. {exc}"
        return f"Sir ji, file {target.name} create ho gayi hai."

    def open_file(self, name):
        target = self._resolve_target(name)
        if target.exists():
            try:
                os.startfile(str(target))
                return f"Opening {target.name}."
            except OSError as exc:
                return f"Sir ji, file open nahi ho payi. {exc}"

        matches = self._find_matches(name, limit=1)
        if not matches:
            return f"Sir ji, {str(name).strip()} file mujhe nahi mili."

        try:
            os.startfile(str(matches[0]))
            return f"Opening {matches[0].name}."
        except OSError as exc:
            return f"Sir ji, file open nahi ho payi. {exc}"

    def delete_file(self, name):
        target = self._resolve_target(name)
        if not target.exists():
            return f"Sir ji, {target.name} file nahi mili."
        if target.is_dir():
            return "Sir ji, yeh folder hai. Delete file command se remove nahi hoga."
        try:
            target.unlink()
        except OSError as exc:
            return f"Sir ji, file delete nahi ho payi. {exc}"
        return f"Sir ji, file {target.name} delete ho gayi hai."

    def rename_file(self, old_name, new_name):
        source = self._resolve_target(old_name)
        if not source.exists():
            return f"Sir ji, {source.name} file nahi mili."

        target_name = str(new_name).strip().strip('"').strip("'")
        if not target_name:
            return "Sir ji, new file name clear nahi hai."

        target = source.with_name(target_name)
        try:
            source.rename(target)
        except OSError as exc:
            return f"Sir ji, file rename nahi ho payi. {exc}"
        return f"Sir ji, {source.name} ka naam {target.name} kar diya hai."

    def search_files(self, name):
        query = str(name).strip().strip('"').strip("'")
        if not query:
            return "Sir ji, search query clear nahi hai."

        matches = self._find_matches(query, limit=3)

        if not matches:
            return f"Sir ji, {query} naam ki file mujhe nahi mili."

        preview = ", ".join(item.name for item in matches)
        return f"Sir ji, yeh matches mile: {preview}"

    def _resolve_target(self, raw_name):
        cleaned = str(raw_name).strip().strip('"').strip("'")
        target = Path(cleaned)
        if not target.is_absolute():
            target = self.base_dir / target
        return target

    def _match_payload(self, command, prefix):
        lowered = str(command).lower()
        lowered_prefix = str(prefix).lower()
        if not lowered.startswith(lowered_prefix):
            return ""
        return str(command)[len(prefix):].strip()

    def _match_rename_payload(self, command):
        if not command.startswith("rename file "):
            return None

        payload = command[len("rename file "):].strip()
        if " to " not in payload:
            return None

        old_name, new_name = payload.split(" to ", 1)
        old_name = old_name.strip()
        new_name = new_name.strip()
        if not old_name or not new_name:
            return None
        return old_name, new_name

    def _find_matches(self, query, limit):
        matches = []
        token = str(query).strip().strip('"').strip("'").lower()
        for item in self.base_dir.rglob("*"):
            if token in item.name.lower():
                matches.append(item)
            if len(matches) == limit:
                break
        return matches
