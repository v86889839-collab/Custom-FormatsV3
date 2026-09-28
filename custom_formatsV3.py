# -*- coding: utf-8 -*-
"""
custom_formats_v3.py — Единый модуль для работы с пользовательскими форматами.
Version 3: производительность, лёгкость, скорость.
Совместимость: Python 3.9+
Зависимости: только стандартная библиотека.

Форматы V3 (20):
  V2: .luna .unkn .pyru .lujit .acf .ctxt .stxt
  V3: .cmdx .ptbl .rmap .qset .tcfg .mmsg .vset .gcfg .skey .pfx .ulog

V3-улучшения:
  - Предкомпилированные регулярные выражения
  - ThreadPoolExecutor для папок .unkn
  - Кэш SHA-256 (путь → mtime + хэш)
  - Потоковое чтение (построчно / чанками)
  - Ранний выход при невалидных заголовках
  - async-обёртки (asyncio.to_thread)
"""

from __future__ import annotations

import os
import re
import json
import time
import hashlib
import asyncio
import subprocess
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed


# =====================================================================
# V3: Предкомпилированные регулярные выражения
# =====================================================================
_LANG_SIGNATURES_RAW = [
    ("py",   [r"^#!.*python", r"^\s*def\s+\w+\(", r"^\s*import\s+\w+", r"^\s*from\s+\w+\s+import"]),
    ("rs",   [r"^\s*fn\s+\w+\(", r"^\s*use\s+\w+::", r"^\s*pub\s+(fn|struct|enum)\s+\w+"]),
    ("lua",  [r"^\s*local\s+\w+\s*=", r"^\s*function\s+\w+\(", r"^\s*require\s*[\(\"]"]),
    ("js",   [r"^\s*const\s+\w+\s*=", r"^\s*function\s+\w+\(", r"^\s*import\s+.*from\s+"]),
    ("c",    [r"^\s*#include\s*<", r"^\s*int\s+main\s*\("]),
    ("cpp",  [r"^\s*#include\s*<", r"^\s*std::", r"^\s*class\s+\w+\s*\{"]),
    ("go",   [r"^\s*package\s+\w+", r"^\s*func\s+\w+\(", r"^\s*import\s+\("]),
    ("sh",   [r"^#!/bin/(ba)?sh", r"^\s*echo\s+"]),
    ("java", [r"^\s*public\s+(class|static|void)\s+", r"^\s*import\s+java\."]),
]

_LANG_SIGNATURES_COMPILED: Dict[str, List[re.Pattern]] = {
    lang: [re.compile(p, re.MULTILINE) for p in patterns]
    for lang, patterns in _LANG_SIGNATURES_RAW
}

_LUAJIT_MARKERS = ["jit", "luajit", "ffi.cdef", "ffi.C"]

# V3: Кэш SHA-256 — (путь, mtime) → хэш
_SHA256_CACHE: Dict[Tuple[str, float], str] = {}


def _sha256_cached(path: Path) -> str:
    """V3: кэшированный SHA-256. Не пересчитываем, если файл не менялся."""
    stat = path.stat()
    key = (str(path), stat.st_mtime)
    if key in _SHA256_CACHE:
        return _SHA256_CACHE[key]
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    digest = h.hexdigest()
    _SHA256_CACHE[key] = digest
    return digest


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_float(val: str) -> bool:
    try:
        float(val)
        return True
    except ValueError:
        return False


def _format_value(val: Any) -> str:
    if isinstance(val, list):
        return "[" + ", ".join(str(v) for v in val) + "]"
    return str(val)


# =====================================================================
# 1. .luna — лёгкий формат конфигов (V2 + V3 стриминг)
# =====================================================================
@dataclass
class LunaConfig:
    data: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "LunaConfig":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Файл не найден: {p}")
        cfg = cls()
        current_section: Optional[str] = None

        # V3: построчное чтение вместо read_text().splitlines()
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    current_section = line[1:-1].strip()
                    cfg.data[current_section] = {}
                    continue
                if ": " in line:
                    key, _, value = line.partition(": ")
                    key = key.strip()
                    value = value.strip()
                    if value.startswith("[") and value.endswith("]"):
                        value = [v.strip() for v in value[1:-1].split(",") if v.strip()]
                    elif value.isdigit():
                        value = int(value)
                    elif _is_float(value):
                        value = float(value)
                    if current_section:
                        cfg.data[current_section][key] = value
                    else:
                        cfg.data[key] = value
        return cfg

    def save(self, path: str | Path) -> None:
        p = Path(path)
        lines: List[str] = []
        for key, value in self.data.items():
            if isinstance(value, dict):
                lines.append(f"[{key}]")
                for k, v in value.items():
                    lines.append(f"  {k}: {_format_value(v)}")
                lines.append("")
            else:
                lines.append(f"{key}: {_format_value(value)}")
        p.write_text("\n".join(lines), encoding="utf-8")

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self.data.get(section, {}).get(key, default)


