"""Utilities for sending keyboard input via Win32."""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from PyQt6.QtCore import Qt  # Imported to ensure Qt DLLs are loaded before SendInput.

from .winapi import INPUT, KEYBDINPUT, kernel32, user32


@dataclass(frozen=True)
class ParsedSequence:
    """Represents a parsed key sequence."""

    vk: int
    modifiers: Tuple[int, ...]
    tokens: Tuple[str, ...]


class KeySender:
    """Wraps Win32 SendInput for character and modifier combinations."""

    _MODIFIER_TOKENS: Dict[str, Tuple[int, str, str]] = {
        "SHIFT": (0xA0, "Shift", "SHIFT"),
        "LSHIFT": (0xA0, "Left Shift", "SHIFT"),
        "LEFTSHIFT": (0xA0, "Left Shift", "SHIFT"),
        "LSSHIFT": (0xA0, "Left Shift", "SHIFT"),
        "RSHIFT": (0xA1, "Right Shift", "SHIFT"),
        "RIGHTSHIFT": (0xA1, "Right Shift", "SHIFT"),
        "RSSHIFT": (0xA1, "Right Shift", "SHIFT"),
        "CTRL": (0xA2, "Ctrl", "CTRL"),
        "CONTROL": (0xA2, "Ctrl", "CTRL"),
        "LCTRL": (0xA2, "Left Ctrl", "CTRL"),
        "LEFTCTRL": (0xA2, "Left Ctrl", "CTRL"),
        "LEFTCONTROL": (0xA2, "Left Ctrl", "CTRL"),
        "RCTRL": (0xA3, "Right Ctrl", "CTRL"),
        "RIGHTCTRL": (0xA3, "Right Ctrl", "CTRL"),
        "RIGHTCONTROL": (0xA3, "Right Ctrl", "CTRL"),
        "ALT": (0xA4, "Alt", "ALT"),
        "OPTION": (0xA4, "Alt", "ALT"),
        "LALT": (0xA4, "Left Alt", "ALT"),
        "LEFTALT": (0xA4, "Left Alt", "ALT"),
        "LOPTION": (0xA4, "Left Alt", "ALT"),
        "RALT": (0xA5, "Right Alt", "ALT"),
        "RIGHTALT": (0xA5, "Right Alt", "ALT"),
        "ROPTION": (0xA5, "Right Alt", "ALT"),
        "WIN": (0x5B, "Win", "WIN"),
        "LWIN": (0x5B, "Left Win", "WIN"),
        "LEFTWIN": (0x5B, "Left Win", "WIN"),
        "RWIN": (0x5C, "Right Win", "WIN"),
        "RIGHTWIN": (0x5C, "Right Win", "WIN"),
        "CMD": (0x5B, "Win", "WIN"),
        "COMMAND": (0x5B, "Win", "WIN"),
        "META": (0x5B, "Win", "WIN"),
    }

    _NAMED_KEYS: Dict[str, Tuple[int, str]] = {
        "ENTER": (0x0D, "Enter"),
        "RETURN": (0x0D, "Enter"),
        "ESC": (0x1B, "Esc"),
        "ESCAPE": (0x1B, "Esc"),
        "TAB": (0x09, "Tab"),
        "SPACE": (0x20, "Space"),
        "SPACEBAR": (0x20, "Space"),
        "BACKSPACE": (0x08, "Backspace"),
        "BS": (0x08, "Backspace"),
        "UP": (0x26, "Up"),
        "DOWN": (0x28, "Down"),
        "LEFT": (0x25, "Left"),
        "RIGHT": (0x27, "Right"),
        "DELETE": (0x2E, "Delete"),
        "DEL": (0x2E, "Delete"),
        "INSERT": (0x2D, "Insert"),
        "INS": (0x2D, "Insert"),
        "HOME": (0x24, "Home"),
        "END": (0x23, "End"),
        "PAGEUP": (0x21, "Page Up"),
        "PGUP": (0x21, "Page Up"),
        "PAGEDOWN": (0x22, "Page Down"),
        "PGDN": (0x22, "Page Down"),
        "CAPSLOCK": (0x14, "Caps Lock"),
        "CAPS": (0x14, "Caps Lock"),
        "NUMLOCK": (0x90, "Num Lock"),
        "SCROLLLOCK": (0x91, "Scroll Lock"),
        "SCROLL": (0x91, "Scroll Lock"),
        "PRINTSCREEN": (0x2C, "Print Screen"),
        "PRTSC": (0x2C, "Print Screen"),
        "MENU": (0x5D, "Menu"),
        "APPS": (0x5D, "Menu"),
        "PAUSE": (0x13, "Pause"),
        "BREAK": (0x13, "Pause"),
    }

    for index in range(1, 25):
        key = f"F{index}"
        _NAMED_KEYS[key] = (0x6F + index, key)

    _IMPLICIT_MODIFIERS: Tuple[Tuple[int, str, str], ...] = (
        (0xA0, "Shift", "SHIFT"),
        (0xA2, "Ctrl", "CTRL"),
        (0xA4, "Alt", "ALT"),
    )

    def __init__(self) -> None:
        self._cached_layout = user32.GetKeyboardLayout(0)

    def send_sequence(self, sequence: str) -> None:
        sequence = sequence.strip()
        if not sequence:
            return

        parsed = self.parse_sequence(sequence)
        events: List[Tuple[int, bool]] = []
        for mod in parsed.modifiers:
            events.append((mod, False))
        events.append((parsed.vk, False))
        events.append((parsed.vk, True))
        for mod in reversed(parsed.modifiers):
            events.append((mod, True))
        self._send_events(events)

    def press_hold(self, sequence: str) -> Optional[Tuple[int, Tuple[int, ...]]]:
        sequence = sequence.strip()
        if not sequence:
            return None
        parsed = self.parse_sequence(sequence)
        events: List[Tuple[int, bool]] = []
        for mod in parsed.modifiers:
            events.append((mod, False))
        events.append((parsed.vk, False))
        self._send_events(events)
        return parsed.vk, tuple(parsed.modifiers)

    def release_hold(self, combination: Tuple[int, Tuple[int, ...]]) -> None:
        vk, modifiers = combination
        events: List[Tuple[int, bool]] = [(vk, True)]
        for mod in reversed(modifiers):
            events.append((mod, True))
        self._send_events(events)

    def parse_sequence(self, sequence: str) -> ParsedSequence:
        sequence = sequence.strip()
        if not sequence:
            raise ValueError("Empty sequence")
        return self._parse_sequence(sequence)

    def normalize_sequence(self, sequence: str) -> str:
        parsed = self.parse_sequence(sequence)
        return " + ".join(parsed.tokens)

    def _parse_sequence(self, sequence: str) -> ParsedSequence:
        parts = [chunk.strip() for chunk in sequence.split("+") if chunk.strip()]
        if not parts:
            raise ValueError("Empty sequence")

        modifiers: List[int] = []
        modifier_names: List[str] = []
        seen_vks: set[int] = set()
        skip_groups_for_implicit: set[str] = set()

        for part in parts[:-1]:
            resolved = self._resolve_modifier(part)
            if not resolved:
                raise ValueError(f"Unknown modifier: {part}")
            vk, name, group = resolved
            if vk not in seen_vks:
                modifiers.append(vk)
                modifier_names.append(name)
                seen_vks.add(vk)
            skip_groups_for_implicit.add(group)

        base_vk, base_name, implicit_mods = self._resolve_key(parts[-1])
        for vk, name, group in implicit_mods:
            if group in skip_groups_for_implicit:
                continue
            if vk in seen_vks:
                continue
            modifiers.append(vk)
            modifier_names.append(name)
            seen_vks.add(vk)
            skip_groups_for_implicit.add(group)

        tokens = tuple(modifier_names + [base_name])
        return ParsedSequence(base_vk, tuple(modifiers), tokens)

    def _send_events(self, events: Sequence[Tuple[int, bool]]) -> None:
        if not events:
            return

        inputs = [self._create_input(vk, is_keyup=is_keyup) for vk, is_keyup in events]
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

    def _resolve_modifier(self, token: str) -> Optional[Tuple[int, str, str]]:
        key = self._normalize_token_key(token)
        return self._MODIFIER_TOKENS.get(key)

    def _fallback_keybd_event(self, events: Sequence[Tuple[int, bool]]) -> bool:
        try:
            for vk, is_keyup in events:
                flag = 0x0002 if is_keyup else 0x0000
                user32.keybd_event(vk, 0, flag, 0)
            return True
        except Exception:
            return False

    def _resolve_key(self, token: str) -> Tuple[int, str, List[Tuple[int, str, str]]]:
        lookup = self._normalize_token_key(token)
        named = self._NAMED_KEYS.get(lookup)
        if named:
            vk, name = named
            return vk, name, []

        if len(token) == 1:
            char_code = ord(token)
            vk_scan = user32.VkKeyScanExW(char_code, self._cached_layout)
            if vk_scan == -1:
                raise ValueError(f"Unsupported key: {token}")
            vk = vk_scan & 0xFF
            base_char = token.upper() if token.isalpha() else token
            implicit: List[Tuple[int, str, str]] = []
            for mask, (mod_vk, name, group) in zip(
                (0x0100, 0x0200, 0x0400), self._IMPLICIT_MODIFIERS
            ):
                if vk_scan & mask:
                    implicit.append((mod_vk, name, group))
            return vk, base_char, implicit

        modifier = self._resolve_modifier(token)
        if modifier:
            vk, name, group = modifier
            return vk, name, []

        raise ValueError(f"Unsupported key token: {token}")

    @staticmethod
    def _normalize_token_key(token: str) -> str:
        return "".join(ch for ch in token.upper() if ch.isalnum())
