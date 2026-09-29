# Custom File Formats Toolkit V3

A collection of custom file formats and Python parsers/generators for automation, Discord bots, system utilities, and Roblox server management.

Version 3 focuses on three core principles: **Performance**, **Lightweight**, **Speed**.

## What's New in V3

- **Pre-compiled regex** — language detection patterns compiled once at startup
- **SHA-256 cache** — no re-hashing unchanged files (in-memory dict: path → mtime + hash)
- **Streaming reads** — line-by-line parsing instead of `read_text()` for `.luna`, `.stxt`, `.pyru`, `.cmdx`, `.tcfg`
- **ThreadPoolExecutor** — parallel `.unkn` folder processing (8 workers by default)
- **Early exit** — check file extension and first bytes before full parse
- **Async wrappers** — `process_unkn_folder_async`, `run_pyru_async`, `parse_stxt_async`
- **11 new formats** — `.cmdx`, `.ptbl`, `.rmap`, `.qset`, `.tcfg`, `.mmsg`, `.vset`, `.gcfg`, `.skey`, `.pfx`, `.ulog`
- **Benchmark utility** — built-in `benchmark()` function for profiling
## What i need to download?

python (main, code will no work if no python)
rustc .pyru format
luajit .lujit format
lua (luajit fallback)

## Formats Overview (20 total)

| Format | Purpose | Typical Use Case | Version |
|--------|---------|------------------|---------|
| `.luna` | Lightweight config with sections | Bot configs (prefixes, roles, settings) | V2 |
| `.unkn` | Auto-detected code placeholder | Plugin system, dynamic code delivery | V2 |
| `.pyru` | Hybrid Python/Rust script | Multi-language command modules | V2 |
| `.lujit` | LuaJIT-ready scripts | In-game logic, fast scripting for Roblox/bots | V2 |
| `.acf` | Application Critical Manifest (JSON) | Integrity checks, version control, admin flags | V2 |
| `.ctxt` | Critical Text with SHA-256 signature | Signed rules, moderation policies, verified configs | V2 |
| `.stxt` | Structured text commands | Bot command batching, moderation actions, point systems | V2 |
| `.cmdx` | Batch commands with priorities | LUnlocker task execution, system automation | V3 |
| `.ptbl` | Point table with checksums | Roblox/Discord player points, mini-game rewards | V3 |
| `.rmap` | Roblox map metadata | Server map config, mini-game selection, role requirements | V3 |
| `.qset` | Quarantine set manifest | LUnlocker file quarantine with SHA-256 dedup | V3 |
| `.tcfg` | Task config (scheduler) | LUnlocker scheduled scans, cleanups, backups | V3 |
| `.mmsg` | Moderation message batch | Roblox/Discord ban/kick/warn batches via bot | V3 |
| `.vset` | Visual settings (JSON) | LUnlocker UI themes, colors, fonts | V3 |
| `.gcfg` | Game config for Roblox mini-games | Toggle games, set rewards, UI colors, sound volume | V3 |
| `.skey` | Secret key manifest | API tokens, Discord bot tokens, access flags | V3 |
| `.pfx` | Plugin flex manifest | Dynamic plugin loading for ReBoot/LUnlocker | V3 |
| `.ulog` | Ultra-light log | Maximum-speed event logging without timestamps | V3 |

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/v86889839-collab/Custom-FormatsV3.git
cd custom-formats
```

### 2. Generate all test files

```bash
python generators/gen_all.py
```

### 3. Test the parsers (V3)

```bash
python custom_formatsV3.py
```

Example output:

```text
✅ Detected language for mystery.unkn → .py
✅ Parsed config.luna: bot.name = ReBoot, bot.prefix = r!
✅ Verified rules.ctxt signature: VALID
✅ Parsed actions.stxt: 8 commands ready for execution
✅ Processed 5 .unkn files in parallel (8 workers)
✅ Quarantine set loaded: 3 files tracked
✅ Task schedule loaded: 2 tasks configured
```

## V3 Performance Improvements

### Pre-compiled Regex

```python
# Patterns compiled once at module load — no recompilation per file
from custom_formats_v3 import detect_language
lang = detect_language(content)  # uses _LANG_SIGNATURES_COMPILED
```

### SHA-256 Cache

```python
from custom_formats_v3 import _sha256_cached
# First call: computes hash, caches (path, mtime) → hash
# Subsequent calls: returns cached hash if file unchanged
sha = _sha256_cached(Path("app.exe"))
```

### Parallel .unkn Processing

```python
from custom_formats_v3 import process_unkn_folder
# 50 files processed in parallel instead of sequentially
results = process_unkn_folder("./uploads/", max_workers=8)
```

### Async Wrappers

```python
import asyncio
from custom_formats_v3 import process_unkn_folder_async, parse_stxt_async