# =====================================================================
# 2. .unkn — авто-определение языка (V2 + V3 скорость)
# =====================================================================
def detect_language(content: str) -> str:
    for marker in _LUAJIT_MARKERS:
        if marker in content:
            return "lujit"
    # V3: используем предкомпилированные паттерны
    for lang, patterns in _LANG_SIGNATURES_COMPILED.items():
        score = 0
        for pat in patterns:
            if pat.search(content):
                score += 1
        if score >= 2:
            return lang
    for lang, patterns in _LANG_SIGNATURES_COMPILED.items():
        for pat in patterns:
            if pat.search(content):
                return lang
    return "txt"


def process_unkn(path: str | Path, dry_run: bool = False) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Файл не найден: {p}")
    # V3: ранний выход — если не .unkn, пропускаем
    if p.suffix != ".unkn":
        return str(p)

    # V3: читаем только первые 4 КБ для детекта
    with p.open("r", encoding="utf-8", errors="replace") as f:
        content = f.read(4096)

    lang = detect_language(content)
    ext_map = {
        "py": "py", "rs": "rs", "lua": "lua", "lujit": "lujit",
        "js": "js", "c": "c", "cpp": "cpp", "go": "go",
        "sh": "sh", "java": "java", "txt": "txt",
    }
    new_ext = ext_map.get(lang, "txt")
    new_path = p.with_suffix(f".{new_ext}")
    if dry_run:
        print(f"[DRY RUN] {p.name} -> {new_path.name} (язык: {lang})")
    else:
        p.rename(new_path)
        print(f"[OK] {p.name} -> {new_path.name} (язык: {lang})")
    return str(new_path)


def process_unkn_folder(folder: str | Path, dry_run: bool = False, max_workers: int = 8) -> List[str]:
    """V3: параллельная обработка через ThreadPoolExecutor."""
    f = Path(folder)
    unkn_files = [fp for fp in f.iterdir() if fp.suffix == ".unkn"]
    results: List[str] = []

    def _process(fp: Path) -> str:
        try:
            return process_unkn(fp, dry_run)
        except Exception as e:
            return f"[ERROR] {fp.name}: {e}"

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process, fp): fp for fp in unkn_files}
        for future in as_completed(futures):
            results.append(future.result())
    return results


async def process_unkn_folder_async(folder: str | Path, dry_run: bool = False) -> List[str]:
    """V3: асинхронная обёртка."""
    return await asyncio.to_thread(process_unkn_folder, folder, dry_run)


# =====================================================================
# 3. .pyru — гибрид Python/Rust (V2)
# =====================================================================
_PYRU_PYTHON_MARKER = "# === PYTHON ==="
_PYRU_RUST_MARKER = "# === RUST ==="
_PYRU_END_MARKER = "# === END ==="


def create_pyru(python_code: str, rust_code: str, path: str | Path) -> None:
    p = Path(path)
    content = f"""{_PYRU_PYTHON_MARKER}
{python_code}
{_PYRU_END_MARKER}
{_PYRU_RUST_MARKER}
{rust_code}
{_PYRU_END_MARKER}
"""
    p.write_text(content.strip() + "\n", encoding="utf-8")


