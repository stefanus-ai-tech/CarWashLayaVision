"""HTTP API and static dashboard for CarWashVision."""

from __future__ import annotations

import re
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import cv2
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from carwash.core import DEFAULT_TARIFFS
from carwash.pipeline import process_video


ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"
WEB = ROOT / "web"
ALLOWED_FILES = {"annotated.mp4", "events.csv", "summary.json"}
ALLOWED_VIDEO = {".mp4", ".mov", ".avi", ".mkv"}
VIDEO_LIBRARY = Path(os.environ.get("CARWASH_VIDEO_DIR", str(Path.home() / "Videos" / "CuciMobil")))


@dataclass
class Job:
    id: str
    folder: Path
    status: str = "queued"
    message: str = "Menyiapkan video..."
    warning: str = ""
    seconds: float = 0.0
    visible: int = 0
    count: int = 0
    revenue: int = 0
    progress: float = 0.0
    width: int = 0
    height: int = 0
    events: list[dict] = field(default_factory=list)
    frame: bytes | None = None
    frame_seq: int = 0
    lock: threading.RLock = field(default_factory=threading.RLock)
    changed: threading.Condition = field(init=False)

    def __post_init__(self):
        self.changed = threading.Condition(self.lock)

    def payload(self) -> dict:
        with self.lock:
            return {
                "id": self.id,
                "status": self.status,
                "message": self.message,
                "warning": self.warning,
                "seconds": self.seconds,
                "visible": self.visible,
                "count": self.count,
                "revenue": self.revenue,
                "progress": self.progress,
                "width": self.width,
                "height": self.height,
                "event_count": len(self.events),
                "by_class": {name: sum(event["tariff_class"] == name for event in self.events)
                             for name in (*DEFAULT_TARIFFS, "REVIEW")},
                "events": list(reversed(self.events[-30:])),
                "downloads": [name for name in sorted(ALLOWED_FILES) if
                              self.status == "done" and (self.folder / name).exists()],
            }


app = FastAPI(title="CarWashVision")
app.mount("/assets", StaticFiles(directory=WEB), name="assets")
jobs: dict[str, Job] = {}
jobs_lock = threading.Lock()


@app.get("/")
def home():
    return FileResponse(WEB / "index.html")


def _get_job(job_id: str) -> Job:
    with jobs_lock:
        job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Analisis tidak ditemukan")
    return job


def _library_path(filename: str) -> Path:
    path = (VIDEO_LIBRARY / filename).resolve()
    if path.parent != VIDEO_LIBRARY.resolve() or path.suffix.lower() not in ALLOWED_VIDEO or not path.is_file():
        raise HTTPException(404, "Video lokal tidak ditemukan")
    return path


@app.get("/api/library")
def library():
    if not VIDEO_LIBRARY.is_dir():
        return {"videos": []}
    videos = []
    for path in sorted(VIDEO_LIBRARY.iterdir()):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_VIDEO:
            continue
        capture = cv2.VideoCapture(str(path))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = capture.get(cv2.CAP_PROP_FPS) or 0
        frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        capture.release()
        if width and height:
            videos.append({"name": path.name, "width": width, "height": height,
                           "duration": round(frames / fps, 1) if fps else 0,
                           "size_mb": round(path.stat().st_size / 1024 / 1024, 1)})
    return {"videos": videos}


@app.get("/api/library/{filename}/preview")
def library_preview(filename: str):
    return FileResponse(_library_path(filename), media_type="video/mp4")


