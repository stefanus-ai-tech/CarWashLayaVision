"""Make a contact sheet for local camera layout inspection."""

from pathlib import Path

import cv2
import numpy as np

library = Path.home() / "Videos" / "CuciMobil"
files = sorted(library.glob("*.mp4"))
sheet = np.zeros((720, 960, 3), dtype=np.uint8)
for index, path in enumerate(files[:8]):
    capture = cv2.VideoCapture(str(path))
    capture.set(cv2.CAP_PROP_POS_FRAMES, int(capture.get(cv2.CAP_PROP_FRAME_COUNT) * 0.3))
    ok, frame = capture.read()
    capture.release()
    if not ok:
        continue
    height, width = frame.shape[:2]
    scale = min(240 / width, 360 / height)
    image = cv2.resize(frame, (int(width * scale), int(height * scale)))
    card = np.zeros((360, 240, 3), dtype=np.uint8)
    x = (240 - image.shape[1]) // 2
    y = (360 - image.shape[0]) // 2
    card[y:y + image.shape[0], x:x + image.shape[1]] = image
    cv2.putText(card, path.name, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    row, col = divmod(index, 4)
    sheet[row * 360:(row + 1) * 360, col * 240:(col + 1) * 240] = card
Path("outputs").mkdir(exist_ok=True)
cv2.imwrite("outputs/contact_sheet.jpg", sheet)
