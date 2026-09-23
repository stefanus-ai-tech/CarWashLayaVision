"""Process the shortest provided clip through the local library API."""

import time
import sys

import httpx


base = "http://127.0.0.1:8501"
filename = sys.argv[1] if len(sys.argv) > 1 else "7.mp4"
response = httpx.post(base + "/api/jobs", data={"library_name": filename,
                      "count_mode": "presence", "use_laya": "false"}, timeout=30)
response.raise_for_status()
job_id = response.json()["id"]
for _ in range(300):
    state = httpx.get(f"{base}/api/jobs/{job_id}", timeout=10).json()
    if state["status"] in {"done", "error"}:
        break
    time.sleep(1)
assert state["status"] == "done", state
assert state["width"] > 0 and state["height"] > 0
assert state["progress"] == 1
print(f"Local clip OK: {state['count']} vehicle(s), {state['event_count']} event(s)")
