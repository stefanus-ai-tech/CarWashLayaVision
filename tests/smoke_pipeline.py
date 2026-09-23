"""Manual end-to-end smoke test: python tests/smoke_pipeline.py."""

import sys
from pathlib import Path

import cv2
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from carwash.core import DEFAULT_TARIFFS
from carwash.pipeline import process_video


folder = Path("outputs/smoke")
folder.mkdir(parents=True, exist_ok=True)
source = folder / "source.mp4"
writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 5, (320, 240))
assert writer.isOpened()
for _ in range(3):
    writer.write(np.zeros((240, 320, 3), dtype=np.uint8))
writer.release()

snapshots = list(process_video(source, folder, "yolo11n.pt", 0.6, "up",
                               DEFAULT_TARIFFS, None, 0.65))
assert len(snapshots) == 3
assert (folder / "annotated.mp4").stat().st_size > 0
assert (folder / "events.csv").exists()
assert (folder / "summary.json").exists()
print("Smoke test OK")


class FakeBoxes:
    def __init__(self, y):
        self.id = torch.tensor([7])
        self.xyxy = torch.tensor([[80, y - 25, 180, y + 25]])
        self.conf = torch.tensor([0.9])


class FakeResult:
    def __init__(self, y):
        self.boxes = FakeBoxes(y)


class FakeModel:
    def __init__(self):
        self.y_values = iter([180, 120, 100])

    def track(self, *_args, **_kwargs):
        return [FakeResult(next(self.y_values))]


event_folder = folder / "crossing"
event_folder.mkdir(exist_ok=True)
crossings = list(process_video(source, event_folder, "unused.pt", 0.6, "up",
                               DEFAULT_TARIFFS, None, 0.65, FakeModel()))
assert [snapshot.count for snapshot in crossings] == [0, 1, 1]
assert crossings[-1].revenue == 0
assert crossings[-1].events[0]["track_id"] == 7
assert crossings[-1].events[0]["tariff_class"] == "REVIEW"
print("Crossing event test OK")

presence_folder = folder / "presence"
presence_folder.mkdir(exist_ok=True)
visible = list(process_video(source, presence_folder, "unused.pt", 0.6, "up",
                             DEFAULT_TARIFFS, None, 0.65, FakeModel(), count_mode="presence"))
assert [snapshot.count for snapshot in visible] == [0, 0, 1]
print("Presence event test OK")