def _run(job: Job, source: Path, model: str, line: float, direction: str, count_mode: str,
         tariffs: dict[str, int], use_laya: bool, threshold: float):
    classifier = None
    try:
        with job.lock:
            job.status = "loading"
            job.message = "Memuat model..."
        if use_laya:
            try:
                from carwash.classifier import LayaClassifier
                classifier = LayaClassifier()
            except Exception as exc:
                with job.lock:
                    job.warning = f"Laya Vision belum siap: {exc}. Tarif masuk cek manual."
        capture = cv2.VideoCapture(str(source))
        total_frames = max(0, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
        with job.lock:
            job.width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            job.height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        capture.release()
        with job.lock:
            job.status = "running"
            job.message = "Menganalisis video..."
        for index, snapshot in enumerate(process_video(source, job.folder, model, line,
                                                       direction, tariffs, classifier, threshold,
                                                       count_mode=count_mode), 1):
            ok, jpeg = cv2.imencode(".jpg", snapshot.frame, [cv2.IMWRITE_JPEG_QUALITY, 78])
            with job.changed:
                job.seconds = snapshot.seconds
                job.visible = snapshot.visible
                job.count = snapshot.count
                job.revenue = snapshot.revenue
                job.events = snapshot.events
                job.progress = min(1.0, index / total_frames) if total_frames else 0.0
                if ok:
                    job.frame = jpeg.tobytes()
                    job.frame_seq += 1
                job.changed.notify_all()
        with job.changed:
            job.status = "done"
            job.message = "Analisis selesai"
            job.progress = 1.0
            job.changed.notify_all()
    except Exception as exc:
        with job.changed:
            job.status = "error"
            job.message = f"Analisis gagal: {exc}"
            job.changed.notify_all()


@app.post("/api/jobs")
async def create_job(
    video: UploadFile | None = File(None),
    library_name: str = Form(""),
    line: float = Form(0.60),
    direction: str = Form("up"),
    count_mode: str = Form("line"),
    model: str = Form("yolo11n.pt"),
    use_laya: bool = Form(True),
    threshold: float = Form(0.65),
    motorcycle: int = Form(15000),
    small: int = Form(30000),
    medium: int = Form(40000),
    large: int = Form(50000),
    commercial: int = Form(65000),
):
    filename = library_name or (video.filename if video else "")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_VIDEO or (not library_name and video is None):
        raise HTTPException(400, "Format video harus MP4, MOV, AVI, atau MKV")
    if not 0.05 <= line <= 0.95 or direction not in {"up", "down"} or count_mode not in {"line", "presence"}:
        raise HTTPException(400, "Pengaturan garis tidak valid")
    if model not in {"yolo11n.pt", "yolo11s.pt"} or not 0 <= threshold <= 1:
        raise HTTPException(400, "Pengaturan model tidak valid")
    tariffs = dict(zip(DEFAULT_TARIFFS, [motorcycle, small, medium, large, commercial]))
    if any(price < 0 or price > 100_000_000 for price in tariffs.values()):
        raise HTTPException(400, "Tarif tidak valid")

    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(filename).stem)[:32] or "video"
    job_id = uuid.uuid4().hex[:12]
    folder = OUTPUTS / f"{datetime.now():%Y%m%d_%H%M%S}_{safe_name}_{job_id}"
    folder.mkdir(parents=True, exist_ok=True)
    if library_name:
        source = _library_path(library_name)
    else:
        source = folder / f"source{suffix}"
        with source.open("wb") as target:
            while chunk := await video.read(1024 * 1024):
                target.write(chunk)
        await video.close()
    job = Job(job_id, folder)
    with jobs_lock:
        jobs[job_id] = job
    threading.Thread(target=_run, args=(job, source, model, line, direction, count_mode,
                                        tariffs, use_laya, threshold), daemon=True).start()
    return {"id": job_id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    return _get_job(job_id).payload()


@app.get("/api/jobs/{job_id}/stream")
def job_stream(job_id: str):
    job = _get_job(job_id)

    def frames():
        seen = 0
        while True:
            with job.changed:
                job.changed.wait_for(lambda: job.frame_seq != seen or job.status in {"done", "error"}, timeout=2)
                data = job.frame
                current = job.frame_seq
                finished = job.status in {"done", "error"}
            if data is not None and current != seen:
                seen = current
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n"
            if finished:
                break

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/jobs/{job_id}/download/{filename}")
def download(job_id: str, filename: str):
    job = _get_job(job_id)
    if filename not in ALLOWED_FILES or job.status != "done":
        raise HTTPException(404, "File belum tersedia")
    path = job.folder / filename
    if not path.exists():
        raise HTTPException(404, "File tidak ditemukan")
    return FileResponse(path, filename=filename)