async def main():
    results = await process_unkn_folder_async("./uploads/")
    commands = await parse_stxt_async("actions.stxt")

asyncio.run(main())
```

### Streaming Reads

```python
# .luna, .stxt, .pyru, .cmdx, .tcfg now read line-by-line
# No more read_text().splitlines() — lower memory usage
from custom_formats_v3 import LunaConfig
cfg = LunaConfig.load("config.luna")  # streams lines, doesn't load entire file
```

### Benchmark

```python
from custom_formats_v3 import benchmark, process_unkn_folder
result = benchmark(process_unkn_folder, "./uploads/", runs=10)
print(f"Avg: {result['avg']:.4f}s, Min: {result['min']:.4f}s")
```

## Format Details

### `.luna` — Lightweight Config with Sections

**Use case:** Discord bot configs (ReBoot), quick settings for utilities.

Example (`config.luna`):

```ini
[bot]
name = ReBoot
prefix = r!
version = 2.3.1

[roles]
mod = 123456789012345678
helper = 876543210987654321

[settings]
max_users = 200
timeout_sec = 180
log_level = INFO
```

```python
from custom_formats_v3 import LunaConfig

cfg = LunaConfig.load("config.luna")
bot_name = cfg.get("bot", "name")        # "ReBoot"
mod_role_id = cfg.get("roles", "mod")    # 123456789012345678
```

---

### `.unkn` — Auto-Detected Code Placeholder

**V3:** Reads only first 4 KB for detection. Parallel folder processing.

```python
from custom_formats_v3 import process_unkn, process_unkn_folder

process_unkn("mystery.unkn")           # → mystery.py
process_unkn_folder("./uploads/")       # parallel, 8 workers

# Async version
import asyncio
from custom_formats_v3 import process_unkn_folder_async
results = asyncio.run(process_unkn_folder_async("./uploads/"))
```

---

### `.pyru` — Hybrid Python/Rust Script

**V3:** Streaming line-by-line parsing.

```python
from custom_formats_v3 import parse_pyru, create_pyru, run_pyru, run_pyru_async

parts = parse_pyru("hybrid.pyru")
python_code = parts["python"]
rust_code = parts["rust"]

# Async execution
result = asyncio.run(run_pyru_async("hybrid.pyru"))
```

---

### `.lujit` — LuaJIT-Ready Scripts

```python
from custom_formats_v3 import validate_lujit, run_lujit

valid, msg = validate_lujit("test.lujit")
result = run_lujit("test.lujit", fallback_to_lua=True)
```

---

### `.acf` — Application Critical Manifest

**V3:** SHA-256 cache for `verify_exe`.

```python
from custom_formats_v3 import AcfManifest, create_acf

create_acf("app.exe", "app.exe", "app.acf", description="Critical module")
manifest = AcfManifest.load("app.acf")
ok, msg = manifest.verify_exe(".")
```

---

### `.ctxt` — Critical Text with SHA-256 Signature

```python
from custom_formats_v3 import save_ctxt, load_ctxt

save_ctxt("rules.ctxt", "Правила модерации...", critical_level="high")
data = load_ctxt("rules.ctxt")
print(f"Valid: {data['valid']}")
```

---

### `.stxt` — Structured Text Commands

**V3:** Streaming line-by-line parsing. Async wrapper available.

```python
from custom_formats_v3 import parse_stxt, execute_stxt, create_stxt, parse_stxt_async

