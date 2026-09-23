from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from .core import Track, crossed, format_time


@dataclass
class Snapshot:
    frame: object
    seconds: float
    visible: int
    count: int
    revenue: int
    events: list[dict] = field(default_factory=list)
    error: str = ""


def _crop_score(crop, box_area: int, frame_area: int, confidence: float) -> float:
    import cv2

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    sharpness = min(float(cv2.Laplacian(gray, cv2.CV_64F).var()) / 150.0, 1.0)
    area = min(box_area / max(frame_area * 0.15, 1), 1.0)
    return 0.50 * area + 0.30 * confidence + 0.20 * sharpness


def scaled_dimensions(width: int, height: int, max_side: int = 1280) -> tuple[int, int]:
    """Keep the source aspect ratio while limiting 4K inference and output size."""
    if width <= 0 or height <= 0:
        raise ValueError("Invalid video dimensions")
    scale = min(1.0, max_side / max(width, height))
    if scale == 1.0:
        return width, height
    return max(2, round(width * scale / 2) * 2), max(2, round(height * scale / 2) * 2)


def _save_reports(folder: Path, events: list[dict], count: int, revenue: int) -> None:
    fields = ["event_id", "timestamp", "track_id", "body_type", "size", "tariff_class",
              "confidence", "tariff", "status", "crop"]
    with (folder / "events.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(events)
    summary = {
        "vehicles": count,
        "estimated_revenue": revenue,
        "review_count": sum(e["status"] != "Otomatis" for e in events),
        "by_class": {name: sum(e["tariff_class"] == name for e in events)
                     for name in ("MOTORCYCLE", "SMALL", "MEDIUM", "LARGE", "COMMERCIAL", "REVIEW")},
    }
    (folder / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def process_video(
    source: Path,
    output_dir: Path,
    model_name: str,
    line_fraction: float,
    direction: str,
    tariffs: dict[str, int],
    classifier,
    threshold: float,
    model_override=None,
    count_mode: str = "line",
    max_side: int = 1280,
) -> Iterator[Snapshot]:
    import cv2
    config_dir = Path.cwd() / ".ultralytics"
    config_dir.mkdir(exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(config_dir))
    from ultralytics import YOLO

    output_dir.mkdir(parents=True, exist_ok=True)
    crops_dir = output_dir / "crops"
    crops_dir.mkdir(exist_ok=True)
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError("Video tidak bisa dibuka. Coba file MP4 lain.")
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if width <= 0 or height <= 0:
        capture.release()
        raise RuntimeError("Resolusi video tidak terbaca.")
    if count_mode not in {"line", "presence"}:
        capture.release()
        raise ValueError("Unknown count mode")
    width, height = scaled_dimensions(width, height, max_side)
    writer = cv2.VideoWriter(str(output_dir / "annotated.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        capture.release()
        raise RuntimeError("Video output tidak bisa dibuat.")
    try:
        model = model_override if model_override is not None else YOLO(model_name)
    except Exception:
        capture.release()
        writer.release()
        raise
    line_y = int(height * line_fraction)
    tracks: dict[int, Track] = {}
    events: list[dict] = []
    frame_index = 0
    revenue = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if frame.shape[1] != width or frame.shape[0] != height:
                frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
            frame_index += 1
            seconds = frame_index / fps
            result = model.track(frame, persist=True, tracker="bytetrack.yaml",
                                 classes=[2, 3, 5, 7], verbose=False, conf=0.25)[0]
            visible = 0
            if result.boxes is not None and result.boxes.id is not None:
                boxes = result.boxes
                ids = boxes.id.int().cpu().tolist()
                coords = boxes.xyxy.int().cpu().tolist()
                confidences = boxes.conf.cpu().tolist()
                for track_id, (x1, y1, x2, y2), confidence in zip(ids, coords, confidences):
                    x1, x2 = max(0, x1), min(width, x2)
                    y1, y2 = max(0, y1), min(height, y2)
                    if x2 <= x1 or y2 <= y1:
                        continue
                    visible += 1
                    track = tracks.setdefault(track_id, Track())
                    track.seen += 1
                    center_y = (y1 + y2) / 2
                    crop = frame[y1:y2, x1:x2]
                    score = _crop_score(crop, (x2-x1)*(y2-y1), width*height, confidence)
                    if score > track.best_score:
                        track.best_score = score
                        track.best_crop = crop.copy()
                    entering = (not track.counted and track.seen >= 3) if count_mode == "presence" else (
                        not track.counted and track.seen >= 2 and
                        crossed(track.previous_y, center_y, line_y, direction))
                    if entering:
                        track.counted = True
                        crop_name = f"vehicle_{len(events)+1:04d}.jpg"
                        cv2.imwrite(str(crops_dir / crop_name), track.best_crop)
                        body_type, size, klass, confidence_value, status = "Menunggu", "", "REVIEW", 0.0, "Perlu cek manual"
                        if classifier is not None:
                            try:
                                found = classifier.classify(track.best_crop, threshold)
                                body_type, size, klass = found.body_type, found.size, found.tariff_class
                                confidence_value, status = found.confidence, found.status
                            except Exception as exc:
                                status = f"Klasifikasi gagal: {type(exc).__name__}"
                        track.body_type, track.tariff_class = body_type, klass
                        track.tariff = tariffs.get(klass) if status == "Otomatis" else None
                        if track.tariff is not None:
                            revenue += track.tariff
                        events.append({
                            "event_id": f"CW-{len(events)+1:05d}",
                            "timestamp": format_time(seconds),
                            "track_id": track_id,
                            "body_type": body_type,
                            "size": size,
                            "tariff_class": klass,
                            "confidence": round(confidence_value, 4),
                            "tariff": track.tariff if track.tariff is not None else "",
                            "status": status,
                            "crop": f"crops/{crop_name}",
                        })
                    track.previous_y = center_y
                    color = (45, 190, 90) if track.counted else (0, 185, 255)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    label = f"#{track_id} {track.tariff_class if track.counted else 'mendekat'}"
                    cv2.putText(frame, label, (x1, max(22, y1-8)), cv2.FONT_HERSHEY_SIMPLEX,
                                0.65, color, 2, cv2.LINE_AA)
            if count_mode == "line":
                cv2.line(frame, (0, line_y), (width, line_y), (255, 180, 0), 2)
                cv2.putText(frame, "ENTRY", (12, max(25, line_y-8)), cv2.FONT_HERSHEY_SIMPLEX,
                            0.65, (255, 180, 0), 2, cv2.LINE_AA)
            writer.write(frame)
            yield Snapshot(frame, seconds, visible, len(events), revenue, events.copy())
    finally:
        capture.release()
        writer.release()
        _save_reports(output_dir, events, len(events), revenue)
