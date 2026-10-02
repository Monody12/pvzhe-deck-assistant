"""植物大战僵尸杂交版 v3.12 内嵌卡组模组。

无需修改游戏文件；程序贴附在选卡界面，并支持选中卡片拖动排序。
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import re
import struct
import sys
import time
from typing import Iterable


PROCESS_NAME = "PlantsVsZombies.exe"
ASSISTANT_VERSION = "2.5.2"
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_SUSPEND_RESUME = 0x0800
TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

LAWN_APP_STATIC = 0x006A9EC0
LAWN_APP_BOARD = 0x768
LAWN_APP_CHOOSER = 0x774
BOARD_SEED_BANK = 0x144

CHOOSER_FIRST_SEED = 0xA4
CHOOSEN_SEED_SIZE = 0x3C
CHOOSER_START_BUTTON = 0x88
CHOOSER_APP = 0xD10
CHOOSER_BOARD = 0xD14
CHOOSER_SEEDS_IN_FLIGHT = 0xD20
CHOOSER_SEEDS_IN_BANK = 0xD24

GAME_BUTTON_DISABLED = 0x1A
GAME_BUTTON_LABEL_COLOR = 0x1C

SEED_X = 0x00
SEED_Y = 0x04
SEED_TIME_START = 0x08
SEED_TIME_END = 0x0C
SEED_START_X = 0x10
SEED_START_Y = 0x14
SEED_END_X = 0x18
SEED_END_Y = 0x1C
SEED_TYPE = 0x20
SEED_STATE = 0x24
SEED_BANK_INDEX = 0x28
SEED_IMITATER_TYPE = 0x34
SEED_CRAZY_DAVE = 0x38

STATE_FLYING_TO_BANK = 0
STATE_IN_BANK = 1
STATE_FLYING_TO_CHOOSER = 2
STATE_IN_CHOOSER = 3
STATE_HIDDEN = 4
IMITATER_SEED_ID = 48
SEED_NONE = 0xFFFFFFFF

SEED_BANK_COUNT = 0x24
SEED_BANK_PACKETS = 0x28
SEED_PACKET_SIZE = 0x50
PACKET_X = 0x08
PACKET_Y = 0x0C
PACKET_TYPE = 0x34
PACKET_IMITATER_TYPE = 0x38

MAX_SEED_ID = 1024
MAX_PRESET_CARDS = 32
MAX_MEMORY_READ = 65536
# 选中卡槽在窗口顶部，覆盖层默认放在此高度之下，避免挡住卡槽。
SEED_BANK_ROW_HEIGHT = 88
PRESET_SLOT_COUNT = 8
MAX_PRESET_NAME_LEN = 12
SLOT_BUTTON_LABEL_LEN = 5
WIDGET_X = 0x08
WIDGET_Y = 0x0C
WIDGET_WIDTH = 0x10
WIDGET_HEIGHT = 0x14

HWND_TOPMOST = -1
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
ERROR_ALREADY_EXISTS = 183


class DeckAssistantError(RuntimeError):
    """可以直接展示给用户的操作错误。"""


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")
user32 = ctypes.WinDLL("user32", use_last_error=True)
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = (
    wintypes.HANDLE,
    ctypes.POINTER(PROCESSENTRY32W),
)
kernel32.Process32FirstW.restype = wintypes.BOOL
kernel32.Process32NextW.argtypes = (
    wintypes.HANDLE,
    ctypes.POINTER(PROCESSENTRY32W),
)
kernel32.Process32NextW.restype = wintypes.BOOL
kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.ReadProcessMemory.argtypes = (
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
)
kernel32.ReadProcessMemory.restype = wintypes.BOOL
kernel32.WriteProcessMemory.argtypes = (
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.LPCVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
)
kernel32.WriteProcessMemory.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = (
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
)
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CreateMutexW.argtypes = (
    wintypes.LPVOID,
    wintypes.BOOL,
    wintypes.LPCWSTR,
)
kernel32.CreateMutexW.restype = wintypes.HANDLE
ntdll.NtSuspendProcess.argtypes = (wintypes.HANDLE,)
ntdll.NtSuspendProcess.restype = wintypes.LONG
ntdll.NtResumeProcess.argtypes = (wintypes.HANDLE,)
ntdll.NtResumeProcess.restype = wintypes.LONG
user32.EnumWindows.argtypes = (WNDENUMPROC, wintypes.LPARAM)
user32.EnumWindows.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = (
    wintypes.HWND,
    ctypes.POINTER(wintypes.DWORD),
)
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.IsWindowVisible.argtypes = (wintypes.HWND,)
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsWindow.argtypes = (wintypes.HWND,)
user32.IsWindow.restype = wintypes.BOOL
user32.IsIconic.argtypes = (wintypes.HWND,)
user32.IsIconic.restype = wintypes.BOOL
user32.GetParent.argtypes = (wintypes.HWND,)
user32.GetParent.restype = wintypes.HWND
user32.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(RECT))
user32.GetClientRect.restype = wintypes.BOOL
user32.ClientToScreen.argtypes = (wintypes.HWND, ctypes.POINTER(POINT))
user32.ClientToScreen.restype = wintypes.BOOL
user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.GetWindowTextW.restype = ctypes.c_int
user32.SetWindowPos.argtypes = (
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
)
user32.SetWindowPos.restype = wintypes.BOOL
user32.MessageBoxW.argtypes = (
    wintypes.HWND,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.UINT,
)
user32.MessageBoxW.restype = ctypes.c_int


def find_game_pid() -> int:
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        found = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while found:
            if entry.szExeFile.casefold() == PROCESS_NAME.casefold():
                return int(entry.th32ProcessID)
            found = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    raise DeckAssistantError("未检测到游戏，请先启动植物大战僵尸杂交版 v3.12。")


def find_main_window(pid: int) -> int:
    candidates: list[tuple[int, int]] = []

    @WNDENUMPROC
    def callback(hwnd: int, _lparam: int) -> bool:
        window_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        if window_pid.value != pid or not user32.IsWindowVisible(hwnd):
            return True
        class_name = ctypes.create_unicode_buffer(256)
        title = ctypes.create_unicode_buffer(512)
        user32.GetClassNameW(hwnd, class_name, 256)
        user32.GetWindowTextW(hwnd, title, 512)
        score = 0
        if class_name.value == "MainWindow":
            score += 3
        if any(
            token in title.value
            for token in ("植物大战僵尸", "杂交", "PlantsVsZombies")
        ):
            score += 2
        if title.value:
            score += 1
        candidates.append((score, int(hwnd)))
        return True

    user32.EnumWindows(callback, 0)
    if not candidates:
        raise DeckAssistantError("已检测到游戏进程，但尚未找到游戏窗口。")
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


class ProcessMemory:
    def __init__(self, pid: int) -> None:
        rights = (
            PROCESS_QUERY_INFORMATION
            | PROCESS_VM_OPERATION
            | PROCESS_VM_READ
            | PROCESS_VM_WRITE
            | PROCESS_SUSPEND_RESUME
        )
        self.handle = kernel32.OpenProcess(rights, False, pid)
        if not self.handle:
            error = ctypes.get_last_error()
            if error == 5:
                raise DeckAssistantError(
                    "无法访问游戏进程。请关闭助手后，以管理员身份重新运行。"
                )
            raise ctypes.WinError(error)
        self.pid = pid

    def close(self) -> None:
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self) -> "ProcessMemory":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def read(self, address: int, size: int) -> bytes:
        if size <= 0 or size > MAX_MEMORY_READ:
            raise DeckAssistantError("读取游戏内存长度不合法。")
        buffer = ctypes.create_string_buffer(size)
        amount = ctypes.c_size_t()
        if not kernel32.ReadProcessMemory(
            self.handle, address, buffer, size, ctypes.byref(amount)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if amount.value != size:
            raise DeckAssistantError(
                f"读取游戏内存不完整：0x{address:08X}。"
            )
        return buffer.raw

    def write(self, address: int, data: bytes) -> None:
        if not data or len(data) > MAX_MEMORY_READ:
            raise DeckAssistantError("写入游戏内存长度不合法。")
        buffer = ctypes.create_string_buffer(data)
        amount = ctypes.c_size_t()
        if not kernel32.WriteProcessMemory(
            self.handle, address, buffer, len(data), ctypes.byref(amount)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if amount.value != len(data):
            raise DeckAssistantError(
                f"写入游戏内存不完整：0x{address:08X}。"
            )

    def u32(self, address: int) -> int:
        return struct.unpack("<I", self.read(address, 4))[0]

    def write_u32(self, address: int, value: int) -> None:
        self.write(address, struct.pack("<I", value & 0xFFFFFFFF))

    def write_u8(self, address: int, value: int) -> None:
        self.write(address, struct.pack("<B", value & 0xFF))

    def image_path(self) -> Path:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(
            self.handle, 0, buffer, ctypes.byref(size)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return Path(buffer.value)

    def suspend(self) -> None:
        status = ntdll.NtSuspendProcess(self.handle)
        if status < 0:
            raise DeckAssistantError(f"暂停游戏进程失败：0x{status & 0xFFFFFFFF:08X}")

    def resume(self) -> None:
        status = ntdll.NtResumeProcess(self.handle)
        if status < 0:
            raise DeckAssistantError(f"恢复游戏进程失败：0x{status & 0xFFFFFFFF:08X}")


@dataclass(frozen=True)
class DeckCard:
    seed_type: int
    imitater_type: int = -1


@dataclass(frozen=True)
class SelectedSeed:
    bank_index: int
    card: DeckCard
    x: int
    y: int
    locked: bool


@dataclass
class DeckPreset:
    name: str
    cards: list[DeckCard] = field(default_factory=list)


class PresetStore:
    SCHEMA_VERSION = 1

    def __init__(self, path: Path | None = None) -> None:
        app_data = Path(os.environ.get("APPDATA", Path.home()))
        self.path = path or app_data / "PvZHybridDeckAssistant" / "decks.json"
        self.presets = [
            DeckPreset(f"卡组 {index + 1}") for index in range(PRESET_SLOT_COUNT)
        ]
        self.allow_overwrite_locked = False
        self.overlay_offset: tuple[int, int] | None = None
        self.load()

    @staticmethod
    def sanitize_name(name: str, index: int) -> str:
        cleaned = "".join(
            char
            for char in str(name)
            if char.isprintable() and char not in "<>\"'\\/"
        )
        cleaned = " ".join(cleaned.split())[:MAX_PRESET_NAME_LEN].strip()
        return cleaned or f"卡组 {index + 1}"

    @staticmethod
    def _sanitize_card(raw: object) -> DeckCard | None:
        if isinstance(raw, DeckCard):
            seed_type = int(raw.seed_type)
            imitater_type = int(raw.imitater_type)
        elif isinstance(raw, dict):
            try:
                seed_type = int(raw["seed_type"])
                imitater_type = int(raw.get("imitater_type", -1))
            except (TypeError, ValueError, KeyError):
                return None
        else:
            return None
        if not 0 <= seed_type < MAX_SEED_ID:
            return None
        if imitater_type != -1 and not 0 <= imitater_type < MAX_SEED_ID:
            return None
        return DeckCard(seed_type=seed_type, imitater_type=imitater_type)

    @classmethod
    def _sanitize_cards(cls, raw_cards: object) -> list[DeckCard]:
        if not isinstance(raw_cards, list):
            return []
        cards: list[DeckCard] = []
        seen: set[int] = set()
        for raw in raw_cards[: MAX_PRESET_CARDS * 4]:
            card = cls._sanitize_card(raw)
            if card is None or card.seed_type in seen:
                continue
            seen.add(card.seed_type)
            cards.append(card)
            if len(cards) >= MAX_PRESET_CARDS:
                break
        return cards

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            if self.path.stat().st_size > 200_000:
                raise ValueError("preset file too large")
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if int(payload.get("schema_version", 0)) not in (1, self.SCHEMA_VERSION):
                raise ValueError("unsupported schema")
            loaded = []
            for index, item in enumerate(
                payload.get("presets", [])[:PRESET_SLOT_COUNT]
            ):
                cards = self._sanitize_cards(item.get("cards", []))
                loaded.append(
                    DeckPreset(
                        name=self.sanitize_name(
                            str(item.get("name") or f"卡组 {index + 1}"),
                            index,
                        ),
                        cards=cards,
                    )
                )
            while len(loaded) < PRESET_SLOT_COUNT:
                loaded.append(DeckPreset(f"卡组 {len(loaded) + 1}"))
            self.presets = loaded
            self.allow_overwrite_locked = bool(
                payload.get("allow_overwrite_locked", False)
            )
            offset = payload.get("overlay_offset")
            if isinstance(offset, list) and len(offset) == 2:
                ox, oy = int(offset[0]), int(offset[1])
                if abs(ox) <= 4096 and abs(oy) <= 4096:
                    self.overlay_offset = (ox, oy)
                else:
                    self.overlay_offset = None
            else:
                self.overlay_offset = None
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            backup = self.path.with_suffix(".broken.json")
            try:
                self.path.replace(backup)
            except OSError:
                pass

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "game_version": "pvzHE-v3.12",
            "allow_overwrite_locked": bool(self.allow_overwrite_locked),
            "overlay_offset": (
                list(self.overlay_offset) if self.overlay_offset else None
            ),
            "presets": [
                {
                    "name": self.sanitize_name(preset.name, index),
                    "cards": [asdict(card) for card in self._sanitize_cards(preset.cards)],
                }
                for index, preset in enumerate(self.presets[:PRESET_SLOT_COUNT])
            ],
        }
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)


class PlantNameStore:
    def __init__(self, path: Path | None = None) -> None:
        app_data = Path(os.environ.get("APPDATA", Path.home()))
        self.path = (
            path
            or app_data
            / "PvZHybridDeckAssistant"
            / "plant_names.json"
        )
        self.names: dict[int, str] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            if self.path.stat().st_size > 200_000:
                raise ValueError("name cache too large")
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("invalid name cache")
            self.names = {}
            for seed_id, name in list(payload.items())[:2048]:
                text = str(name).strip()[:80]
                try:
                    key = int(seed_id)
                except (TypeError, ValueError):
                    continue
                if text and 0 <= key < MAX_SEED_ID:
                    self.names[key] = text
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self.names = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    str(seed_id): name
                    for seed_id, name in sorted(self.names.items())
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def get(self, seed_id: int) -> str:
        return self.names.get(seed_id, f"植物 {seed_id}")

    def update(self, values: dict[int, str]) -> None:
        changed = False
        for seed_id, name in values.items():
            name = name.strip()[:80]
            if name and 0 <= int(seed_id) < MAX_SEED_ID and self.names.get(seed_id) != name:
                self.names[seed_id] = name
                changed = True
        if changed:
            self.save()

    def replace(self, values: dict[int, str]) -> None:
        normalized = {
            int(seed_id): str(name).strip()
            for seed_id, name in values.items()
            if str(name).strip()
        }
        if normalized != self.names:
            self.names = normalized
            self.save()


class GameResourceNameResolver:
    BASE_SEED_KEYS = (
        "PEASHOOTER",
        "SUNFLOWER",
        "CHERRY_BOMB",
        "WALL_NUT",
        "POTATO_MINE",
        "SNOW_PEA",
        "CHOMPER",
        "REPEATER",
        "PUFF_SHROOM",
        "SUN_SHROOM",
        "FUME_SHROOM",
        "GRAVE_BUSTER",
        "HYPNO_SHROOM",
        "SCAREDY_SHROOM",
        "ICE_SHROOM",
        "DOOM_SHROOM",
        "LILY_PAD",
        "SQUASH",
        "THREEPEATER",
        "TANGLE_KELP",
        "JALAPENO",
        "SPIKEWEED",
        "TORCHWOOD",
        "TALL_NUT",
        "SEA_SHROOM",
        "PLANTERN",
        "CACTUS",
        "BLOVER",
        "SPLIT_PEA",
        "STARFRUIT",
        "PUMPKIN",
        "MAGNET_SHROOM",
        "CABBAGE_PULT",
        "FLOWER_POT",
        "KERNEL_PULT",
        "COFFEE_BEAN",
        "GARLIC",
        "UMBRELLA_LEAF",
        "MARIGOLD",
        "MELON_PULT",
        "GATLING_PEA",
        "TWIN_SUNFLOWER",
        "GLOOM_SHROOM",
        "CATTAIL",
        "WINTER_MELON",
        "GOLD_MAGNET",
        "SPIKEROCK",
        "COB_CANNON",
        "IMITATER",
    )
    EXTENDED_FIRST_ID = 75
    EXTENDED_SIGNATURE = (
        b"POTATOMINE_R\0\0WALLNUT_R\0\0CATTAIL_P\0\0"
    )

    @classmethod
    def load(cls, game_executable: Path) -> dict[int, str]:
        extended_keys = cls._read_extended_keys(game_executable)
        if not extended_keys:
            return {}
        best_names: dict[int, str] = {}
        best_extended_count = 0
        for pak_path in cls._main_pak_candidates(game_executable):
            translations = cls._read_translations(pak_path)
            if not translations:
                continue
            names = {
                seed_id: translations[key].strip()
                for seed_id, key in enumerate(cls.BASE_SEED_KEYS)
                if translations.get(key, "").strip()
            }
            extended_count = 0
            for seed_id, key in enumerate(
                extended_keys, cls.EXTENDED_FIRST_ID
            ):
                name = translations.get(key, "").strip()
                if name:
                    names[seed_id] = name
                    extended_count += 1
            if extended_count > best_extended_count:
                best_names = names
                best_extended_count = extended_count
        minimum_coverage = max(1, int(len(extended_keys) * 0.75))
        return (
            best_names if best_extended_count >= minimum_coverage else {}
        )

    @staticmethod
    def _application_directory() -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parent

    @classmethod
    def _main_pak_candidates(cls, game_executable: Path) -> list[Path]:
        candidates = (
            game_executable.parent / "main.pak",
            game_executable.parent.parent / "main.pak",
            cls._application_directory() / "main.pak",
            Path.cwd() / "main.pak",
        )
        result: list[Path] = []
        seen: set[Path] = set()
        for path in candidates:
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved not in seen and resolved.is_file():
                seen.add(resolved)
                result.append(resolved)
        return result

    @staticmethod
    def _xor(data: bytes) -> bytes:
        return bytes(value ^ 0xF7 for value in data)

    @classmethod
    def _read_translations(cls, pak_path: Path) -> dict[str, str]:
        records: list[tuple[str, int]] = []
        texts: list[str] = []
        try:
            with pak_path.open("rb") as pak:
                header = cls._read_xored(pak, 8)
                if header != struct.pack("<II", 0xBAC04AC0, 0):
                    return {}
                while True:
                    flag = cls._read_xored(pak, 1)[0]
                    if flag == 0x80:
                        break
                    if flag != 0:
                        return {}
                    name_length = cls._read_xored(pak, 1)[0]
                    name = cls._read_xored(
                        pak, name_length
                    ).decode("latin1")
                    size = struct.unpack("<I", cls._read_xored(pak, 4))[0]
                    cls._read_xored(pak, 8)
                    records.append((name, size))
                    if len(records) > 100_000:
                        return {}
                data_start = pak.tell()
                total_size = sum(size for _, size in records)
                if data_start + total_size > pak_path.stat().st_size:
                    return {}
                offset = 0
                for name, size in records:
                    normalized = name.lower()
                    if (
                        normalized.startswith("properties\\")
                        and normalized.endswith("strings.txt")
                    ):
                        pak.seek(data_start + offset)
                        raw = cls._read_xored(pak, size)
                        try:
                            texts.append(raw.decode("gb18030"))
                        except UnicodeDecodeError:
                            pass
                    offset += size
        except (OSError, ValueError, IndexError, struct.error):
            return {}
        translations: dict[str, str] = {}
        for text in texts:
            pending_key: str | None = None
            for line in text.splitlines():
                value = line.strip()
                if value.startswith("[") and value.endswith("]"):
                    pending_key = value[1:-1]
                elif pending_key and value:
                    translations.setdefault(pending_key, value)
                    pending_key = None
        return translations

    @classmethod
    def _read_xored(cls, stream: object, size: int) -> bytes:
        data = stream.read(size)
        if len(data) != size:
            raise ValueError("truncated pak")
        return cls._xor(data)

    @classmethod
    def _read_extended_keys(cls, game_executable: Path) -> list[str]:
        try:
            executable = game_executable.read_bytes()
        except OSError:
            return []
        position = executable.find(cls.EXTENDED_SIGNATURE)
        if position < 0:
            return []
        keys: list[str] = []
        while position < len(executable):
            end = executable.find(b"\0\0", position)
            if end < 0:
                break
            raw = executable[position:end]
            if (
                not raw
                or len(raw) > 80
                or not re.fullmatch(rb"[A-Za-z0-9_-]+", raw)
            ):
                break
            keys.append(raw.decode("ascii"))
            if len(keys) >= 1024:
                break
            position = end + 2
        return keys


class GameSession:
    def __init__(self) -> None:
        self.memory = ProcessMemory(find_game_pid())
        self.executable_path = self.memory.image_path()
        self.hwnd = find_main_window(self.memory.pid)
        self.lawn_app = self.memory.u32(LAWN_APP_STATIC)
        self.last_apply_note = ""
        if not self._reasonable_pointer(self.lawn_app):
            self.close()
            raise DeckAssistantError(
                "游戏核心地址校验失败；当前版本可能不是杂交版 v3.12。"
            )

    def close(self) -> None:
        self.memory.close()

    def __enter__(self) -> "GameSession":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _reasonable_pointer(value: int) -> bool:
        return 0x10000 <= value <= 0x7FFFFFFF

    def _board(self) -> int:
        board = self.memory.u32(self.lawn_app + LAWN_APP_BOARD)
        if not self._reasonable_pointer(board):
            raise DeckAssistantError("尚未进入关卡，无法访问游戏卡槽。")
        return board

    def _seed_bank(self) -> int:
        seed_bank = self.memory.u32(self._board() + BOARD_SEED_BANK)
        if not self._reasonable_pointer(seed_bank):
            raise DeckAssistantError("当前关卡没有可用的植物卡槽。")
        return seed_bank

    def _capacity(self) -> int:
        capacity = self.memory.u32(self._seed_bank() + SEED_BANK_COUNT)
        if not 1 <= capacity <= 32:
            raise DeckAssistantError(
                f"卡槽容量异常（{capacity}），当前关卡可能不支持自由选卡。"
            )
        return capacity

    def _chooser(self) -> int:
        chooser = self.memory.u32(self.lawn_app + LAWN_APP_CHOOSER)
        if not self._reasonable_pointer(chooser):
            raise DeckAssistantError("请先进入普通选卡界面再使用卡组。")
        board = self._board()
        try:
            valid = (
                self.memory.u32(chooser + CHOOSER_APP) == self.lawn_app
                and self.memory.u32(chooser + CHOOSER_BOARD) == board
            )
        except OSError as exc:
            raise DeckAssistantError("选卡界面已经关闭，请重新进入后再试。") from exc
        if not valid:
            raise DeckAssistantError(
                "选卡结构校验失败；当前模式或游戏版本暂不受支持。"
            )
        return chooser

    def chooser_ready(self) -> bool:
        try:
            chooser = self._chooser()
            return self._chooser_ui_active(chooser)
        except (OSError, DeckAssistantError):
            return False

    def _chooser_ui_active(self, chooser: int) -> bool:
        """开始按钮仍在选卡面板上时，才视为真正的选卡界面。"""
        button = self.memory.u32(chooser + CHOOSER_START_BUTTON)
        if not self._reasonable_pointer(button):
            return False
        width = self.memory.u32(button + WIDGET_WIDTH)
        height = self.memory.u32(button + WIDGET_HEIGHT)
        x = self.memory.u32(button + WIDGET_X)
        y = self.memory.u32(button + WIDGET_Y)
        return (
            80 <= width <= 400
            and 20 <= height <= 90
            and 0 <= x <= 1080
            and 80 <= y <= 700
        )

    @staticmethod
    def _seed_address(chooser: int, seed_id: int) -> int:
        return chooser + CHOOSER_FIRST_SEED + seed_id * CHOOSEN_SEED_SIZE

    def _valid_seed_ids(self, chooser: int) -> list[int]:
        result = []
        misses = 0
        for seed_id in range(MAX_SEED_ID):
            address = self._seed_address(chooser, seed_id)
            try:
                actual_type = self.memory.u32(address + SEED_TYPE)
                state = self.memory.u32(address + SEED_STATE)
            except OSError:
                break
            if actual_type == seed_id and state <= STATE_HIDDEN:
                result.append(seed_id)
                misses = 0
            else:
                misses += 1
                if result and misses >= 64:
                    break
        return result

    def _wait_for_stable_chooser(self, chooser: int) -> None:
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if self.memory.u32(chooser + CHOOSER_SEEDS_IN_FLIGHT) == 0:
                return
            time.sleep(0.05)
        raise DeckAssistantError("选卡动画尚未结束，请稍等片刻后重试。")

    def _is_locked_seed(self, address: int) -> bool:
        try:
            return self.memory.read(address + SEED_CRAZY_DAVE, 1)[0] != 0
        except (OSError, DeckAssistantError):
            return False

    def _selected_entries(self, chooser: int) -> list[SelectedSeed]:
        selected: list[SelectedSeed] = []
        for seed_id in self._valid_seed_ids(chooser):
            address = self._seed_address(chooser, seed_id)
            if self.memory.u32(address + SEED_STATE) != STATE_IN_BANK:
                continue
            selected.append(
                SelectedSeed(
                    bank_index=self.memory.u32(address + SEED_BANK_INDEX),
                    card=DeckCard(
                        seed_type=seed_id,
                        imitater_type=self._signed_u32(
                            self.memory.u32(address + SEED_IMITATER_TYPE)
                        ),
                    ),
                    x=self._signed_u32(self.memory.u32(address + SEED_X)),
                    y=self._signed_u32(self.memory.u32(address + SEED_Y)),
                    locked=self._is_locked_seed(address),
                )
            )
        selected.sort(key=lambda item: item.bank_index)
        return selected

    def _read_seed_bank_cards(self) -> tuple[list[DeckCard], int]:
        seed_bank = self._seed_bank()
        capacity = self._capacity()
        cards = []
        for index in range(capacity):
            packet = seed_bank + SEED_BANK_PACKETS + index * SEED_PACKET_SIZE
            seed_type = self.memory.u32(packet + PACKET_TYPE)
            if seed_type == SEED_NONE:
                continue
            cards.append(
                DeckCard(
                    seed_type=seed_type,
                    imitater_type=self._signed_u32(
                        self.memory.u32(packet + PACKET_IMITATER_TYPE)
                    ),
                )
            )
        return cards, capacity

    def read_current_deck(
        self, *, wait_stable: bool = False
    ) -> tuple[list[DeckCard], int, str]:
        """读取选卡界面；界面不存在或结构未就绪时回退读取战斗卡槽。"""
        chooser_ptr = self.memory.u32(self.lawn_app + LAWN_APP_CHOOSER)
        if self._reasonable_pointer(chooser_ptr):
            try:
                chooser = self._chooser()
                if wait_stable:
                    self._wait_for_stable_chooser(chooser)
                selected = self._selected_entries(chooser)
                return (
                    [item.card for item in selected],
                    self._capacity(),
                    "选卡界面",
                )
            except DeckAssistantError:
                pass
        cards, capacity = self._read_seed_bank_cards()
        return cards, capacity, "战斗卡槽"

    def selected_card_layout(
        self,
    ) -> tuple[int, list[tuple[int, DeckCard, int, int]]]:
        chooser = self._chooser()
        if self.memory.u32(chooser + CHOOSER_SEEDS_IN_FLIGHT) != 0:
            return chooser, []
        selected = self._selected_entries(chooser)
        return chooser, [
            (item.bank_index, item.card, item.x, item.y) for item in selected
        ]

    def _chooser_return_position(
        self, address: int, seed_id: int = 0
    ) -> tuple[int, int]:
        start_x = self._signed_u32(self.memory.u32(address + SEED_START_X))
        start_y = self._signed_u32(self.memory.u32(address + SEED_START_Y))
        current_x = self._signed_u32(self.memory.u32(address + SEED_X))
        current_y = self._signed_u32(self.memory.u32(address + SEED_Y))

        def usable(x: int, y: int) -> bool:
            return -80 <= x <= 1000 and -20 <= y <= 900

        if usable(start_x, start_y) and start_y >= 70:
            return start_x, start_y
        if usable(current_x, current_y) and current_y >= 70:
            return current_x, current_y
        if start_y >= 70:
            return start_x, start_y
        if current_y >= 70:
            return current_x, current_y
        # 锁定卡的起点常被写成卡槽坐标，丢回去会叠在顶栏卡槽上。
        column = seed_id % 10
        row = (seed_id // 10) % 12
        return 14 + column * 53, 123 + row * 70 + 7000

    def _compose_with_locked(
        self,
        cards: list[DeckCard],
        locked: list[SelectedSeed],
        capacity: int,
    ) -> tuple[list[DeckCard], list[tuple[int, DeckCard]]]:
        locked_ids = {item.card.seed_type for item in locked}
        used_indices: set[int] = set()
        normalized: list[SelectedSeed] = []
        for item in locked:
            index = item.bank_index
            if not 0 <= index < capacity or index in used_indices:
                continue
            used_indices.add(index)
            normalized.append(item)
        locked = normalized
        free_indices = [
            index for index in range(capacity) if index not in used_indices
        ]
        fill: list[DeckCard] = []
        for card in cards:
            if card.seed_type in locked_ids:
                continue
            if len(fill) >= len(free_indices):
                break
            fill.append(card)
        assignments = [(item.bank_index, item.card) for item in locked]
        assignments.extend(
            (index, card) for index, card in zip(free_indices, fill)
        )
        assignments.sort(key=lambda item: item[0])
        return [card for _, card in assignments], assignments

    def _compose_conflicts(
        self,
        cards: list[DeckCard],
        locked: list[SelectedSeed],
        capacity: int,
    ) -> bool:
        if not locked:
            return False
        composed, _ = self._compose_with_locked(cards, locked, capacity)
        return composed != cards[:capacity]

    def locked_apply_conflict(
        self, cards: Iterable[DeckCard]
    ) -> list[SelectedSeed]:
        cards = list(cards)
        chooser = self._chooser()
        locked = [
            item for item in self._selected_entries(chooser) if item.locked
        ]
        if not locked:
            return []
        valid_set = set(self._valid_seed_ids(chooser))
        locked_ids = {item.card.seed_type for item in locked}
        usable = [
            card
            for card in cards
            if card.seed_type in valid_set or card.seed_type in locked_ids
        ]
        if self._compose_conflicts(usable, locked, self._capacity()):
            return locked
        return []

    def _read_msvc_string(self, address: int) -> str:
        try:
            size = self.memory.u32(address + 0x14)
            capacity = self.memory.u32(address + 0x18)
            if size == 0 or size > 256 or capacity < size:
                return ""
            data_address = (
                address + 0x04
                if capacity < 16
                else self.memory.u32(address + 0x04)
            )
            raw = self.memory.read(data_address, size)
            for encoding in ("gbk", "utf-8"):
                try:
                    return raw.decode(encoding).strip()
                except UnicodeDecodeError:
                    continue
        except (OSError, DeckAssistantError):
            pass
        return ""

    def current_tooltip_name(self) -> tuple[int, str] | None:
        try:
            chooser = self._chooser()
            seed_id = self.memory.u32(chooser + 0xD2C)
            if seed_id == 0xFFFFFFFF:
                return None
            tooltip = self.memory.u32(chooser + 0xD28)
            name = self._read_msvc_string(tooltip)
            return (seed_id, name) if name else None
        except (OSError, DeckAssistantError):
            return None

    @staticmethod
    def _signed_u32(value: int) -> int:
        return value if value < 0x80000000 else value - 0x100000000

    def _capture_deck_memory(
        self, chooser: int, valid_ids: Iterable[int]
    ) -> list[tuple[int, bytes]]:
        button = self.memory.u32(chooser + CHOOSER_START_BUTTON)
        if not self._reasonable_pointer(button):
            raise DeckAssistantError("开始按钮结构校验失败，已取消操作。")
        regions = [
            (self._seed_address(chooser, seed_id), CHOOSEN_SEED_SIZE)
            for seed_id in valid_ids
        ]
        regions.extend(
            (
                (chooser + CHOOSER_SEEDS_IN_FLIGHT, 8),
                (button + GAME_BUTTON_DISABLED, 1),
                (button + GAME_BUTTON_LABEL_COLOR, 16),
            )
        )
        return [
            (address, self.memory.read(address, size))
            for address, size in regions
        ]

    @contextmanager
    def _atomic_deck_write(
        self, chooser: int, valid_ids: Iterable[int]
    ) -> Iterable[None]:
        self.memory.suspend()
        snapshot: list[tuple[int, bytes]] = []
        try:
            snapshot = self._capture_deck_memory(chooser, valid_ids)
            try:
                yield
            except Exception as operation_error:
                try:
                    for address, data in reversed(snapshot):
                        self.memory.write(address, data)
                except Exception as rollback_error:
                    raise DeckAssistantError(
                        "卡组写入失败且自动回滚未完成；请立即重新进入选卡界面。"
                    ) from rollback_error
                raise operation_error
        finally:
            self.memory.resume()

    @staticmethod
    def _validate_imitater_cards(
        cards: Iterable[DeckCard], valid_ids: set[int]
    ) -> None:
        for card in cards:
            if card.seed_type == IMITATER_SEED_ID:
                if (
                    card.imitater_type not in valid_ids
                    or card.imitater_type == IMITATER_SEED_ID
                ):
                    raise DeckAssistantError(
                        "模仿者目标无效，无法安全应用卡组。"
                    )
            elif card.imitater_type != -1:
                raise DeckAssistantError(
                    f"普通植物 #{card.seed_type} 携带了非法模仿目标。"
                )

    def apply_deck(
        self,
        cards: Iterable[DeckCard],
        *,
        overwrite_locked: bool = False,
    ) -> tuple[int, int]:
        cards = list(cards)
        chooser = self._chooser()
        capacity = self._capacity()
        if len({card.seed_type for card in cards}) != len(cards):
            raise DeckAssistantError("预设中含有重复植物，无法安全应用。")

        self._wait_for_stable_chooser(chooser)
        locked = [
            item for item in self._selected_entries(chooser) if item.locked
        ]
        if len(locked) > capacity:
            raise DeckAssistantError("本关锁定卡片数量超过卡槽，无法安全应用。")

        valid_ids = self._valid_seed_ids(chooser)
        valid_set = set(valid_ids)
        locked_ids = {item.card.seed_type for item in locked}
        unavailable = [
            card.seed_type
            for card in cards
            if card.seed_type not in valid_set and card.seed_type not in locked_ids
        ]
        usable = [
            card
            for card in cards
            if card.seed_type in valid_set or card.seed_type in locked_ids
        ]
        if cards and not usable and not locked:
            formatted = "、".join(f"#{item}" for item in unavailable[:8])
            raise DeckAssistantError(f"当前版本或关卡中找不到植物：{formatted}。")
        conflict = self._compose_conflicts(usable, locked, capacity)
        replace_locked = bool(overwrite_locked and conflict)
        effective_locked = [] if replace_locked else locked
        final_cards, assignments = self._compose_with_locked(
            usable, effective_locked, capacity
        )
        kept_ids = {item.card.seed_type for item in effective_locked}
        requested_free = [
            card for card in usable if card.seed_type not in kept_ids
        ]
        dropped_slots = max(
            0, len(requested_free) - (capacity - len(effective_locked))
        )
        notes = []
        if replace_locked:
            notes.append(f"已覆盖{len(locked)}张锁定卡")
        elif locked:
            notes.append(f"锁定{len(locked)}张已留")
        if unavailable:
            notes.append(f"跳过{len(unavailable)}张本关没有")
        if dropped_slots:
            notes.append(f"{dropped_slots}张槽位不够")
        self.last_apply_note = ("，" + "，".join(notes)) if notes else ""
        if len(final_cards) > capacity:
            raise DeckAssistantError(
                f"预设有 {len(cards)} 张卡，但本关只有 {capacity} 个卡槽。"
            )
        missing = [
            card.seed_type
            for card in final_cards
            if card.seed_type not in valid_set
        ]
        if missing:
            formatted = "、".join(f"#{item}" for item in missing)
            raise DeckAssistantError(f"当前版本或关卡中找不到植物：{formatted}。")
        self._validate_imitater_cards(final_cards, valid_set)
        cards = final_cards

        seed_bank = self._seed_bank()
        age = self.memory.u32(chooser + 0xD1C)
        moving = [
            (index, card)
            for index, card in assignments
            if card.seed_type not in kept_ids
        ]
        with self._atomic_deck_write(chooser, valid_ids):
            for seed_id in valid_ids:
                address = self._seed_address(chooser, seed_id)
                state = self.memory.u32(address + SEED_STATE)
                if state != STATE_IN_BANK:
                    continue
                locked_here = self._is_locked_seed(address)
                if locked_here and not replace_locked:
                    continue
                if locked_here and replace_locked:
                    self.memory.write_u8(address + SEED_CRAZY_DAVE, 0)
                origin_x, origin_y = self._chooser_return_position(
                    address, seed_id
                )
                default_state = (
                    STATE_HIDDEN if seed_id == IMITATER_SEED_ID else STATE_IN_CHOOSER
                )
                self._write_seed_position(
                    address, origin_x, origin_y, default_state, 0
                )
                self.memory.write_u32(address + SEED_IMITATER_TYPE, SEED_NONE)

            self.memory.write_u32(chooser + CHOOSER_SEEDS_IN_FLIGHT, 0)
            self.memory.write_u32(
                chooser + CHOOSER_SEEDS_IN_BANK, len(effective_locked)
            )

            flying = 0
            for index, card in moving:
                address = self._seed_address(chooser, card.seed_type)
                origin_x = self._signed_u32(self.memory.u32(address + SEED_X))
                origin_y = self._signed_u32(self.memory.u32(address + SEED_Y))
                packet = seed_bank + SEED_BANK_PACKETS + index * SEED_PACKET_SIZE
                end_x = self.memory.u32(packet + PACKET_X)
                end_y = self.memory.u32(packet + PACKET_Y)
                end_sx = self._signed_u32(end_x)
                end_sy = self._signed_u32(end_y)
                far = (
                    origin_y > 620
                    or origin_y < 60
                    or abs(origin_x - end_sx) + abs(origin_y - end_sy) > 720
                )
                self.memory.write_u32(
                    address + SEED_IMITATER_TYPE, card.imitater_type
                )
                self.memory.write_u32(address + SEED_BANK_INDEX, index)
                if far:
                    self._write_seed_position(
                        address, end_x, end_y, STATE_IN_BANK, index
                    )
                    continue
                self.memory.write_u32(address + SEED_TIME_START, age)
                self.memory.write_u32(address + SEED_TIME_END, age + 2)
                self.memory.write_u32(address + SEED_START_X, origin_x)
                self.memory.write_u32(address + SEED_START_Y, origin_y)
                self.memory.write_u32(address + SEED_END_X, end_x)
                self.memory.write_u32(address + SEED_END_Y, end_y)
                self.memory.write_u32(address + SEED_STATE, STATE_FLYING_TO_BANK)
                flying += 1

            self.memory.write_u32(chooser + CHOOSER_SEEDS_IN_FLIGHT, flying)
            # 游戏在 ClickedSeedInChooser 中增加已选数量，而不是在落位动画中增加。
            # 助手绕过了点击入口，因此必须同步该计数，否则后续手动增删会产生负索引。
            self.memory.write_u32(chooser + CHOOSER_SEEDS_IN_BANK, len(cards))
            self._set_start_button_enabled(
                chooser, enabled=len(cards) == capacity
            )

        if not cards:
            self._assert_applied_invariants(chooser, cards, capacity)
            return 0, capacity

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            selected, _, source = self.read_current_deck()
            if source == "选卡界面" and selected == cards:
                self._assert_applied_invariants(chooser, cards, capacity)
                return len(cards), capacity
            time.sleep(0.05)

        # 远距离飞行动画可能未在超时前结束，改为直接落位以免卡住计数。
        for index, card in moving:
            address = self._seed_address(chooser, card.seed_type)
            if self.memory.u32(address + SEED_STATE) != STATE_FLYING_TO_BANK:
                continue
            packet = seed_bank + SEED_BANK_PACKETS + index * SEED_PACKET_SIZE
            self._write_seed_position(
                address,
                self.memory.u32(packet + PACKET_X),
                self.memory.u32(packet + PACKET_Y),
                STATE_IN_BANK,
                index,
            )
        self.memory.write_u32(chooser + CHOOSER_SEEDS_IN_FLIGHT, 0)
        self.memory.write_u32(chooser + CHOOSER_SEEDS_IN_BANK, len(cards))

        selected, _, source = self.read_current_deck()
        if source == "选卡界面" and selected == cards:
            self._assert_applied_invariants(chooser, cards, capacity)
            return len(cards), capacity
        applied_ids = {card.seed_type for card in selected}
        failed = [card.seed_type for card in cards if card.seed_type not in applied_ids]
        detail = "、".join(f"#{seed_id}" for seed_id in failed)
        if failed:
            raise DeckAssistantError(
                f"以下植物未能选入，可能尚未解锁或本关禁用：{detail}。"
            )
        raise DeckAssistantError("游戏没有确认此次卡组变更，请重新进入选卡界面。")

    def clear_bank(self, *, overwrite_locked: bool = False) -> tuple[int, int]:
        """清空选卡栏。默认保留锁定卡。

        勾选覆盖后会清掉戴夫锁定卡。在 8-6 等关卡实测：清掉后仍可开局，
        重开本关会恢复锁定，进程不会崩溃。因此允许按用户确认强制清空。
        """
        remaining, capacity = self.apply_deck(
            [], overwrite_locked=overwrite_locked
        )
        locked_left = 0
        try:
            locked_left = sum(
                1
                for item in self._selected_entries(self._chooser())
                if item.locked
            )
        except DeckAssistantError:
            pass
        if overwrite_locked and locked_left:
            self.last_apply_note = f"，锁定{locked_left}张无法清除已保留"
        elif overwrite_locked:
            self.last_apply_note = "，含锁定卡已清空"
        elif locked_left:
            self.last_apply_note = f"，锁定{locked_left}张已留"
        else:
            self.last_apply_note = ""
        return remaining, capacity

    def reorder_deck(
        self, source_index: int, target_index: int
    ) -> list[DeckCard]:
        chooser = self._chooser()
        self._wait_for_stable_chooser(chooser)
        entries = self._selected_entries(chooser)
        cards = [item.card for item in entries]
        if not cards:
            raise DeckAssistantError("当前选卡栏为空，无法排序。")
        if not 0 <= source_index < len(cards):
            raise DeckAssistantError("拖动起始卡槽已失效，请重试。")
        capacity = self._capacity()
        if len(cards) > capacity:
            raise DeckAssistantError(
                "当前卡组超出卡槽容量，已取消排序；请重新进入选卡界面。"
            )
        if entries[source_index].locked:
            raise DeckAssistantError("本关锁定的卡片不能移动。")
        unlocked_positions = [
            index for index, item in enumerate(entries) if not item.locked
        ]
        if target_index not in unlocked_positions:
            raise DeckAssistantError("不能把卡片拖到锁定卡槽。")
        target_index = max(0, min(target_index, len(cards) - 1))
        if source_index == target_index:
            return cards

        unlocked_cards = [entries[index].card for index in unlocked_positions]
        source_unlocked = unlocked_positions.index(source_index)
        target_unlocked = unlocked_positions.index(target_index)
        moved = unlocked_cards.pop(source_unlocked)
        unlocked_cards.insert(target_unlocked, moved)
        locked_map = {
            item.bank_index: item.card for item in entries if item.locked
        }
        free_indices = [
            index for index in range(capacity) if index not in locked_map
        ]
        assignments = list(locked_map.items())
        assignments.extend(zip(free_indices, unlocked_cards))
        assignments.sort(key=lambda item: item[0])
        cards = [card for _, card in assignments]
        seed_bank = self._seed_bank()
        valid_ids = self._valid_seed_ids(chooser)
        with self._atomic_deck_write(chooser, valid_ids):
            for index, card in assignments:
                address = self._seed_address(chooser, card.seed_type)
                packet = seed_bank + SEED_BANK_PACKETS + index * SEED_PACKET_SIZE
                x = self.memory.u32(packet + PACKET_X)
                y = self.memory.u32(packet + PACKET_Y)
                self.memory.write_u32(address + SEED_X, x)
                self.memory.write_u32(address + SEED_Y, y)
                self.memory.write_u32(address + SEED_END_X, x)
                self.memory.write_u32(address + SEED_END_Y, y)
                self.memory.write_u32(address + SEED_STATE, STATE_IN_BANK)
                self.memory.write_u32(address + SEED_BANK_INDEX, index)
            self.memory.write_u32(chooser + CHOOSER_SEEDS_IN_FLIGHT, 0)
            self.memory.write_u32(chooser + CHOOSER_SEEDS_IN_BANK, len(cards))
            self._set_start_button_enabled(
                chooser, enabled=len(cards) == capacity
            )

        self._assert_applied_invariants(chooser, cards, capacity)
        return cards

    def _assert_applied_invariants(
        self, chooser: int, cards: list[DeckCard], capacity: int
    ) -> None:
        if self.memory.u32(chooser + CHOOSER_SEEDS_IN_FLIGHT) != 0:
            raise DeckAssistantError("卡组动画计数未归零，请重新进入选卡界面。")
        if self.memory.u32(chooser + CHOOSER_SEEDS_IN_BANK) != len(cards):
            raise DeckAssistantError("游戏已选卡片数量未同步，请重新进入选卡界面。")

        seed_bank = self._seed_bank()
        for index, card in enumerate(cards):
            address = self._seed_address(chooser, card.seed_type)
            packet = seed_bank + SEED_BANK_PACKETS + index * SEED_PACKET_SIZE
            if self.memory.u32(address + SEED_BANK_INDEX) != index:
                raise DeckAssistantError("卡组索引校验失败，请重新进入选卡界面。")
            if (
                self.memory.u32(address + SEED_X)
                != self.memory.u32(packet + PACKET_X)
                or self.memory.u32(address + SEED_Y)
                != self.memory.u32(packet + PACKET_Y)
            ):
                raise DeckAssistantError("卡片位置校验失败，请重新进入选卡界面。")

        button = self.memory.u32(chooser + CHOOSER_START_BUTTON)
        expected_disabled = 0 if len(cards) == capacity else 1
        if self.memory.read(button + GAME_BUTTON_DISABLED, 1)[0] != expected_disabled:
            raise DeckAssistantError("开始按钮状态未同步，请重新应用卡组。")

    def _set_start_button_enabled(self, chooser: int, enabled: bool) -> None:
        button = self.memory.u32(chooser + CHOOSER_START_BUTTON)
        if not self._reasonable_pointer(button):
            raise DeckAssistantError("开始按钮结构校验失败，已取消应用。")
        self.memory.write_u8(button + GAME_BUTTON_DISABLED, 0 if enabled else 1)
        color = 255 if enabled else 64
        for component in range(3):
            self.memory.write_u32(
                button + GAME_BUTTON_LABEL_COLOR + component * 4, color
            )
        self.memory.write_u32(button + GAME_BUTTON_LABEL_COLOR + 12, 255)

    def _write_seed_position(
        self, address: int, x: int, y: int, state: int, bank_index: int
    ) -> None:
        self.memory.write_u32(address + SEED_X, x)
        self.memory.write_u32(address + SEED_Y, y)
        self.memory.write_u32(address + SEED_TIME_START, 0)
        self.memory.write_u32(address + SEED_TIME_END, 0)
        self.memory.write_u32(address + SEED_START_X, x)
        self.memory.write_u32(address + SEED_START_Y, y)
        self.memory.write_u32(address + SEED_END_X, x)
        self.memory.write_u32(address + SEED_END_Y, y)
        self.memory.write_u32(address + SEED_STATE, state)
        self.memory.write_u32(address + SEED_BANK_INDEX, bank_index)


def format_cards(cards: list[DeckCard]) -> str:
    if not cards:
        return "空卡组"
    labels = []
    for card in cards:
        label = f"#{card.seed_type}"
        if card.imitater_type >= 0:
            label += f"(模仿 #{card.imitater_type})"
        labels.append(label)
    return "  ·  ".join(labels) + f"  （{len(cards)} 张）"


class GameConnector:
    def __init__(self) -> None:
        self.session: GameSession | None = None

    def close(self) -> None:
        if self.session:
            self.session.close()
            self.session = None

    def ensure_session(self) -> GameSession | None:
        if self.session:
            try:
                if (
                    self.session.memory.u32(LAWN_APP_STATIC)
                    == self.session.lawn_app
                    and user32.IsWindow(self.session.hwnd)
                ):
                    return self.session
            except Exception:
                self.close()
        try:
            self.session = GameSession()
        except Exception:
            self.session = None
        return self.session


class DeckOrderStrip:
    def __init__(
        self,
        parent: object,
        connector: GameConnector,
        store: PresetStore,
        name_store: PlantNameStore,
        selected_slot: object,
        status_callback: object,
        presets_changed_callback: object,
    ) -> None:
        import tkinter as tk

        self.tk = tk
        self.connector = connector
        self.store = store
        self.name_store = name_store
        self.selected_slot = selected_slot
        self.status_callback = status_callback
        self.presets_changed_callback = presets_changed_callback
        self.window = tk.Toplevel(parent)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg="#3b1c0e")
        self.canvas = tk.Canvas(
            self.window,
            height=58,
            bg="#4a2410",
            highlightbackground="#d79b45",
            highlightthickness=1,
        )
        self.canvas.pack(fill="both", expand=True, padx=2, pady=(2, 0))
        footer = tk.Frame(self.window, bg="#3b1c0e")
        footer.pack(fill="x", padx=3, pady=2)
        self.hint = tk.Label(
            footer,
                        text="拖动卡片名称块调整顺序",
            bg="#3b1c0e",
            fg="#f6d89b",
            font=("Microsoft YaHei UI", 8),
        )
        self.hint.pack(side="left")
        tk.Button(
            footer,
            text="完成",
            width=5,
            bg="#79b64c",
            command=self.close,
        ).pack(side="right")
        self.cards: list[DeckCard] = []
        self.locked_ids: set[int] = set()
        self.tile_width = 45
        self.tile_height = 52
        self.columns = 1
        self.rows = 1
        self.margin = 5
        self.drag_index: int | None = None
        self.drag_item_ids: tuple[int, ...] = ()
        self.drag_last_x = 0
        self.drag_last_y = 0
        self.canvas.bind("<ButtonPress-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)
        self.canvas.bind("<Motion>", self._show_hover_name)
        self.canvas.bind("<Leave>", self._reset_hint)
        self.refresh()

    def refresh(self) -> None:
        session = self.connector.ensure_session()
        if not session:
            self.close()
            return
        try:
            self.cards, _, source = session.read_current_deck()
            if source != "选卡界面" or not self.cards:
                raise DeckAssistantError("请先在选卡界面选择至少一张卡片。")
            try:
                chooser = session._chooser()
                self.locked_ids = {
                    item.card.seed_type
                    for item in session._selected_entries(chooser)
                    if item.locked
                }
            except DeckAssistantError:
                self.locked_ids = set()
            self._position(session)
            self._draw()
        except Exception as exc:
            self.status_callback(f"无法打开排序条：{exc}")
            self.close()

    def _position(self, session: GameSession) -> None:
        client = RECT()
        origin = POINT(0, 0)
        user32.GetClientRect(session.hwnd, ctypes.byref(client))
        user32.ClientToScreen(session.hwnd, ctypes.byref(origin))
        game_width = client.right - client.left
        game_height = client.bottom - client.top
        width = min(520, max(360, int(game_width * 0.48)))
        self.columns = max(1, min(len(self.cards), (width - 10) // 52))
        self.rows = (len(self.cards) + self.columns - 1) // self.columns
        canvas_height = self.rows * self.tile_height + 8
        window_height = canvas_height + 30
        self.canvas.configure(height=canvas_height)
        x = origin.x + game_width - width - 8
        y = origin.y + SEED_BANK_ROW_HEIGHT + IntegratedDeckOverlay.PANEL_HEIGHT + 6
        if y + window_height > origin.y + game_height - 10:
            y = origin.y + game_height - window_height - 10
        y = max(y, origin.y + SEED_BANK_ROW_HEIGHT)
        self.window.geometry(f"{width}x{window_height}+{x}+{y}")
        self.window.update_idletasks()
        content_hwnd = int(self.window.winfo_id())
        wrapper_hwnd = user32.GetParent(content_hwnd)
        hwnd = int(wrapper_hwnd or content_hwnd)
        user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            x,
            y,
            width,
            window_height,
            SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )

    def _draw(self) -> None:
        self.canvas.delete("all")
        width = max(1, self.canvas.winfo_width())
        self.tile_width = max(
            42, (width - self.margin * 2) // self.columns
        )
        for index, card in enumerate(self.cards):
            row, column = divmod(index, self.columns)
            left = self.margin + column * self.tile_width
            top = 4 + row * self.tile_height
            right = left + self.tile_width - 3
            bottom = top + self.tile_height - 4
            if card.seed_type in self.locked_ids:
                fill = "#8a6a4a"
            else:
                fill = "#d9a441" if index % 2 == 0 else "#b97931"
            self.canvas.create_rectangle(
                left,
                top,
                right,
                bottom,
                fill=fill,
                outline="#ffe4a3",
                tags=(f"card-{index}",),
            )
            self.canvas.create_text(
                (left + right) // 2,
                top + 12,
                text=str(index + 1),
                fill="#3a200d",
                font=("Microsoft YaHei UI", 8, "bold"),
                tags=(f"card-{index}",),
            )
            name = self.name_store.get(card.seed_type)
            if len(name) <= 4:
                display_name = name
            elif len(name) <= 8:
                display_name = name[:4] + "\n" + name[4:]
            else:
                display_name = name[:4] + "\n" + name[4:7] + "…"
            self.canvas.create_text(
                (left + right) // 2,
                top + 31,
                text=display_name,
                fill="white",
                font=("Microsoft YaHei UI", 7, "bold"),
                tags=(f"card-{index}",),
            )

    def _index_at(self, x: int, y: int) -> int | None:
        if not self.cards:
            return None
        local_x = x - self.margin
        local_y = y - 4
        if local_x < 0 or local_y < 0:
            return None
        column, x_offset = divmod(local_x, self.tile_width)
        row, y_offset = divmod(local_y, self.tile_height)
        if (
            column >= self.columns
            or row >= self.rows
            or x_offset >= self.tile_width - 3
            or y_offset >= self.tile_height - 4
        ):
            return None
        raw = row * self.columns + column
        return int(raw) if raw < len(self.cards) else None

    def _drag_start(self, event: object) -> None:
        self.drag_index = self._index_at(event.x, event.y)
        if self.drag_index is None:
            self.drag_item_ids = ()
            return
        card = self.cards[self.drag_index]
        if card.seed_type in self.locked_ids:
            self.drag_index = None
            self.drag_item_ids = ()
            self.hint.configure(text="本关锁定的卡片不能移动")
            return
        self.drag_last_x = event.x
        self.drag_last_y = event.y
        tag = f"card-{self.drag_index}"
        self.drag_item_ids = tuple(self.canvas.find_withtag(tag))
        for item in self.drag_item_ids:
            self.canvas.tag_raise(item)

    def _drag_move(self, event: object) -> None:
        if self.drag_index is None:
            return
        delta_x = event.x - self.drag_last_x
        delta_y = event.y - self.drag_last_y
        self.drag_last_x = event.x
        self.drag_last_y = event.y
        for item in self.drag_item_ids:
            self.canvas.move(item, delta_x, delta_y)

    def _drag_end(self, event: object) -> None:
        if self.drag_index is None:
            return
        source = self.drag_index
        target = self._index_at(event.x, event.y)
        self.drag_index = None
        self.drag_item_ids = ()
        if target is None or source == target:
            self._draw()
            return
        session = self.connector.ensure_session()
        if not session:
            self.close()
            return
        try:
            latest_cards, _, source_name = session.read_current_deck()
            if source_name != "选卡界面" or latest_cards != self.cards:
                raise DeckAssistantError(
                    "拖动期间卡组已变化，请按最新卡组重新拖动。"
                )
            self.cards = session.reorder_deck(source, target)
            slot = int(self.selected_slot.get())
            preset = self.store.presets[slot]
            if (
                len(preset.cards) == len(self.cards)
                and {
                    (card.seed_type, card.imitater_type)
                    for card in preset.cards
                }
                == {
                    (card.seed_type, card.imitater_type)
                    for card in self.cards
                }
            ):
                preset.cards = self.cards
                self.store.save()
                self.presets_changed_callback()
                suffix = "，已同步存储栏"
            else:
                suffix = ""
            self.status_callback(
                f"第 {source + 1} 张已移动到第 {target + 1} 张{suffix}"
            )
            self._draw()
        except Exception as exc:
            self.status_callback(f"排序失败：{exc}")
            self.refresh()

    def _show_hover_name(self, event: object) -> None:
        if not self.cards or self.drag_index is not None:
            return
        index = self._index_at(event.x, event.y)
        if index is None:
            self._reset_hint(event)
            return
        card = self.cards[index]
        lock = "，锁定" if card.seed_type in self.locked_ids else ""
        self.hint.configure(
            text=(
                f"{index + 1}. {self.name_store.get(card.seed_type)}"
                f"（#{card.seed_type}{lock}）"
            )
        )

    def _reset_hint(self, _event: object) -> None:
        self.hint.configure(text="拖动卡片名称块调整顺序")

    def close(self) -> None:
        if self.window.winfo_exists():
            self.window.destroy()


class IntegratedDeckOverlay:
    PANEL_HEIGHT = 220
    SLOT_COLUMNS = 4

    def __init__(self) -> None:
        import tkinter as tk

        self.tk = tk
        self.store = PresetStore()
        self.name_store = PlantNameStore()
        self.connector = GameConnector()
        self._resource_names_pid = 0
        initial_session = self.connector.ensure_session()
        if initial_session:
            self._load_resource_names(initial_session)
        self.root = tk.Tk()
        self.root.title(f"杂交版内嵌卡组模组 {ASSISTANT_VERSION}")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#3b1c0e")
        self.selected_slot = tk.IntVar(value=0)
        self.status = tk.StringVar(value="保存 / 应用 / 清空；双击卡组位改名")
        self.name_var = tk.StringVar(value=self.store.presets[0].name)
        self.allow_overwrite = tk.BooleanVar(
            value=self.store.allow_overwrite_locked
        )
        self.slot_buttons: list[object] = []
        self.order_strip: DeckOrderStrip | None = None
        self._dragging = False
        self._drag_pointer = (0, 0)
        self._drag_geom = (0, 0)
        self._last_place: tuple[int, int, int, int] | None = None
        self._overlay_visible = False
        self._prefs_ready = False
        self._build()
        self._prefs_ready = True
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._refresh_slot_buttons()
        self.root.withdraw()
        self._tick()

    def _load_resource_names(self, session: GameSession) -> None:
        if self._resource_names_pid == session.memory.pid:
            return
        self._resource_names_pid = session.memory.pid
        try:
            names = GameResourceNameResolver.load(session.executable_path)
        except (OSError, ValueError, struct.error):
            names = {}
        self.name_store.replace(names)

    def _build(self) -> None:
        tk = self.tk
        bar = tk.Frame(
            self.root,
            bg="#4a2410",
            highlightbackground="#d79b45",
            highlightthickness=1,
            padx=5,
            pady=4,
        )
        bar.pack(fill="both", expand=True)
        bar.bind("<ButtonPress-1>", self._drag_start)
        bar.bind("<B1-Motion>", self._drag_move)
        bar.bind("<ButtonRelease-1>", self._drag_end)

        grip = tk.Label(
            bar,
            text="⋮",
            bg="#4a2410",
            fg="#f6d89b",
            font=("Microsoft YaHei UI", 9),
            cursor="fleur",
        )
        grip.grid(row=0, column=0, sticky="nsw", padx=(0, 2))
        grip.bind("<ButtonPress-1>", self._drag_start)
        grip.bind("<B1-Motion>", self._drag_move)
        grip.bind("<ButtonRelease-1>", self._drag_end)

        name_entry = tk.Entry(
            bar,
            textvariable=self.name_var,
            font=("Microsoft YaHei UI", 8),
            width=14,
        )
        name_entry.grid(
            row=0, column=1, columnspan=3, sticky="ew", padx=1, pady=(0, 2)
        )
        name_entry.bind("<Return>", self._commit_name)
        name_entry.bind("<FocusOut>", self._commit_name)
        self.name_entry = name_entry

        tk.Button(
            bar,
            text="×",
            width=2,
            bg="#7d3528",
            fg="white",
            activebackground="#a54a39",
            pady=0,
            font=("Microsoft YaHei UI", 8),
            command=self.close,
        ).grid(row=0, column=4, padx=(3, 0), sticky="ew")

        for index in range(PRESET_SLOT_COUNT):
            row, column = divmod(index, self.SLOT_COLUMNS)
            button = tk.Button(
                bar,
                text=self._slot_button_text(index),
                width=5,
                bd=1,
                pady=0,
                font=("Microsoft YaHei UI", 8),
                command=lambda i=index: self._select_slot(i),
            )
            button.grid(
                row=1 + row,
                column=column,
                padx=1,
                pady=(2, 0),
                sticky="ew",
            )
            button.bind(
                "<Double-Button-1>",
                lambda _event, i=index: self._focus_rename(i),
            )
            self.slot_buttons.append(button)

        tk.Button(
            bar,
            text="保存",
            bg="#e2ad56",
            activebackground="#f3c879",
            pady=0,
            font=("Microsoft YaHei UI", 8),
            command=self.save_current,
        ).grid(row=3, column=0, padx=1, pady=(4, 0), sticky="ew")
        tk.Button(
            bar,
            text="应用",
            bg="#79b64c",
            activebackground="#98d16d",
            pady=0,
            font=("Microsoft YaHei UI", 8),
            command=self.apply_current,
        ).grid(row=3, column=1, padx=1, pady=(4, 0), sticky="ew")
        tk.Button(
            bar,
            text="排序",
            bg="#6ca5d8",
            activebackground="#91bfe7",
            pady=0,
            font=("Microsoft YaHei UI", 8),
            command=self.open_sorter,
        ).grid(row=3, column=2, padx=1, pady=(4, 0), sticky="ew")
        tk.Button(
            bar,
            text="清空",
            bg="#c9844a",
            activebackground="#d9a066",
            pady=0,
            font=("Microsoft YaHei UI", 8),
            command=self.clear_current,
        ).grid(row=3, column=3, padx=1, pady=(4, 0), sticky="ew")

        self.status_label = tk.Label(
            bar,
            textvariable=self.status,
            bg="#4a2410",
            fg="#f6d89b",
            anchor="nw",
            justify="left",
            wraplength=240,
            height=2,
            font=("Microsoft YaHei UI", 8),
        )
        self.status_label.grid(
            row=4, column=0, columnspan=5, sticky="nsew", pady=(3, 0)
        )
        self.status_label.bind("<ButtonPress-1>", self._drag_start)
        self.status_label.bind("<B1-Motion>", self._drag_move)
        self.status_label.bind("<ButtonRelease-1>", self._drag_end)
        overwrite = tk.Checkbutton(
            bar,
            text="覆盖锁定卡",
            variable=self.allow_overwrite,
            command=self._persist_overwrite_pref,
            bg="#4a2410",
            fg="#f6d89b",
            selectcolor="#3b1c0e",
            activebackground="#4a2410",
            activeforeground="#ffe4a3",
            font=("Microsoft YaHei UI", 8),
            anchor="w",
        )
        overwrite.grid(row=5, column=0, columnspan=5, sticky="w", pady=(1, 0))
        for column in range(5):
            bar.columnconfigure(column, weight=1)
        bar.rowconfigure(4, weight=1)

    def _select_slot(self, index: int) -> None:
        self._commit_name()
        self.selected_slot.set(index)
        self._refresh_slot_buttons()
        preset = self.store.presets[index]
        self.name_var.set(preset.name)
        self.status.set(f"{preset.name}：{len(preset.cards)} 张卡")

    def _focus_rename(self, index: int) -> None:
        self._select_slot(index)
        self.name_entry.focus_set()
        self.name_entry.selection_range(0, "end")

    def _commit_name(self, _event: object | None = None) -> None:
        if not getattr(self, "_prefs_ready", False):
            return
        index = int(self.selected_slot.get())
        name = PresetStore.sanitize_name(self.name_var.get(), index)
        self.name_var.set(name)
        if self.store.presets[index].name != name:
            self.store.presets[index].name = name
            self.store.save()
        self._refresh_slot_buttons()

    def _slot_button_text(self, index: int) -> str:
        name = self.store.presets[index].name.strip()
        default = f"卡组 {index + 1}"
        if not name or name == default:
            return str(index + 1)
        return name[:SLOT_BUTTON_LABEL_LEN]

    def _refresh_slot_buttons(self) -> None:
        selected = self.selected_slot.get()
        for index, button in enumerate(self.slot_buttons):
            button.configure(
                text=self._slot_button_text(index),
                bg="#ffc85b" if index == selected else "#8b5a2b",
                fg="#2b1808" if index == selected else "white",
                activebackground="#ffd77d",
            )

    def _set_status(self, message: str) -> None:
        self.status.set(message)

    def _persist_overwrite_pref(self) -> None:
        if not getattr(self, "_prefs_ready", False):
            return
        self.store.allow_overwrite_locked = bool(self.allow_overwrite.get())
        self.store.save()

    def _drag_start(self, event: object) -> None:
        self._dragging = True
        self._drag_pointer = (int(event.x_root), int(event.y_root))
        self._drag_geom = (int(self.root.winfo_x()), int(self.root.winfo_y()))

    def _drag_move(self, event: object) -> None:
        if not self._dragging:
            return
        x = self._drag_geom[0] + int(event.x_root) - self._drag_pointer[0]
        y = self._drag_geom[1] + int(event.y_root) - self._drag_pointer[1]
        x, y = self._clamp_overlay(x, y)
        width = int(self.root.winfo_width() or 220)
        self.root.geometry(f"{width}x{self.PANEL_HEIGHT}+{x}+{y}")

    def _drag_end(self, _event: object) -> None:
        if not self._dragging:
            return
        self._dragging = False
        session = self.connector.ensure_session()
        if not session:
            return
        origin = POINT(0, 0)
        if not user32.ClientToScreen(session.hwnd, ctypes.byref(origin)):
            return
        x, y = self._clamp_overlay(
            int(self.root.winfo_x()), int(self.root.winfo_y())
        )
        self.store.overlay_offset = (x - origin.x, y - origin.y)
        self.store.save()
        self._last_place = None

    def _client_origin_size(
        self, session: GameSession
    ) -> tuple[int, int, int, int] | None:
        client = RECT()
        origin = POINT(0, 0)
        if not user32.GetClientRect(session.hwnd, ctypes.byref(client)):
            return None
        if not user32.ClientToScreen(session.hwnd, ctypes.byref(origin)):
            return None
        return (
            origin.x,
            origin.y,
            client.right - client.left,
            client.bottom - client.top,
        )

    def _clamp_overlay(
        self, x: int, y: int, width: int | None = None
    ) -> tuple[int, int]:
        session = self.connector.ensure_session()
        width = width or max(210, int(self.root.winfo_width() or 230))
        if not session:
            return x, y
        place = self._client_origin_size(session)
        if not place:
            return x, y
        origin_x, origin_y, game_width, game_height = place
        min_y = origin_y + SEED_BANK_ROW_HEIGHT
        max_x = origin_x + max(0, game_width - width)
        max_y = origin_y + max(
            SEED_BANK_ROW_HEIGHT, game_height - self.PANEL_HEIGHT
        )
        x = min(max(x, origin_x), max_x)
        y = min(max(y, min_y), max_y)
        return x, y

    def save_current(self) -> None:
        session = self.connector.ensure_session()
        if not session:
            self.status.set("未检测到游戏。")
            return
        self._commit_name()
        try:
            cards, capacity, source = session.read_current_deck(
                wait_stable=False
            )
            slot = self.selected_slot.get()
            self.store.presets[slot].cards = PresetStore._sanitize_cards(cards)
            self.store.save()
            suffix = "（战斗卡槽）" if source == "战斗卡槽" else ""
            lock_note = ""
            try:
                chooser = session._chooser()
                locked_n = sum(
                    1
                    for item in session._selected_entries(chooser)
                    if item.locked
                )
                if locked_n:
                    lock_note = f"，含{locked_n}张锁定"
            except DeckAssistantError:
                pass
            self.status.set(
                f"已保存到「{self.store.presets[slot].name}」："
                f"{len(cards)}/{capacity} 张{suffix}{lock_note}"
            )
        except Exception as exc:
            self.status.set(f"保存失败：{exc}")

    def apply_current(self) -> None:
        session = self.connector.ensure_session()
        if not session:
            self.status.set("未检测到游戏。")
            return
        self._commit_name()
        slot = self.selected_slot.get()
        preset_cards = self.store.presets[slot].cards
        overwrite = bool(self.allow_overwrite.get())
        try:
            if overwrite:
                locked = session.locked_apply_conflict(preset_cards)
                if locked:
                    from tkinter import messagebox

                    names = "、".join(
                        self.name_store.get(item.card.seed_type) for item in locked
                    )
                    confirmed = messagebox.askokcancel(
                        "覆盖锁定卡",
                        (
                            f"本关锁定 {len(locked)} 张：{names}。\n"
                            "强制覆盖会移走这些卡并写入当前卡组，"
                            "可能改变本关机制。确定继续？"
                        ),
                        parent=self.root,
                    )
                    if not confirmed:
                        self.status.set("已取消覆盖锁定卡。")
                        return
            count, capacity = session.apply_deck(
                preset_cards, overwrite_locked=overwrite
            )
            note = getattr(session, "last_apply_note", "")
            if note.startswith("，"):
                note = "\n" + note[1:]
            self.status.set(
                f"已应用「{self.store.presets[slot].name}」："
                f"{count}/{capacity}{note}"
            )
            if self.order_strip and self.order_strip.window.winfo_exists():
                self.order_strip.refresh()
        except Exception as exc:
            self.status.set(f"应用失败：{exc}")

    def clear_current(self) -> None:
        session = self.connector.ensure_session()
        if not session:
            self.status.set("未检测到游戏。")
            return
        overwrite = bool(self.allow_overwrite.get())
        try:
            locked = []
            if overwrite:
                locked = [
                    item
                    for item in session._selected_entries(session._chooser())
                    if item.locked
                ]
                if locked:
                    from tkinter import messagebox

                    names = "、".join(
                        self.name_store.get(item.card.seed_type) for item in locked
                    )
                    confirmed = messagebox.askokcancel(
                        "清空锁定卡",
                        (
                            f"本关锁定 {len(locked)} 张：{names}。\n"
                            "清空会移走这些卡，可能改变本关机制。确定继续？"
                        ),
                        parent=self.root,
                    )
                    if not confirmed:
                        self.status.set("已取消清空锁定卡。")
                        return
            remaining, capacity = session.clear_bank(
                overwrite_locked=overwrite
            )
            note = getattr(session, "last_apply_note", "")
            if note.startswith("，"):
                note = "\n" + note[1:]
            self.status.set(f"已清空选卡栏：{remaining}/{capacity}{note}")
            if self.order_strip and self.order_strip.window.winfo_exists():
                if remaining:
                    self.order_strip.refresh()
                else:
                    self.order_strip.close()
                    self.order_strip = None
        except Exception as exc:
            self.status.set(f"清空失败：{exc}")

    def open_sorter(self) -> None:
        if self.order_strip and self.order_strip.window.winfo_exists():
            self.order_strip.refresh()
            self.order_strip.window.lift()
            return
        self.order_strip = DeckOrderStrip(
            self.root,
            self.connector,
            self.store,
            self.name_store,
            self.selected_slot,
            self._set_status,
            self._refresh_slot_buttons,
        )

    def _tick(self) -> None:
        try:
            session = self.connector.ensure_session()
            game_visible = bool(
                session
                and user32.IsWindowVisible(session.hwnd)
                and not user32.IsIconic(session.hwnd)
            )
            if not game_visible or not session.chooser_ready():
                self._hide_overlay()
            else:
                self._load_resource_names(session)
                self._attach_to_game(session)
                tooltip_name = session.current_tooltip_name()
                if tooltip_name:
                    self.name_store.update(dict([tooltip_name]))
                if self.status.get().startswith(("等待", "请进入")):
                    self.status.set("保存 / 应用 / 清空；双击卡组位改名")
        except Exception:
            try:
                self._hide_overlay()
            except Exception:
                pass
        try:
            self.root.after(250, self._tick)
        except Exception:
            pass

    def _hide_overlay(self) -> None:
        if self.order_strip and self.order_strip.window.winfo_exists():
            self.order_strip.close()
            self.order_strip = None
        if self._overlay_visible:
            self.root.withdraw()
            self._overlay_visible = False
            self._last_place = None

    def _show_waiting(self) -> None:
        self._hide_overlay()

    def _attach_to_game(self, session: GameSession) -> None:
        if self._dragging:
            return
        place = self._client_origin_size(session)
        if not place:
            return
        origin_x, origin_y, game_width, game_height = place
        panel_width = max(280, min(340, int(game_width * 0.30)))
        default_x = origin_x + game_width - panel_width - 8
        default_y = origin_y + SEED_BANK_ROW_HEIGHT
        if self.store.overlay_offset:
            x = origin_x + self.store.overlay_offset[0]
            y = origin_y + self.store.overlay_offset[1]
        else:
            x, y = default_x, default_y
        x, y = self._clamp_overlay(x, y, panel_width)
        try:
            self.status_label.configure(wraplength=max(200, panel_width - 14))
        except Exception:
            pass
        key = (x, y, panel_width, self.PANEL_HEIGHT)
        if key == self._last_place:
            if not self._overlay_visible:
                self.root.deiconify()
                self._overlay_visible = True
            return
        self._last_place = key
        self.root.geometry(
            f"{panel_width}x{self.PANEL_HEIGHT}+{x}+{y}"
        )
        self.root.update_idletasks()
        content_hwnd = int(self.root.winfo_id())
        wrapper_hwnd = user32.GetParent(content_hwnd)
        overlay_hwnd = int(wrapper_hwnd or content_hwnd)
        user32.SetWindowPos(
            overlay_hwnd,
            HWND_TOPMOST,
            x,
            y,
            panel_width,
            self.PANEL_HEIGHT,
            SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )
        self.root.deiconify()
        self._overlay_visible = True

    def close(self) -> None:
        if self.order_strip and self.order_strip.window.winfo_exists():
            self.order_strip.close()
        self.connector.close()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


class DeckAssistantWindow:
    def __init__(self) -> None:
        import tkinter as tk
        from tkinter import messagebox, ttk

        self.tk = tk
        self.messagebox = messagebox
        self.ttk = ttk
        self.store = PresetStore()
        self.root = tk.Tk()
        self.root.title(f"杂交版 v3.12 卡组助手 · {ASSISTANT_VERSION}")
        self.root.geometry("720x820")
        self.root.minsize(650, 640)

        self.selected_slot = tk.IntVar(value=0)
        self.status = tk.StringVar(value="正在检测游戏……")
        self.name_vars = [
            tk.StringVar(value=preset.name) for preset in self.store.presets
        ]
        self.card_vars = [
            tk.StringVar(value=format_cards(preset.cards))
            for preset in self.store.presets
        ]
        self._build()
        self._poll_status()

    def _build(self) -> None:
        ttk = self.ttk
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="植物大战僵尸杂交版 · 卡组助手",
            font=("Microsoft YaHei UI", 15, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text="选择一个存储栏，然后读取游戏卡组或将预设覆盖到选卡栏。",
        ).pack(anchor="w", pady=(4, 14))

        for index in range(PRESET_SLOT_COUNT):
            row = ttk.Frame(outer, padding=(10, 8))
            row.pack(fill="x", pady=3)
            ttk.Radiobutton(
                row,
                text=f"存储栏 {index + 1}",
                variable=self.selected_slot,
                value=index,
            ).grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 12))
            name = ttk.Entry(row, textvariable=self.name_vars[index], width=18)
            name.grid(row=0, column=1, sticky="w")
            name.bind("<FocusOut>", lambda _event, i=index: self._save_name(i))
            ttk.Label(
                row,
                textvariable=self.card_vars[index],
                foreground="#555555",
                wraplength=470,
            ).grid(row=1, column=1, sticky="w", pady=(4, 0))
            row.columnconfigure(1, weight=1)

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(16, 10))
        ttk.Button(
            actions,
            text="读取当前卡组 → 覆盖存储栏",
            command=self.read_into_slot,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6), ipady=7)
        ttk.Button(
            actions,
            text="使用存储卡组 → 覆盖游戏卡组",
            command=self.apply_selected_slot,
        ).pack(side="left", expand=True, fill="x", padx=(6, 0), ipady=7)

        ttk.Separator(outer).pack(fill="x", pady=(4, 10))
        ttk.Label(outer, textvariable=self.status).pack(anchor="w")
        ttk.Label(
            outer,
            text="提示：应用卡组仅支持普通选卡界面；预设保存在当前 Windows 用户目录。",
            foreground="#666666",
        ).pack(anchor="w", pady=(5, 0))

    def _save_name(self, index: int) -> None:
        name = PresetStore.sanitize_name(
            self.name_vars[index].get(), index
        )
        self.name_vars[index].set(name)
        self.store.presets[index].name = name
        self.store.save()

    def read_into_slot(self) -> None:
        index = self.selected_slot.get()
        try:
            with GameSession() as game:
                cards, capacity, source = game.read_current_deck()
            self.store.presets[index].name = PresetStore.sanitize_name(
                self.name_vars[index].get(), index
            )
            self.store.presets[index].cards = PresetStore._sanitize_cards(cards)
            self.store.save()
            self.card_vars[index].set(format_cards(cards))
            self.status.set(
                f"已从{source}读取 {len(cards)}/{capacity} 张卡，"
                f"并覆盖存储栏 {index + 1}。"
            )
        except Exception as exc:
            self._show_error(exc)

    def apply_selected_slot(self) -> None:
        index = self.selected_slot.get()
        preset = self.store.presets[index]
        try:
            with GameSession() as game:
                overwrite = bool(self.store.allow_overwrite_locked)
                if overwrite:
                    locked = game.locked_apply_conflict(preset.cards)
                    if locked:
                        names = "、".join(
                            f"#{item.card.seed_type}" for item in locked
                        )
                        if not self.messagebox.askokcancel(
                            "覆盖锁定卡",
                            (
                                f"本关锁定 {len(locked)} 张：{names}。\n"
                                "强制覆盖会移走这些卡并写入当前卡组，"
                                "可能改变本关机制。确定继续？"
                            ),
                        ):
                            self.status.set("已取消覆盖锁定卡。")
                            return
                count, capacity = game.apply_deck(
                    preset.cards, overwrite_locked=overwrite
                )
            self.status.set(
                f"已将“{preset.name}”的 {count}/{capacity} 张卡覆盖到游戏选卡栏"
                f"{getattr(game, 'last_apply_note', '')}。"
            )
        except Exception as exc:
            self._show_error(exc)

    def _show_error(self, exc: Exception) -> None:
        message = str(exc)
        self.status.set(f"操作失败：{message}")
        self.messagebox.showerror("卡组助手", message)

    def _poll_status(self) -> None:
        try:
            with GameSession() as game:
                try:
                    capacity = game._capacity()
                    self.status.set(f"已连接游戏（当前卡槽：{capacity}）")
                except DeckAssistantError:
                    self.status.set("已连接游戏，等待进入关卡选卡界面。")
        except Exception:
            self.status.set("未检测到游戏，请先启动杂交版 v3.12。")
        self.root.after(1500, self._poll_status)

    def run(self) -> None:
        self.root.mainloop()


def print_status() -> int:
    try:
        with GameSession() as game:
            cards, capacity, source = game.read_current_deck()
        print(
            json.dumps(
                {
                    "connected": True,
                    "source": source,
                    "capacity": capacity,
                    "cards": [asdict(card) for card in cards],
                },
                ensure_ascii=False,
            )
        )
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {"connected": False, "error": str(exc)},
                ensure_ascii=False,
            )
        )
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--status",
        action="store_true",
        help="输出当前连接和卡组状态，不打开界面",
    )
    parser.add_argument(
        "--classic",
        action="store_true",
        help="打开旧版独立管理窗口",
    )
    args = parser.parse_args()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass
    if args.status:
        return print_status()
    ctypes.set_last_error(0)
    mutex = kernel32.CreateMutexW(
        None, False, "Local\\PvZHybridDeckAssistantV2"
    )
    if not mutex:
        user32.MessageBoxW(
            None,
            "无法创建单实例锁，助手未启动。请重试或重新启动 Windows。",
            "杂交版卡组助手",
            0x10,
        )
        return 1
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(mutex)
        user32.MessageBoxW(
            None,
            "卡组助手已经在运行。进入选卡界面后即可看到工具栏。",
            "杂交版卡组助手",
            0x40,
        )
        return 0
    try:
        if args.classic:
            DeckAssistantWindow().run()
        else:
            IntegratedDeckOverlay().run()
        return 0
    except Exception as exc:
        user32.MessageBoxW(
            None,
            f"助手异常退出：{exc}"[:800],
            "杂交版卡组助手",
            0x10,
        )
        return 1
    finally:
        if mutex:
            kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    sys.exit(main())