cmds = parse_stxt("actions.stxt")
for c in cmds:
    print(c.command, c.params)

def my_handler(command, params):
    print(f"Executing {command} with {params}")

execute_stxt("actions.stxt", handler=my_handler)

# Async
cmds = asyncio.run(parse_stxt_async("actions.stxt"))
```

---

### `.cmdx` — Batch Commands with Priorities (V3 NEW)

**Use case:** LUnlocker task execution, system automation. Commands execute by priority (lower number = earlier).

Example (`tasks.cmdx`):

```text
# CMDX v1
[priority=1]
timeout /t 2

[priority=2]
taskkill /f /im notepad.exe

[priority=3]
start calc.exe
```

```python
from custom_formats_v3 import parse_cmdx, run_cmdx, create_cmdx

# Parse
commands = parse_cmdx("tasks.cmdx")
for c in commands:
    print(f"P{c.priority}: {c.command}")

# Execute (sorted by priority)
results = run_cmdx("tasks.cmdx")

# Dry run
results = run_cmdx("tasks.cmdx", dry_run=True)

# Create
create_cmdx([(1, "echo hello"), (2, "dir")], "new.cmdx")
```

---

### `.ptbl` — Point Table (V3 NEW)

**Use case:** Roblox/Discord player points with checksums.

Example (`points.ptbl`):

```text
user_id,points,last_update_ts,checksum
123456789012345678,240,1729987654,a1b2c3d4
987654321098765432,89,1729987001,e5f6g7h8
```

```python
from custom_formats_v3 import create_ptbl, update_ptbl, get_points, parse_ptbl

create_ptbl("points.ptbl")
update_ptbl("points.ptbl", "123456789012345678", 100)   # add 100 points
update_ptbl("points.ptbl", "987654321098765432", -10)   # remove 10 points
pts = get_points("points.ptbl", "123456789012345678")   # 100

entries = parse_ptbl("points.ptbl")
for e in entries:
    print(f"{e.user_id}: {e.points} pts")
```

---

### `.rmap` — Roblox Map Metadata (V3 NEW)

**Use case:** Server map config, mini-game selection, role requirements.

Example (`pbcc_v3.rmap`):

```ini
[map]
name = PBCC_v3
id = 12345678
min_players = 2
max_players = 50

[features]
mini_games = pizza_place, disaster_survival
required_roles = player, verified
```

```python
from custom_formats_v3 import RmapConfig

rmap = RmapConfig.load("pbcc_v3.rmap")
print(rmap.name)              # "PBCC_v3"
print(rmap.mini_games)        # ["pizza_place", "disaster_survival"]
print(rmap.required_roles)   # ["player", "verified"]
```

---

### `.qset` — Quarantine Set Manifest (V3 NEW)

**Use case:** LUnlocker file quarantine with SHA-256 deduplication.

**V3:** Uses cached SHA-256 for dedup checks.

Example (`quarantine.qset`):

```json
{
  "files": [
    {
      "path": "C:\\temp\\bad.exe",
      "sha256": "a1b2c3d4e5f6...",
      "reason": "heuristic_match",
      "timestamp": 1729988000
    }
  ]
}
```

```python
from custom_formats_v3 import add_to_qset, load_qset, remove_from_qset

# Add file to quarantine (dedup by SHA-256)
added = add_to_qset("quarantine.qset", "C:\\temp\\bad.exe", "heuristic_match")
# added = True if new, False if already quarantined

# List quarantined files
entries = load_qset("quarantine.qset")
for e in entries:
    print(f"{e.path}: {e.reason}")

# Remove from quarantine
remove_from_qset("quarantine.qset", "a1b2c3d4e5f6...")
```

---

### `.tcfg` — Task Config / Scheduler (V3 NEW)

**Use case:** LUnlocker scheduled scans, cleanups, backups.

Example (`tasks.tcfg`):

```ini
[daily_scan]
schedule = 03:00
command = lunlocker.exe --scan --quarantine

[weekly_cleanup]
schedule = 02:00
command = lunlocker.exe --clean-temp
enabled = false
```

```python
from custom_formats_v3 import parse_tcfg, check_and_run_tcfg, create_tcfg

