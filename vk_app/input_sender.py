"""Utilities for sending keyboard input via Win32."""
from __future__ import annotations

import ctypes
from typing import Dict, List, Optional, Sequence, Tuple

from PyQt6.QtCore import Qt  # Imported to ensure Qt DLLs are loaded before SendInput.

from .winapi import INPUT, KEYBDINPUT, kernel32, user32


class KeySender:
    """Wraps Win32 SendInput for character and modifier combinations."""

    MODIFIERS: Dict[str, int] = {
        "SHIFT": 0x10,
        "CTRL": 0x11,
        "ALT": 0x12,
    }

    NAMED_KEYS: Dict[str, int] = {
        "ENTER": 0x0D,
        "ESC": 0x1B,
        "TAB": 0x09,
        "SPACE": 0x20,
        "BACKSPACE": 0x08,
        "UP": 0x26,
        "DOWN": 0x28,
        "LEFT": 0x25,
        "RIGHT": 0x27,
        "DELETE": 0x2E,
        "HOME": 0x24,
        "END": 0x23,
        "PAGEUP": 0x21,
        "PAGEDOWN": 0x22,
    }

    def __init__(self) -> None:
        self._cached_layout = user32.GetKeyboardLayout(0)

    def send_sequence(self, sequence: str) -> None:
        sequence = sequence.strip()
        if not sequence:
            return

        vk, modifiers = self._parse_sequence(sequence)
        events: List[Tuple[int, bool]] = []
        for mod in modifiers:
            events.append((mod, False))
        events.append((vk, False))
        events.append((vk, True))
        for mod in reversed(modifiers):
            events.append((mod, True))
        self._send_events(events)

    def press_hold(self, sequence: str) -> Optional[Tuple[int, Tuple[int, ...]]]:
        sequence = sequence.strip()
        if not sequence:
            return None
        vk, modifiers = self._parse_sequence(sequence)
        events: List[Tuple[int, bool]] = []
        for mod in modifiers:
            events.append((mod, False))
        events.append((vk, False))
        self._send_events(events)
        return vk, tuple(modifiers)

    def release_hold(self, combination: Tuple[int, Tuple[int, ...]]) -> None:
        vk, modifiers = combination
        events: List[Tuple[int, bool]] = [(vk, True)]
        for mod in reversed(modifiers):
            events.append((mod, True))
        self._send_events(events)

    def _parse_sequence(self, sequence: str) -> Tuple[int, List[int]]:
        parts = [chunk.strip() for chunk in sequence.split("+") if chunk.strip()]
        if not parts:
            raise ValueError("Empty sequence")

        modifiers: List[int] = []
        base_part = parts[-1]
        for part in parts[:-1]:
            vk = self._resolve_modifier(part)
            if vk:
                modifiers.append(vk)
            else:
                raise ValueError(f"Unknown modifier: {part}")

        base_vk, implicit_mods = self._resolve_key(base_part)
        for vk in implicit_mods:
            if vk not in modifiers:
                modifiers.append(vk)
        return base_vk, modifiers

    def _send_events(self, events: Sequence[Tuple[int, bool]]) -> None:
        if not events:
            return

        inputs = [self._create_input(vk, is_keyup) for vk, is_keyup in events]
        array_type = INPUT * len(inputs)
        input_array = array_type(*inputs)
        ctypes.set_last_error(0)
        sent = user32.SendInput(len(inputs), input_array, ctypes.sizeof(INPUT))
        if sent == len(inputs):
            return

        error_code = ctypes.get_last_error()
        if self._fallback_keybd_event(events):
            return

        if error_code:
            raise ctypes.WinError(error_code)
        raise OSError("SendInput failed without extended error information")

    def _create_input(self, vk: int, *, is_keyup: bool) -> INPUT:
        flags = 0x0002 if is_keyup else 0x0000
        keyboard_input = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0)
        input_union = INPUT._INPUTUNION()
        input_union.ki = keyboard_input
        return INPUT(type=1, _iu=input_union)

    def _resolve_modifier(self, token: str) -> Optional[int]:
        return self.MODIFIERS.get(token.upper())

    def _fallback_keybd_event(self, events: Sequence[Tuple[int, bool]]) -> bool:
        try:
            for vk, is_keyup in events:
                flag = 0x0002 if is_keyup else 0x0000
                user32.keybd_event(vk, 0, flag, 0)
            return True
        except Exception:
            return False

    def _resolve_key(self, token: str) -> Tuple[int, List[int]]:
        token_upper = token.upper()
        if token_upper in self.NAMED_KEYS:
            return self.NAMED_KEYS[token_upper], []

        if len(token) == 1:
            vk_scan = user32.VkKeyScanExW(ord(token), self._cached_layout)
            if vk_scan == -1:
                raise ValueError(f"Unsupported key: {token}")
            vk = vk_scan & 0xFF
            required_mods: List[int] = []
            if vk_scan & 0x0100:
                required_mods.append(self.MODIFIERS["SHIFT"])
            if vk_scan & 0x0200:
                required_mods.append(self.MODIFIERS["CTRL"])
            if vk_scan & 0x0400:
                required_mods.append(self.MODIFIERS["ALT"])
            return vk, required_mods

        raise ValueError(f"Unsupported key token: {token}")