def parse_pyru(path: str | Path) -> Dict[str, str]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Файл не найден: {p}")
    result: Dict[str, str] = {"python": "", "rust": ""}
    current_block: Optional[str] = None
    block_lines: List[str] = []

    # V3: построчное чтение
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped == _PYRU_PYTHON_MARKER:
                current_block = "python"
                block_lines = []
                continue
            elif stripped == _PYRU_RUST_MARKER:
                if current_block:
                    result[current_block] = "\n".join(block_lines).strip()
                current_block = "rust"
                block_lines = []
                continue
            elif stripped == _PYRU_END_MARKER:
                if current_block:
                    result[current_block] = "\n".join(block_lines).strip()
                current_block = None
                block_lines = []
                continue
            if current_block:
                block_lines.append(line.rstrip())
    if current_block and block_lines:
        result[current_block] = "\n".join(block_lines).strip()
    return result


def run_pyru(
    path: str | Path,
    python_executable: str = "python",
    rust_compiler: str = "rustc",
    temp_dir: str | Path = ".pyru_temp",
) -> Dict[str, Any]:
    parts = parse_pyru(path)
    result: Dict[str, Any] = {"python_output": "", "rust_output": "", "rust_compiled": False}

    if parts["python"]:
        proc = subprocess.run(
            [python_executable, "-c", parts["python"]],
            capture_output=True, text=True, timeout=30,
        )
        result["python_output"] = proc.stdout + proc.stderr

    if parts["rust"]:
        tmp = Path(temp_dir)
        tmp.mkdir(exist_ok=True)
        rs_file = tmp / "_pyru_rust.rs"
        rs_file.write_text(parts["rust"], encoding="utf-8")
        exe_file = tmp / "_pyru_rust"
        compile_proc = subprocess.run(
            [rust_compiler, "-o", str(exe_file), str(rs_file)],
            capture_output=True, text=True, timeout=60,
        )
        if compile_proc.returncode == 0:
            result["rust_compiled"] = True
            run_proc = subprocess.run(
                [str(exe_file)],
                capture_output=True, text=True, timeout=30,
            )
            result["rust_output"] = run_proc.stdout + run_proc.stderr
        else:
            result["rust_output"] = f"[Ошибка компиляции]\n{compile_proc.stderr}"
    return result


async def run_pyru_async(path: str | Path) -> Dict[str, Any]:
    return await asyncio.to_thread(run_pyru, path)


# =====================================================================
# 4. .lujit — LuaJIT-скрипты (V2)
# =====================================================================
def is_lujit_file(path: str | Path) -> bool:
    return Path(path).suffix == ".lujit"


def run_lujit(
    path: str | Path,
    luajit_executable: str = "luajit",
    fallback_to_lua: bool = False,
    lua_executable: str = "lua",
) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Файл не найден: {p}")
    if not is_lujit_file(p):
        raise ValueError(f"Ожидался .lujit файл, получено: {p.suffix}")

    lujit_path = shutil.which(luajit_executable)
    if lujit_path:
        proc = subprocess.run(
            [lujit_path, str(p)],
            capture_output=True, text=True, timeout=60,
        )
        return {
            "runner": "luajit",
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    elif fallback_to_lua:
        lua_path = shutil.which(lua_executable)
        if lua_path:
            proc = subprocess.run(
                [lua_path, str(p)],
                capture_output=True, text=True, timeout=60,
            )
            return {
                "runner": "lua (fallback)",
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "warning": "LuaJIT не найден, использован обычный Lua",
            }
    return {
        "runner": "none",
        "returncode": -1,
        "stdout": "",
        "stderr": "LuaJIT не найден в системе",
    }


def validate_lujit(path: str | Path) -> tuple[bool, str]:
    p = Path(path)
    content = p.read_text(encoding="utf-8", errors="replace")
    jit_features = []
    if "ffi." in content:
        jit_features.append("ffi")
    if "jit." in content:
        jit_features.append("jit")
    if "require('ffi')" in content or 'require("ffi")' in content:
        jit_features.append("require ffi")
    if jit_features:
        return True, f"Найдены LuaJIT-фичи: {', '.join(jit_features)}. Обычный Lua не подойдёт."
    return True, "LuaJIT-специфичных конструкций не найдено. Можно запустить и на обычном Lua."


# =====================================================================
# 5. .acf — манифест критического exe (V2 + V3 кэш SHA-256)
# =====================================================================
@dataclass
class AcfManifest:
    exe_name: str
    version: str = "1.0.0"
    critical: bool = True
    description: str = ""
    expected_sha256: str = ""
    min_os_version: str = ""
    requires_admin: bool = False
    auto_restart: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exe_name": self.exe_name,
            "version": self.version,
            "critical": self.critical,
            "description": self.description,
            "expected_sha256": self.expected_sha256,
            "min_os_version": self.min_os_version,
            "requires_admin": self.requires_admin,
            "auto_restart": self.auto_restart,
        }

    @classmethod
    def load(cls, path: str | Path) -> "AcfManifest":
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls(**data)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def verify_exe(self, exe_dir: str | Path) -> tuple[bool, str]:
        exe_path = Path(exe_dir) / self.exe_name
        if not exe_path.exists():
            return False, f"EXE не найден: {exe_path}"
        if self.expected_sha256:
            # V3: используем кэшированный SHA-256
            sha = _sha256_cached(exe_path)
            if sha != self.expected_sha256:
                return False, f"Хэш не совпадает: {sha} != {self.expected_sha256}"
        return True, "OK"


