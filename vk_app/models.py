"""Data structures describing virtual keyboard keys."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any

from PyQt6.QtCore import QPoint


@dataclass
class KeyDefinition:
    """Serializable description of a virtual key."""

    label: str
    sequence: str
    locked: bool = False
    position: QPoint = field(default_factory=lambda: QPoint(50, 50))
    kind: str = "normal"
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "sequence": self.sequence,
            "locked": self.locked,
            "x": int(self.position.x()),
            "y": int(self.position.y()),
            "kind": self.kind,
            "config": self.config,
        }

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "KeyDefinition":
        point = QPoint(int(payload.get("x", 50)), int(payload.get("y", 50)))
        kind = str(payload.get("kind", "normal"))
        config_payload = payload.get("config", {})
        config = dict(config_payload) if isinstance(config_payload, dict) else {}
        return KeyDefinition(
            label=str(payload.get("label", "?")),
            sequence=str(payload.get("sequence", "A")),
            locked=bool(payload.get("locked", False)),
            position=point,
            kind=kind,
            config=config,
        )
