from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


TARIFF_CLASSES = ("MOTORCYCLE", "SMALL", "MEDIUM", "LARGE", "COMMERCIAL")
DEFAULT_TARIFFS = {
    "MOTORCYCLE": 15000,
    "SMALL": 30000,
    "MEDIUM": 40000,
    "LARGE": 50000,
    "COMMERCIAL": 65000,
}


@dataclass
class Track:
    previous_y: Optional[float] = None
    seen: int = 0
    counted: bool = False
    best_score: float = -1.0
    best_crop: object = None
    body_type: str = "Menunggu"
    tariff_class: str = "REVIEW"
    tariff: Optional[int] = None


def crossed(previous_y: Optional[float], current_y: float, line_y: float,
            direction: str, margin: float = 0.0) -> bool:
    """Count only a real transition across the line, in the selected direction."""
    if previous_y is None:
        return False
    if direction == "up":
        return previous_y > line_y + margin and current_y < line_y - margin
    if direction == "down":
        return previous_y < line_y - margin and current_y > line_y + margin
    raise ValueError(f"Unknown direction: {direction}")


def tariff_class(body_type: str, size: str, commercial: bool) -> str:
    body = body_type.lower().strip()
    size = size.lower().strip()
    if body == "motorcycle":
        return "MOTORCYCLE"
    if commercial or body in {"pickup", "van"}:
        return "COMMERCIAL"
    if size in {"small", "medium", "large"}:
        return size.upper()
    return "REVIEW"


def format_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"
