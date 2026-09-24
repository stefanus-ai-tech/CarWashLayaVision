"""Process the shortest provided clip through the local library API."""

import time
import sys

import httpx


base = "http://127.0.0.1:8501"
filename = sys.argv[1] if len(sys.argv) > 1 else "7.mp4"
laya_enabled = "--laya" in sys.argv
response = httpx.post(base + "/api/jobs", data={"library_name": filename,
                      "count_mode": "presence", "use_laya": str(laya_enabled).lower()}, timeout=30)
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
if laya_enabled:
    assert not state["warning"], state["warning"]
    assert all(not event["status"].startswith("Klasifikasi gagal") for event in state["events"])
    assert isinstance(state["events"][0]["tariff"], int), state["events"][0]
    event_id = state["events"][0]["event_id"]
    changed = httpx.patch(f"{base}/api/jobs/{job_id}/events/{event_id}",
                          json={"tariff_class": "MEDIUM"}, timeout=10)
    changed.raise_for_status()
    assert changed.json()["event"]["tariff"] == 40000
    assert httpx.get(f"{base}/api/jobs/{job_id}", timeout=10).json()["revenue"] == 40000
print(f"Local clip OK: {state['count']} vehicle(s), {state['event_count']} event(s)")