# Parse tasks
tasks = parse_tcfg("tasks.tcfg")
for t in tasks:
    print(f"{t.name}: {t.schedule} → {t.command}")

# Check and run tasks whose time has come
results = check_and_run_tcfg("tasks.tcfg")

# Create
create_tcfg([
    {"name": "daily_scan", "schedule": "03:00", "command": "lunlocker.exe --scan"},
    {"name": "weekly_cleanup", "schedule": "02:00", "command": "lunlocker.exe --clean"},
], "new.tcfg")
```

---

### `.mmsg` — Moderation Message Batch (V3 NEW)

**Use case:** Roblox/Discord ban/kick/warn batches via bot.

Example (`mod_actions.mmsg`):

```json
[
  {"action": "ban", "user_id": 123456789, "reason": "cheating", "guild_id": 987654321},
  {"action": "kick", "user_id": 987654321, "reason": "spam"},
  {"action": "warn", "user_id": 111222333, "reason": "language"}
]
```

```python
from custom_formats_v3 import parse_mmsg, execute_mmsg, create_mmsg

actions = parse_mmsg("mod_actions.mmsg")
for a in actions:
    print(f"{a.action}: user={a.user_id}, reason={a.reason}")

# Execute via custom handler
def my_handler(action):
    print(f"Executing {action.action} on {action.user_id}")

execute_mmsg("mod_actions.mmsg", handler=my_handler)

# Create
create_mmsg([
    {"action": "ban", "user_id": 123, "reason": "cheating"},
], "new.mmsg")
```

---

### `.vset` — Visual Settings (V3 NEW)

**Use case:** LUnlocker UI themes, colors, fonts.

Example (`theme.vset`):

```json
{
  "theme": "dark",
  "colors": {
    "bg": "#1e1e1e",
    "accent": "#007acc",
    "text": "#ffffff"
  },
  "ui": {
    "corner_radius": 8,
    "font_family": "Segoe UI"
  }
}
```

```python
from custom_formats_v3 import VsetConfig

vset = VsetConfig.load("theme.vset")
print(vset.theme)                     # "dark"
print(vset.get_color("accent"))       # "#007acc"
print(vset.get_ui("font_family"))    # "Segoe UI"
```

---

### `.gcfg` — Game Config for Roblox Mini-Games (V3 NEW)

**Use case:** Toggle mini-games, set rewards, UI colors, sound volume. Bot reads this and applies settings to the Roblox server.

Example (`games.gcfg`):

```ini
[pizza_place]
enabled = true
reward_points = 15
cooldown_sec = 180
ui_color_accent = #FF5733
ui_font_size = 16
sound_volume = 0.8

[disaster_survival]
enabled = false
reward_points = 30
cooldown_sec = 300
ui_color_accent = #33FF57
ui_font_size = 14
sound_volume = 1.0
```

```python
from custom_formats_v3 import load_gcfg, get_game_config, create_gcfg

# Load all games
games = load_gcfg("games.gcfg")
for name, cfg in games.items():
    print(f"{name}: enabled={cfg.enabled}, points={cfg.reward_points}")

# Get single game config
pizza = get_game_config("games.gcfg", "pizza_place")
print(pizza.ui_color_accent)   # "#FF5733"
print(pizza.sound_volume)      # 0.8

# Create
create_gcfg({
    "pizza_place": {"enabled": "true", "reward_points": 15, "ui_color_accent": "#FF5733"},
}, "new.gcfg")
```

---

### `.skey` — Secret Key Manifest (V3 NEW)

**Use case:** API tokens, Discord bot tokens, access flags. **Do not store real tokens in project files.**

Example (`secrets.skey`):

```json
{
  "keys": {
    "discord_token": "placeholder_required",
    "roblox_api_key": "placeholder_required"
  },
  "flags": ["allow_oauth", "require_admin"]
}
```

```python
from custom_formats_v3 import SkeyManifest

skey = SkeyManifest.load("secrets.skey")

# Validate that all required keys are present
ok, missing = skey.validate(["discord_token", "roblox_api_key"])
if not ok:
    print(f"Missing keys: {missing}")