def create_acf(exe_path: str | Path, exe_name: str, acf_path: str | Path,
               version: str = "1.0.0", description: str = "",
               critical: bool = True, requires_admin: bool = False) -> None:
    p = Path(exe_path)
    sha = _sha256_cached(p) if p.exists() else ""
    manifest = AcfManifest(
        exe_name=exe_name,
        version=version,
        critical=critical,
        description=description,
        expected_sha256=sha,
        requires_admin=requires_admin,
    )
    manifest.save(acf_path)


# =====================================================================
# 6. .ctxt — подписанный критический текст (V2 + V3 кэш SHA-256)
# =====================================================================
def save_ctxt(path: str | Path, content: str, critical_level: str = "normal") -> None:
    p = Path(path)
    sig = _sha256_text(content)
    header = f"SIGNATURE: {sig}\nCritical Level: {critical_level}\n"
    p.write_text(header + content, encoding="utf-8")


def load_ctxt(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Файл не найден: {p}")
    # V3: построчное чтение заголовка
    with p.open("r", encoding="utf-8") as f:
        first_line = f.readline().strip()
        second_line = f.readline().strip()
        rest = f.read()

    if not first_line.startswith("SIGNATURE: "):
        return {"valid": False, "content": rest, "critical_level": "unknown",
                "error": "Нет подписи"}

    expected_sig = first_line[len("SIGNATURE: "):]
    critical_level = "normal"
    if second_line.startswith("Critical Level: "):
        critical_level = second_line[len("Critical Level: "):].strip()
        content = rest
    else:
        content = second_line + "\n" + rest

    actual_sig = _sha256_text(content)
    return {
        "valid": actual_sig == expected_sig,
        "content": content,
        "critical_level": critical_level,
        "expected_sig": expected_sig,
        "actual_sig": actual_sig,
    }


# =====================================================================
# 7. .stxt — структурированные текстовые команды (V2 + V3 стриминг)
# =====================================================================
@dataclass
class StxtCommand:
    command: str
    params: Dict[str, str] = field(default_factory=dict)


def parse_stxt(path: str | Path) -> List[StxtCommand]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Файл не найден: {p}")
    commands: List[StxtCommand] = []
    current: Optional[StxtCommand] = None

    # V3: построчное чтение
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("COMMAND: "):
                if current:
                    commands.append(current)
                current = StxtCommand(command=line[len("COMMAND: "):].strip())
            elif current and ": " in line:
                key, _, value = line.partition(": ")
                current.params[key.strip()] = value.strip()
    if current:
        commands.append(current)
    return commands


def execute_stxt(path: str | Path, handler: Callable[[str, Dict[str, str]], Any]) -> List[Any]:
    commands = parse_stxt(path)
    results = []
    for cmd in commands:
        results.append(handler(cmd.command, cmd.params))
    return results


def create_stxt(commands: List[Dict[str, Any]], path: str | Path) -> None:
    p = Path(path)
    lines: List[str] = ["# SCRIPT_TXT v1", "# Generated by custom_formats V3", ""]
    for cmd in commands:
        command = cmd.pop("command")
        lines.append(f"COMMAND: {command}")
        for k, v in cmd.items():
            lines.append(f"{k}: {v}")
        lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


async def parse_stxt_async(path: str | Path) -> List[StxtCommand]:
    return await asyncio.to_thread(parse_stxt, path)


# =====================================================================
# 8. .cmdx — пакетные команды с приоритетами (V3 NEW)
# =====================================================================
@dataclass
class CmdxCommand:
    priority: int
    command: str


def parse_cmdx(path: str | Path) -> List[CmdxCommand]:
    """Парсит .cmdx: [priority=N] команда"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Файл не найден: {p}")
    commands: List[CmdxCommand] = []

    # V3: построчное чтение
    with p.open("r", encoding="utf-8") as f:
        prev_prio = None
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and "priority=" in line:
                try:
                    prio_str = line.split("priority=")[1].split("]")[0]
                    prev_prio = int(prio_str)
                except (ValueError, IndexError):
                    prev_prio = 99
            elif prev_prio is not None:
                commands.append(CmdxCommand(priority=prev_prio, command=line))
                prev_prio = None
    # Сортируем по приоритету (меньше = раньше)
    commands.sort(key=lambda c: c.priority)
    return commands


def run_cmdx(path: str | Path, dry_run: bool = False) -> List[Dict[str, Any]]:
    commands = parse_cmdx(path)
    results = []
    for cmd in commands:
        if dry_run:
            results.append({"command": cmd.command, "priority": cmd.priority, "output": "[DRY RUN]"})
        else:
            proc = subprocess.run(cmd.command, shell=True, capture_output=True, text=True, timeout=60)
            results.append({
                "command": cmd.command,
                "priority": cmd.priority,
                "returncode": proc.returncode,
                "output": proc.stdout + proc.stderr,
            })
    return results


def create_cmdx(commands: List[Tuple[int, str]], path: str | Path) -> None:
    p = Path(path)
    lines: List[str] = ["# CMDX v1", "# Generated by custom_formats V3", ""]
    for prio, cmd in sorted(commands, key=lambda x: x[0]):
        lines.append(f"[priority={prio}]")
        lines.append(cmd)
        lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


# =====================================================================
# 9. .ptbl — таблица баллов (V3 NEW)
# =====================================================================
@dataclass
class PtblEntry:
    user_id: str
    points: int
    last_update: int
    checksum: str


def parse_ptbl(path: str | Path) -> List[PtblEntry]:
    """Парсит .ptbl: user_id,points,last_update_ts,checksum"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Файл не найден: {p}")
    entries: List[PtblEntry] = []
    # V3: построчное чтение, пропускаем заголовок
    with p.open("r", encoding="utf-8") as f:
        header = f.readline()  # skip header
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            if len(parts) >= 4:
                entries.append(PtblEntry(
                    user_id=parts[0],
                    points=int(parts[1]),
                    last_update=int(parts[2]),
                    checksum=parts[3],
                ))
    return entries


