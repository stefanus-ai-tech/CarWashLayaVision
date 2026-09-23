"""Manual HTTP smoke test. Run after tests/smoke_pipeline.py and starting uvicorn."""

import time
from pathlib import Path

import httpx


base = "http://127.0.0.1:8501"
source = Path("outputs/smoke/source.mp4")
assert source.exists(), "Run tests/smoke_pipeline.py first"
with source.open("rb") as video:
    response = httpx.post(base + "/api/jobs", files={"video": ("smoke.mp4", video, "video/mp4")},
                          data={"use_laya": "false"}, timeout=30)
response.raise_for_status()
job_id = response.json()["id"]
for _ in range(90):
    state = httpx.get(f"{base}/api/jobs/{job_id}", timeout=10).json()
    if state["status"] in {"done", "error"}:
        break
    time.sleep(1)
assert state["status"] == "done", state
assert state["progress"] == 1
assert state["count"] == 0
assert set(state["downloads"]) == {"annotated.mp4", "events.csv", "summary.json"}
assert httpx.get(f"{base}/api/jobs/{job_id}/download/summary.json").status_code == 200
print("HTTP upload, processing and download OK")