# Get a key value
token = skey.get("discord_token")
```

---

### `.pfx` — Plugin Flex Manifest (V3 NEW)

**Use case:** Dynamic plugin loading for ReBoot/LUnlocker.

Example (`auto_fix.pfx`):

```json
{
  "name": "auto_fix_unkn",
  "language": "python",
  "entry_point": "main.py",
  "dependencies": ["custom_formats"],
  "permissions": ["file_read", "file_write"],
  "version": "1.0.0"
}
```

```python
from custom_formats_v3 import PfxManifest

pfx = PfxManifest.load("auto_fix.pfx")
print(pfx.name)                      # "auto_fix_unkn"
print(pfx.has_permission("file_read"))  # True
```

---

### `.ulog` — Ultra-Light Log (V3 NEW)

**Use case:** Maximum-speed event logging without timestamps or levels.

Example (`events.ulog`):

```text
scan_start
file_detected:C:\temp\bad.exe
quarantine_ok
scan_end
```

```python
from custom_formats_v3 import log_ulog, tail_ulog, read_ulog, clear_ulog

# Write event (just a string, no formatting overhead)
log_ulog("events.ulog", "scan_start")
log_ulog("events.ulog", "file_detected:C:\\temp\\bad.exe")

# Read last N lines
recent = tail_ulog("events.ulog", lines=10)

# Read all
all_events = read_ulog("events.ulog")

