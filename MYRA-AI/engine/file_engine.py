from pathlib import Path
import os
import re
import shutil


class FileEngine:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self._pending_confirmation = None

    def handle(self, command):
        raw_command = " ".join(str(command).strip().split())
        normalized = raw_command.lower().strip()
        if not normalized:
            return False, ""

        pending_reply = self._handle_pending_confirmation(raw_command)
        if pending_reply is not None:
            return True, pending_reply

        screenshot_folder = self._extract_screenshot_organize_payload(raw_command)
        if screenshot_folder is not None:
            return True, self.organize_screenshots(screenshot_folder)

        open_folder = self._extract_open_folder_payload(raw_command)
        if open_folder:
            return True, self.open_folder(open_folder)

        list_target = self._extract_list_files_payload(raw_command)
        if list_target is not None:
            return True, self.list_files(list_target)

        open_file = self._extract_open_file_payload(raw_command)
        if open_file:
            return True, self.open_file(open_file)

        create_folder = self._extract_payload(raw_command, ["create folder", "make folder", "folder banao", "ek folder banao"])
        if create_folder:
            return True, self.create_folder(create_folder)

        create_file = self._extract_payload(raw_command, ["create file", "make file", "file banao", "ek file banao"])
        if create_file:
            return True, self.create_file(create_file)

        write_file = self._extract_write_payload(raw_command)
        if write_file:
            target_name, content = write_file
            return True, self.write_file(target_name, content)

        delete_file = self._extract_payload(raw_command, ["delete file", "remove file", "file delete"])
        if delete_file:
            return True, self.delete_file(delete_file)

        rename_file = self._match_rename_payload(raw_command)
        if rename_file:
            old_name, new_name = rename_file
            return True, self.rename_file(old_name, new_name)

        search_file = self._extract_payload(raw_command, ["search file", "find file", "file search"])
        if search_file:
            return True, self.search_files(search_file)

        return False, ""

    def create_folder(self, name):
        target = self._resolve_folder_target(name)
        if target.exists():
            if target.is_dir():
                return f"Boss, folder {target.name} pehle se bana hua hai."
            return f"Boss, {target.name} naam se already file hai, folder nahi bana sakta."
        try:
            target.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            return f"Boss, folder create nahi ho paya. {exc}"
        return f"Ho gaya Boss, folder {target.name} create ho gaya."

    def create_file(self, name):
        target = self._resolve_target(name)
        if target.exists():
            if target.is_dir():
                return f"Boss, {target.name} folder hai, file nahi bana sakta."
            return f"Boss, file {target.name} pehle se hai."
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch(exist_ok=False)
        except OSError as exc:
            return f"Boss, file create nahi ho payi. {exc}"
        return f"Ho gaya Boss, file {target.name} create ho gayi."

    def write_file(self, name, content):
        target = self._resolve_target(name)
        text = str(content).strip()
        if not text:
            return "Boss, file me kya likhna hai woh thoda clear bol."
        if target.exists() and target.is_dir():
            return f"Boss, {target.name} folder hai, usme direct text write nahi kar sakta."
        if target.exists():
            self._pending_confirmation = {
                "kind": "write",
                "target": target,
                "content": text,
                "label": f"{target.name} ko overwrite",
            }
            return f"Boss, {target.name} already hai. Pakka overwrite karu?"
        return self._write_file(target, text)

    def open_file(self, name):
        target = self._resolve_target(name)
        if target.exists():
            if target.is_dir():
                return self.open_folder(str(target))
            try:
                os.startfile(str(target))
                return f"Arey Boss, {target.name} open kar diya."
            except OSError as exc:
                return f"Boss, file open nahi ho payi. {exc}"

        matches = self._find_matches(name, limit=1, files_only=True)
        if not matches:
            return f"Boss, {str(name).strip()} file mujhe nahi mili."

        try:
            os.startfile(str(matches[0]))
            return f"Arey Boss, {matches[0].name} open kar diya."
        except OSError as exc:
            return f"Boss, file open nahi ho payi. {exc}"

    def open_folder(self, name):
        target = self._resolve_folder_target(name)
        if target.exists() and target.is_dir():
            try:
                os.startfile(str(target))
                return f"Arey Boss, folder {target.name} open kar diya."
            except OSError as exc:
                return f"Boss, folder open nahi ho paya. {exc}"

        matches = self._find_matches(name, limit=1, dirs_only=True)
        if not matches:
            return f"Boss, {str(name).strip()} folder mujhe nahi mila."

        try:
            os.startfile(str(matches[0]))
            return f"Arey Boss, folder {matches[0].name} open kar diya."
        except OSError as exc:
            return f"Boss, folder open nahi ho paya. {exc}"

    def list_files(self, folder_name="."):
        target = self._resolve_folder_target(folder_name or ".")
        if target.exists() and target.is_file():
            return f"Boss, {target.name} file hai, folder nahi."
        if not target.exists():
            matches = self._find_matches(folder_name, limit=1, dirs_only=True)
            if matches:
                target = matches[0]
            else:
                return f"Boss, {str(folder_name).strip()} folder mujhe nahi mila."

        try:
            items = sorted(target.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
        except OSError as exc:
            return f"Boss, folder ke files nahi dekh pa raha. {exc}"

        if not items:
            return f"Boss, {target.name} folder abhi empty hai."

        preview = []
        for item in items[:10]:
            label = item.name + ("/" if item.is_dir() else "")
            preview.append(label)
        return f"Boss, {target.name} me ye items hain: {', '.join(preview)}"

    def delete_file(self, name):
        target = self._resolve_target(name)
        if not target.exists():
            return f"Boss, {target.name} file nahi mili."
        if target.is_dir():
            return "Boss, yeh folder hai. Delete file command se remove nahi hoga."
        self._pending_confirmation = {
            "kind": "delete",
            "target": target,
            "label": f"{target.name} ko delete",
        }
        return f"Boss, pakka delete karu {target.name}? Ye important ho sakta hai."

    def rename_file(self, old_name, new_name):
        source = self._resolve_target(old_name)
        if not source.exists():
            return f"Boss, {source.name} file nahi mili."

        target_name = str(new_name).strip().strip('"').strip("'")
        if not target_name:
            return "Boss, new file name clear nahi hai."

        target = source.with_name(target_name)
        if target.exists() and target.resolve() != source.resolve():
            if target.is_dir():
                return f"Boss, {target.name} folder already hai. Ispe rename nahi kar sakta."
            self._pending_confirmation = {
                "kind": "rename_overwrite",
                "source": source,
                "target": target,
                "label": f"{target.name} ko replace karke rename",
            }
            return f"Boss, {target.name} already hai. Pakka replace karke rename karu?"

        try:
            source.rename(target)
        except OSError as exc:
            return f"Boss, file rename nahi ho payi. {exc}"
        return f"Ho gaya Boss, {source.name} ka naam {target.name} kar diya."

    def search_files(self, name):
        query = str(name).strip().strip('"').strip("'")
        if not query:
            return "Boss, search query clear nahi hai."

        matches = self._find_matches(query, limit=5)
        if not matches:
            return f"Boss, {query} naam ki file mujhe nahi mili."

        preview = ", ".join(item.name for item in matches)
        return f"Boss, yeh matches mile: {preview}"

    def organize_screenshots(self, folder_name=""):
        target_root = self._default_screenshot_folder_root()
        target_root.mkdir(parents=True, exist_ok=True)

        clean_name = self._clean_screenshot_folder_name(folder_name) or "All_Screenshots"
        target_folder = target_root / clean_name
        target_folder.mkdir(parents=True, exist_ok=True)

        screenshot_files = self._collect_screenshot_files(exclude_dir=target_folder)
        if not screenshot_files:
            return "Boss, mujhe organize karne layak screenshots nahi mile."

        moved = 0
        for source in screenshot_files:
            destination = self._unique_target_path(target_folder / source.name)
            try:
                shutil.move(str(source), str(destination))
                moved += 1
            except OSError:
                continue

        if moved == 0:
            return "Boss, screenshots mile the, but move complete nahi ho paya."
        return f"Ho gaya Boss, {moved} screenshots ko {target_folder.name} folder me shift kar diya."

    def _write_file(self, target, content):
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(content), encoding="utf-8")
        except OSError as exc:
            return f"Boss, file write nahi ho payi. {exc}"
        return f"Ho gaya Boss, {target.name} me content likh diya."

    def _handle_pending_confirmation(self, raw_command):
        if not self._pending_confirmation:
            return None

        normalized = " ".join(str(raw_command).lower().split())
        if self._is_confirmation_reply(normalized):
            pending = self._pending_confirmation
            self._pending_confirmation = None
            return self._execute_pending_action(pending)
        if self._is_cancel_reply(normalized):
            label = self._pending_confirmation.get("label", "action")
            self._pending_confirmation = None
            return f"Theek hai Boss, {label} cancel kar diya."

        self._pending_confirmation = None
        return None

    def _execute_pending_action(self, pending):
        kind = pending.get("kind")
        if kind == "delete":
            target = pending.get("target")
            try:
                target.unlink()
            except OSError as exc:
                return f"Boss, file delete nahi ho payi. {exc}"
            return f"Ho gaya Boss, file {target.name} delete kar di."

        if kind == "write":
            return self._write_file(pending.get("target"), pending.get("content", ""))

        if kind == "rename_overwrite":
            source = pending.get("source")
            target = pending.get("target")
            try:
                source.replace(target)
            except OSError as exc:
                return f"Boss, rename complete nahi ho paya. {exc}"
            return f"Ho gaya Boss, {source.name} ko {target.name} se replace karke rename kar diya."

        return "Boss, confirmation wala action clear nahi tha."

    def _resolve_target(self, raw_name):
        cleaned = str(raw_name).strip().strip('"').strip("'")
        known_folder = self._known_folder_path(cleaned)
        if known_folder is not None:
            return known_folder
        target = Path(cleaned)
        if not target.is_absolute():
            target = self.base_dir / target
        return target

    def _resolve_folder_target(self, raw_name):
        cleaned = str(raw_name).strip().strip('"').strip("'")
        if cleaned in {"", ".", "current folder", "this folder", "is folder"}:
            return self.base_dir
        known_folder = self._known_folder_path(cleaned)
        if known_folder is not None:
            return known_folder
        target = Path(cleaned)
        if not target.is_absolute():
            target = self.base_dir / target
        return target

    def _known_folder_path(self, value):
        token = str(value).strip().lower()
        mapping = {
            "desktop": Path.home() / "Desktop",
            "downloads": Path.home() / "Downloads",
            "documents": Path.home() / "Documents",
        }
        return mapping.get(token)

    def _extract_payload(self, command, prefixes):
        lowered = str(command).lower().strip()
        for prefix in prefixes:
            lowered_prefix = str(prefix).lower()
            if lowered.startswith(lowered_prefix):
                return str(command)[len(prefix):].strip()
        return ""

    def _extract_open_file_payload(self, command):
        patterns = [
            r"^open file\s+(.+)$",
            r"^file open\s+(.+)$",
        ]
        return self._extract_first_match(command, patterns)

    def _extract_open_folder_payload(self, command):
        patterns = [
            r"^open folder\s+(.+)$",
            r"^folder open\s+(.+)$",
            r"^open directory\s+(.+)$",
        ]
        return self._extract_first_match(command, patterns)

    def _extract_list_files_payload(self, command):
        normalized = str(command).lower().strip()
        if normalized in {"list files", "show files", "is folder ke files dikha", "current folder ke files dikha"}:
            return "."
        patterns = [
            r"^list files in\s+(.+)$",
            r"^show files in\s+(.+)$",
            r"^files in\s+(.+)$",
            r"^folder ke files dikha\s+(.+)$",
        ]
        payload = self._extract_first_match(command, patterns)
        return payload or None

    def _extract_screenshot_organize_payload(self, command):
        normalized = self._normalize_screenshot_command(command)
        if "screenshot" not in normalized:
            return None

        folder_intent = any(token in normalized for token in ["folder", "organize", "shift", "move", "usme dal", "andar dal"])
        bulk_intent = any(token in normalized for token in ["jitne bhi", "sabhi", "saare", "all"])
        if not folder_intent and not bulk_intent:
            return None

        patterns = [
            r"folder\s+named\s+(.+?)(?:\s+(?:bana|bna|banado|banao|me|mein|main)\b|$)",
            r"folder\s+name\s+(.+?)(?:\s+(?:bana|bna|banado|banao|me|mein|main)\b|$)",
            r"(.+?)\s+naam\s+ka\s+folder",
            r"folder\s+(.+?)(?:\s+(?:bana|bna|banado|banao)\b|$)",
            r"in\s+folder\s+(.+)$",
            r"into\s+folder\s+(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized, re.IGNORECASE)
            if match:
                candidate = self._clean_screenshot_folder_name(match.group(1))
                if candidate:
                    return candidate
        return ""

    def _extract_write_payload(self, command):
        patterns = [
            r"^write file\s+(.+?)\s+(?:saying\s+|content\s+|with\s+content\s+)?(.+)$",
            r"^write in file\s+(.+?)\s+(?:saying\s+|content\s+|with\s+content\s+)?(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, str(command), re.IGNORECASE)
            if match:
                target = match.group(1).strip().strip('"').strip("'")
                content = match.group(2).strip()
                if target and content:
                    return target, content
        return None

    def _extract_first_match(self, command, patterns):
        for pattern in patterns:
            match = re.search(pattern, str(command), re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _match_rename_payload(self, command):
        normalized = str(command).lower().strip()
        if normalized.startswith("rename file "):
            payload = str(command)[len("rename file "):].strip()
        elif normalized.startswith("file rename "):
            payload = str(command)[len("file rename "):].strip()
        else:
            return None
        if " to " not in payload:
            return None

        old_name, new_name = payload.split(" to ", 1)
        old_name = old_name.strip()
        new_name = new_name.strip()
        if not old_name or not new_name:
            return None
        return old_name, new_name

    def _find_matches(self, query, limit, files_only=False, dirs_only=False):
        matches = []
        token = str(query).strip().strip('"').strip("'").lower()
        for item in self.base_dir.rglob("*"):
            if files_only and not item.is_file():
                continue
            if dirs_only and not item.is_dir():
                continue
            if token in item.name.lower():
                matches.append(item)
            if len(matches) == limit:
                break
        return matches

    def _is_confirmation_reply(self, normalized):
        tokens = {
            "yes",
            "yes boss",
            "haan",
            "haan boss",
            "ha",
            "ok",
            "okay",
            "confirm",
            "pakka",
            "kar do",
            "kardo",
            "kar de",
            "kr do",
            "krde",
            "do it",
        }
        return normalized in tokens

    def _is_cancel_reply(self, normalized):
        tokens = {
            "no",
            "no boss",
            "nahi",
            "nahi boss",
            "cancel",
            "mat karo",
            "rehne do",
            "chhodo",
            "skip",
        }
        return normalized in tokens

    def _normalize_screenshot_command(self, command):
        normalized = str(command).lower().strip()
        replacements = [
            (r"\bscreen shot\b", "screenshot"),
            (r"\bscreen short\b", "screenshot"),
            (r"\bscreeneshot\b", "screenshot"),
            (r"\bscreeneshort\b", "screenshot"),
            (r"\bscreenshort\b", "screenshot"),
            (r"\bss\b", "screenshot"),
        ]
        for pattern, target in replacements:
            normalized = re.sub(pattern, target, normalized)
        return " ".join(normalized.split())

    def _clean_screenshot_folder_name(self, value):
        candidate = str(value).strip().strip('"').strip("'")
        if not candidate:
            return ""
        candidate = re.sub(
            r"\b(?:ek|all|saare|sabhi|sbhi|sab|sabko|jitne|jitte|laptop|mein|main|me|screen|screenshot|screenshots|folder|bana|bna|banado|banao|usme|andar|dal|daal|de|aur|or|esi|aise|aisi|name|se)\b",
            " ",
            candidate,
            flags=re.IGNORECASE,
        )
        candidate = re.sub(r"[^\w\s-]", " ", candidate)
        words = [item for item in candidate.split() if item.strip()]
        stopwords = {"ek", "all", "saare", "sabhi", "sbhi", "sab", "aur", "or", "esi", "aise", "aisi", "name", "se"}
        words = [item for item in words if item.lower() not in stopwords]
        candidate = " ".join(words).strip(" -_")
        if len(candidate) < 3:
            return ""
        return candidate

    def _default_screenshot_folder_root(self):
        pictures = Path.home() / "Pictures"
        if pictures.exists():
            return pictures
        return self.base_dir

    def _screenshot_search_roots(self):
        home = Path.home()
        roots = [
            home / "Pictures" / "Screenshots",
            home / "Pictures",
            home / "Desktop",
            home / "Downloads",
            self.base_dir,
            home / "OneDrive" / "Pictures" / "Screenshots",
            home / "OneDrive" / "Pictures",
            home / "OneDrive" / "Desktop",
        ]
        existing = []
        seen = set()
        for root in roots:
            try:
                resolved = root.resolve()
            except Exception:
                resolved = root
            if not root.exists() or str(resolved).lower() in seen:
                continue
            seen.add(str(resolved).lower())
            existing.append(root)
        return existing

    def _collect_screenshot_files(self, exclude_dir=None):
        matches = []
        seen = set()
        exclude = exclude_dir.resolve() if isinstance(exclude_dir, Path) and exclude_dir.exists() else exclude_dir
        image_suffixes = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}

        for root in self._screenshot_search_roots():
            try:
                iterator = root.rglob("*")
            except OSError:
                continue
            for item in iterator:
                try:
                    if not item.is_file() or item.suffix.lower() not in image_suffixes:
                        continue
                    resolved = item.resolve()
                    if exclude is not None:
                        try:
                            resolved.relative_to(exclude)
                            continue
                        except ValueError:
                            pass
                    key = str(resolved).lower()
                    if key in seen or not self._is_screenshot_file(item):
                        continue
                    seen.add(key)
                    matches.append(resolved)
                except Exception:
                    continue
        return matches

    def _is_screenshot_file(self, path):
        name = path.stem.lower()
        parent = path.parent.name.lower()
        if "screenshot" in name or "screen shot" in name:
            return True
        if parent == "screenshots":
            return True
        return re.search(r"(^|[\s_-])ss($|[\s_-]|\d)", name) is not None

    def _unique_target_path(self, target):
        if not target.exists():
            return target
        counter = 1
        while True:
            candidate = target.with_name(f"{target.stem}_{counter}{target.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1