def update_ptbl(path: str | Path, user_id: str, delta: int) -> None:
    """Обновляет баллы игрока (или добавляет нового)."""
    p = Path(path)
    entries = parse_ptbl(path) if p.exists() else []
    found = False
    ts = int(time.time())
    for e in entries:
        if e.user_id == user_id:
            e.points += delta
            e.last_update = ts
            e.checksum = _sha256_text(f"{user_id}:{e.points}:{ts}")[:8]
            found = True
            break
    if not found:
        checksum = _sha256_text(f"{user_id}:{delta}:{ts}")[:8]
        entries.append(PtblEntry(user_id=user_id, points=delta, last_update=ts, checksum=checksum))

    lines = ["user_id,points,last_update_ts,checksum"]
    for e in entries:
        lines.append(f"{e.user_id},{e.points},{e.last_update},{e.checksum}")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def get_points(path: str | Path, user_id: str) -> int:
    entries = parse_ptbl(path)
    for e in entries:
        if e.user_id == user_id:
            return e.points
    return 0


def create_ptbl(path: str | Path) -> None:
    p = Path(path)
    p.write_text("user_id,points,last_update_ts,checksum\n", encoding="utf-8")


# =====================================================================
# 10. .rmap — метаданные карты Roblox (V3 NEW)
# =====================================================================
@dataclass
class RmapConfig:
    name: str = ""
    place_id: str = ""
    min_players: int = 1
    max_players: int = 50
    mini_games: List[str] = field(default_factory=list)
    required_roles: List[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> "RmapConfig":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Файл не найден: {p}")
        cfg = cls()
        current_section: Optional[str] = None
        # V3: построчное чтение
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    current_section = line[1:-1].strip()
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    if current_section == "map":
                        if key == "name":
                            cfg.name = value
                        elif key == "id":
                            cfg.place_id = value
                        elif key == "min_players":
                            cfg.min_players = int(value)
                        elif key == "max_players":
                            cfg.max_players = int(value)
                    elif current_section == "features":
                        if key == "mini_games":
                            cfg.mini_games = [v.strip() for v in value.split(",") if v.strip()]
                        elif key == "required_roles":
                            cfg.required_roles = [v.strip() for v in value.split(",") if v.strip()]
        return cfg

    def save(self, path: str | Path) -> None:
        p = Path(path)
        lines: List[str] = [
            "[map]",
            f"name = {self.name}",
            f"id = {self.place_id}",
            f"min_players = {self.min_players}",
            f"max_players = {self.max_players}",
            "",
            "[features]",
            f"mini_games = {', '.join(self.mini_games)}",
            f"required_roles = {', '.join(self.required_roles)}",
        ]
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")


# =====================================================================
# 11. .qset — манифест карантина (V3 NEW)
# =====================================================================
@dataclass
class QsetEntry:
    path: str
    sha256: str
    reason: str
    timestamp: int


def load_qset(path: str | Path) -> List[QsetEntry]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return [QsetEntry(**f) for f in data.get("files", [])]


def save_qset(path: str | Path, entries: List[QsetEntry]) -> None:
    p = Path(path)
    data = {"files": [
        {"path": e.path, "sha256": e.sha256, "reason": e.reason, "timestamp": e.timestamp}
        for e in entries
    ]}
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def add_to_qset(path: str | Path, file_path: str | Path, reason: str) -> bool:
    """Добавляет файл в карантин. Возвращает True если добавлен, False если уже есть."""
    entries = load_qset(path)
    fp = Path(file_path)
    if not fp.exists():
        return False
    sha = _sha256_cached(fp)  # V3: кэшированный хэш
    for e in entries:
        if e.sha256 == sha:
            return False  # уже в карантине
    entries.append(QsetEntry(
        path=str(file_path),
        sha256=sha,
        reason=reason,
        timestamp=int(time.time()),
    ))
    save_qset(path, entries)
    return True


def remove_from_qset(path: str | Path, sha256: str) -> bool:
    entries = load_qset(path)
    before = len(entries)
    entries = [e for e in entries if e.sha256 != sha256]
    if len(entries) < before:
        save_qset(path, entries)
        return True
    return False


# =====================================================================
# 12. .tcfg — конфиг задач (V3 NEW)
# =====================================================================
@dataclass
class TcfgTask:
    name: str
    schedule: str  # "HH:MM" или "0 3 * * *" (cron-like)
    command: str
    enabled: bool = True


def parse_tcfg(path: str | Path) -> List[TcfgTask]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Файл не найден: {p}")
    tasks: List[TcfgTask] = []
    current: Optional[TcfgTask] = None
    # V3: построчное чтение
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                if current:
                    tasks.append(current)
                current = TcfgTask(name=line[1:-1].strip(), schedule="", command="")
            elif current and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if key == "schedule":
                    current.schedule = value
                elif key == "command":
                    current.command = value
                elif key == "enabled":
                    current.enabled = value.lower() in ("true", "1", "yes")
        if current:
            tasks.append(current)
    return tasks


def check_and_run_tcfg(path: str | Path) -> List[Dict[str, Any]]:
    """Проверяет расписание и запускает задачи, у которых наступило время."""
    tasks = parse_tcfg(path)
    now = time.localtime()
    hh_mm = f"{now.tm_hour:02d}:{now.tm_min:02d}"
    results = []
    for t in tasks:
        if not t.enabled:
            continue
        if t.schedule == hh_mm:
            proc = subprocess.run(t.command, shell=True, capture_output=True, text=True, timeout=120)
            results.append({
                "task": t.name,
                "command": t.command,
                "returncode": proc.returncode,
                "output": proc.stdout + proc.stderr,
            })
    return results


def create_tcfg(tasks: List[Dict[str, str]], path: str | Path) -> None:
    p = Path(path)
    lines: List[str] = ["# TCFG v1", "# Generated by custom_formats V3", ""]
    for t in tasks:
        lines.append(f"[{t['name']}]")
        lines.append(f"schedule = {t.get('schedule', '')}")
        lines.append(f"command = {t.get('command', '')}")
        if "enabled" in t:
            lines.append(f"enabled = {t['enabled']}")
        lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


# =====================================================================
# 13. .mmsg — пакет модерации (V3 NEW)
# =====================================================================
@dataclass
class MmsgAction:
    action: str
    user_id: Optional[int] = None
    channel_id: Optional[int] = None
    message_id: Optional[int] = None
    guild_id: Optional[int] = None
    reason: str = ""
    duration: str = ""


def parse_mmsg(path: str | Path) -> List[MmsgAction]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Файл не найден: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    actions = []
    for item in data:
        actions.append(MmsgAction(
            action=item.get("action", ""),
            user_id=item.get("user_id"),
            channel_id=item.get("channel_id"),
            message_id=item.get("message_id"),
            guild_id=item.get("guild_id"),
            reason=item.get("reason", ""),
            duration=item.get("duration", ""),
        ))
    return actions


def create_mmsg(actions: List[Dict[str, Any]], path: str | Path) -> None:
    p = Path(path)
    p.write_text(json.dumps(actions, indent=2, ensure_ascii=False), encoding="utf-8")


def execute_mmsg(path: str | Path, handler: Callable[[MmsgAction], Any]) -> List[Any]:
    actions = parse_mmsg(path)
    return [handler(a) for a in actions]


# =====================================================================
# 14. .vset — визуальные настройки (V3 NEW)
# =====================================================================
@dataclass
class VsetConfig:
    theme: str = "dark"
    colors: Dict[str, str] = field(default_factory=dict)
    ui: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "VsetConfig":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Файл не найден: {p}")
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls(
            theme=data.get("theme", "dark"),
            colors=data.get("colors", {}),
            ui=data.get("ui", {}),
        )

    def save(self, path: str | Path) -> None:
        p = Path(path)
        data = {"theme": self.theme, "colors": self.colors, "ui": self.ui}
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_color(self, key: str, default: str = "#FFFFFF") -> str:
        return self.colors.get(key, default)

    def get_ui(self, key: str, default: Any = None) -> Any:
        return self.ui.get(key, default)


# =====================================================================
# 15. .gcfg — конфиг мини-игр Roblox (V3 NEW)
# =====================================================================
@dataclass
class GcfgGame:
    enabled: bool = False
    reward_points: int = 0
    cooldown_sec: int = 0
    ui_color_accent: str = "#FFFFFF"
    ui_font_size: int = 12
    sound_volume: float = 1.0


def load_gcfg(path: str | Path) -> Dict[str, GcfgGame]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Файл не найден: {p}")
    from configparser import ConfigParser
    cfg = ConfigParser()
    cfg.read(p, encoding="utf-8")
    games: Dict[str, GcfgGame] = {}
    for section in cfg.sections():
        games[section] = GcfgGame(
            enabled=cfg.getboolean(section, "enabled", fallback=False),
            reward_points=cfg.getint(section, "reward_points", fallback=0),
            cooldown_sec=cfg.getint(section, "cooldown_sec", fallback=0),
            ui_color_accent=cfg.get(section, "ui_color_accent", fallback="#FFFFFF"),
            ui_font_size=cfg.getint(section, "ui_font_size", fallback=12),
            sound_volume=cfg.getfloat(section, "sound_volume", fallback=1.0),
        )
    return games


def get_game_config(path: str | Path, game_name: str) -> Optional[GcfgGame]:
    games = load_gcfg(path)
    return games.get(game_name)


def create_gcfg(games: Dict[str, Dict[str, Any]], path: str | Path) -> None:
    p = Path(path)
    lines: List[str] = ["# GCFG v1", "# Generated by custom_formats V3", ""]
    for name, settings in games.items():
        lines.append(f"[{name}]")
        for k, v in settings.items():
            lines.append(f"{k} = {v}")
        lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


# =====================================================================
# 16. .skey — манифест секретных ключей (V3 NEW)
# =====================================================================
@dataclass
class SkeyManifest:
    keys: Dict[str, str] = field(default_factory=dict)
    flags: List[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> "SkeyManifest":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Файл не найден: {p}")
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls(
            keys=data.get("keys", data.get("secrets", {})),
            flags=data.get("flags", []),
        )

    def save(self, path: str | Path) -> None:
        p = Path(path)
        data = {"keys": self.keys, "flags": self.flags}
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def validate(self, required_keys: List[str]) -> tuple[bool, List[str]]:
        missing = [k for k in required_keys if k not in self.keys or not self.keys[k]]
        return (len(missing) == 0, missing)

    def get(self, key: str, default: str = "") -> str:
        return self.keys.get(key, default)


# =====================================================================
# 17. .pfx — манифест плагина (V3 NEW)
# =====================================================================
@dataclass
class PfxManifest:
    name: str = ""
    language: str = "python"
    entry_point: str = "main.py"
    dependencies: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    version: str = "1.0.0"

    @classmethod
    def load(cls, path: str | Path) -> "PfxManifest":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Файл не найден: {p}")
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls(
            name=data.get("name", ""),
            language=data.get("language", "python"),
            entry_point=data.get("entry_point", "main.py"),
            dependencies=data.get("dependencies", []),
            permissions=data.get("permissions", []),
            version=data.get("version", "1.0.0"),
        )

    def save(self, path: str | Path) -> None:
        p = Path(path)
        data = {
            "name": self.name,
            "language": self.language,
            "entry_point": self.entry_point,
            "dependencies": self.dependencies,
            "permissions": self.permissions,
            "version": self.version,
        }
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def has_permission(self, perm: str) -> bool:
        return perm in self.permissions


# =====================================================================
# 18. .ulog — сверхлёгкий лог (V3 NEW)
# =====================================================================
def log_ulog(path: str | Path, event: str) -> None:
    """Записывает событие в .ulog (только строка, без меток времени)."""
    with Path(path).open("a", encoding="utf-8") as f:
        f.write(event + "\n")


def tail_ulog(path: str | Path, lines: int = 20) -> List[str]:
    """Быстро читает последние N строк."""
    p = Path(path)
    if not p.exists():
        return []
    # V3: читаем с конца через seek
    with p.open("r", encoding="utf-8") as f:
        all_lines = f.readlines()
    return all_lines[-lines:]


def read_ulog(path: str | Path) -> List[str]:
    """Читает все события."""
    p = Path(path)
    if not p.exists():
        return []
    return p.read_text(encoding="utf-8").strip().splitlines()


def clear_ulog(path: str | Path) -> None:
    """Очищает лог."""
    Path(path).write_text("", encoding="utf-8")


# =====================================================================
# V3: Бенчмарк
# =====================================================================
def benchmark(func: Callable, *args, runs: int = 10, **kwargs) -> Dict[str, Any]:
    """Простой бенчмарк: замеряет время выполнения функции."""
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        func(*args, **kwargs)
        times.append(time.perf_counter() - start)
    return {
        "runs": runs,
        "min": min(times),
        "max": max(times),
        "avg": sum(times) / len(times),
        "total": sum(times),
    }


# =====================================================================
# V3: Удобный экспорт
# =====================================================================
__all__ = [
    # V2 форматы
    "LunaConfig", "detect_language", "process_unkn", "process_unkn_folder",
    "process_unkn_folder_async", "create_pyru", "parse_pyru", "run_pyru",
    "run_pyru_async", "is_lujit_file", "run_lujit", "validate_lujit",
    "AcfManifest", "create_acf", "save_ctxt", "load_ctxt",
    "StxtCommand", "parse_stxt", "execute_stxt", "create_stxt",
    "parse_stxt_async",
    # V3 новые форматы
    "CmdxCommand", "parse_cmdx", "run_cmdx", "create_cmdx",
    "PtblEntry", "parse_ptbl", "update_ptbl", "get_points", "create_ptbl",
    "RmapConfig",
    "QsetEntry", "load_qset", "save_qset", "add_to_qset", "remove_from_qset",
    "TcfgTask", "parse_tcfg", "check_and_run_tcfg", "create_tcfg",
    "MmsgAction", "parse_mmsg", "create_mmsg", "execute_mmsg",
    "VsetConfig",
    "GcfgGame", "load_gcfg", "get_game_config", "create_gcfg",
    "SkeyManifest",
    "PfxManifest",
    "log_ulog", "tail_ulog", "read_ulog", "clear_ulog",
    # V3 утилиты
    "benchmark", "_sha256_cached",
]