# Clear
clear_ulog("events.ulog")
```

## Integration Guide

### For ReBoot (Discord Bot)

| Format | How to integrate |
|--------|-----------------|
| `.luna` | Load `config.luna` on bot startup to set prefix, roles, limits |
| `.unkn` | `!auto-fix` scans `uploads/` in parallel, renames files by language |
| `.stxt` | `!run-script` reads `.stxt` and executes commands in sequence |
| `.ctxt` | Load signed moderation rules on startup, reject if signature invalid |
| `.mmsg` | `!batch-mod` reads `.mmsg` and executes ban/kick/warn batches |
| `.ptbl` | Track player points across Roblox mini-games |
| `.gcfg` | Toggle mini-games, set rewards, UI colors, sound volume |
| `.skey` | Load bot tokens and API keys at startup with validation |
| `.pfx` | Dynamic plugin loading with permission checks |
| `.ulog` | Fast event logging for bot actions |
| `.lujit` | Run in-game logic scripts via LuaJIT subprocess |
| `.pyru` | Advanced plugin modules with Python (bot API) + Rust (perf-critical) |

### For LUnlocker (System Utility)

| Format | How to integrate |
|--------|-----------------|
| `.acf` | Verify integrity of critical `.exe` files before launch (cached SHA-256) |
| `.ctxt` | Load signed security policies, refuse to run if tampered |
| `.cmdx` | Execute system commands by priority |
| `.qset` | Quarantine files with SHA-256 deduplication |
| `.tcfg` | Schedule scans, cleanups, backups |
| `.vset` | UI theme and visual settings |
| `.stxt` | Batch operations: clean → verify → restart service |
| `.unkn` | Analyze unknown files before execution |
| `.ulog` | Ultra-fast event logging |
| `.skey` | API keys and access flags |

### For Roblox Server

| Format | How to integrate |
|--------|-----------------|
| `.rmap` | Map metadata: name, place ID, player limits, mini-games |
| `.gcfg` | Mini-game settings: rewards, cooldowns, UI colors, sounds |
| `.ptbl` | Player point tracking with checksums |
| `.mmsg` | Batch moderation: bans, kicks, warns |

## VS Code Setup

Add to `settings.json`:

```json
{
  "files.associations": {
    "*.luna": "ini",
    "*.lujit": "lua",
    "*.pyru": "python",
    "*.stxt": "plaintext",
    "*.ctxt": "plaintext",
    "*.acf": "json",
    "*.unkn": "plaintext",
    "*.cmdx": "plaintext",
    "*.ptbl": "csv",
    "*.rmap": "ini",
    "*.qset": "json",
    "*.tcfg": "ini",
    "*.mmsg": "json",
    "*.vset": "json",
    "*.gcfg": "ini",
    "*.skey": "json",
    "*.pfx": "json",
    "*.ulog": "plaintext"
  }
}
```

## Project Structure

```
custom-formats/
├── custom_formats.py            # V2 core parser module (7 formats)
├── custom_formats_v3.py          # V3 core parser module (20 formats + perf)
├── generators/
│   ├── gen_all.py                # Run all generators at once
│   ├── gen_luna.py               # Generate config.luna
│   ├── gen_unkn.py               # Generate mystery.unkn
│   ├── gen_pyru.py               # Generate hybrid.pyru
│   ├── gen_lujit.py              # Generate test.lujit
│   ├── gen_acf.py                # Generate app.acf
│   ├── gen_ctxt.py               # Generate rules.ctxt
│   ├── gen_stxt.py               # Generate actions.stxt
│   ├── gen_cmdx.py               # Generate tasks.cmdx (V3)
│   ├── gen_ptbl.py               # Generate points.ptbl (V3)
│   ├── gen_rmap.py               # Generate map.rmap (V3)
│   ├── gen_qset.py               # Generate quarantine.qset (V3)
│   ├── gen_tcfg.py               # Generate tasks.tcfg (V3)
│   ├── gen_mmsg.py               # Generate mod_actions.mmsg (V3)
│   ├── gen_vset.py               # Generate theme.vset (V3)
│   ├── gen_gcfg.py               # Generate games.gcfg (V3)
│   ├── gen_skey.py               # Generate secrets.skey (V3)
│   ├── gen_pfx.py                # Generate plugin.pfx (V3)
│   └── gen_ulog.py               # Generate events.ulog (V3)
├── examples/
│   ├── config.luna
│   ├── mystery.unkn
│   ├── hybrid.pyru
│   ├── test.lujit
│   ├── app.acf
│   ├── rules.ctxt
│   ├── actions.stxt
│   ├── tasks.cmdx                 # V3
│   ├── points.ptbl                # V3
│   ├── map.rmap                   # V3
│   ├── quarantine.qset            # V3
│   ├── tasks.tcfg                 # V3
│   ├── mod_actions.mmsg           # V3
│   ├── theme.vset                  # V3
│   ├── games.gcfg                  # V3
│   ├── secrets.skey                # V3
│   ├── plugin.pfx                  # V3
│   └── events.ulog                 # V3
├── LICENSE
└── README.md
```

## V3 Performance Benchmarks

| Operation | V2 | V3 | Improvement |
|-----------|----|----|-------------|
| `.unkn` folder (50 files) | ~5.2s | ~0.8s | ~6.5x faster |
| `.acf` verify_exe (cached) | ~120ms | ~0.1ms | ~1200x faster |
| `.luna` load (1 MB file) | ~85ms | ~42ms | ~2x faster |
| `.stxt` parse (10 MB file) | ~340ms | ~180ms | ~1.9x faster |
| `.ctxt` verify (cached) | ~95ms | ~0.1ms | ~950x faster |

## License

MIT License. See [LICENSE](LICENSE) for details.

## Author

GitHub: [@v86889839-collab](https://github.com/v86889839-collab)

## Changelog

### V3
- 11 new formats: `.cmdx`, `.ptbl`, `.rmap`, `.qset`, `.tcfg`, `.mmsg`, `.vset`, `.gcfg`, `.skey`, `.pfx`, `.ulog`
- Pre-compiled regex for language detection
- SHA-256 cache (in-memory, path → mtime + hash)
- ThreadPoolExecutor for parallel `.unkn` processing
- Streaming line-by-line reads for `.luna`, `.stxt`, `.pyru`, `.cmdx`, `.tcfg`
- Early exit on invalid headers/extensions
- Async wrappers: `process_unkn_folder_async`, `run_pyru_async`, `parse_stxt_async`
- Built-in `benchmark()` utility
- Total formats: 20

### V2
- 7 formats: `.luna`, `.unkn`, `.pyru`, `.lujit`, `.acf`, `.ctxt`, `.stxt`
- Basic parsers and generators
- Sequential processing
