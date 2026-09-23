from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .core import tariff_class


QUESTIONS = {
    "body_type": {
        "type": "choice",
        "instructions": "What is the body type of this single vehicle?",
        "criteria": ["motorcycle", "hatchback", "sedan", "MPV", "SUV", "pickup", "van", "other"],
    },
    "size": {
        "type": "choice",
        "instructions": "For car wash pricing, is this vehicle small, medium or large? Judge the actual vehicle, not its size in the picture.",
        "criteria": ["small", "medium", "large"],
    },
    "commercial": {
        "type": "noul",
        "instructions": "Is this a pickup truck, cargo van, or commercial vehicle?",
    },
}


@dataclass
class Classification:
    body_type: str
    size: str
    tariff_class: str
    confidence: float
    status: str


class LayaClassifier:
    def __init__(self):
        try:
            import laya
        except ImportError as exc:
            raise RuntimeError("Laya Vision belum terpasang. Lihat README untuk instalasi.") from exc
        local_model = Path(__file__).resolve().parents[1] / "models" / "laya-vision"
        model = str(local_model) if (local_model / "model.safetensors").is_file() else "thaitea/laya-vision"
        self.agent = laya.load_vlm(model)

    def classify(self, crop_bgr, threshold: float) -> Classification:
        import cv2
        from PIL import Image

        image = Image.fromarray(cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB))
        answers = self.agent.predict({"image": image}, QUESTIONS)["answers"]
        body = answers["body_type"]["choice"]
        size = answers["size"]["choice"]
        body_p = float(answers["body_type"]["probabilities"][body])
        size_p = float(answers["size"]["probabilities"][size])
        commercial_p = float(answers["commercial"]["noul"])
        commercial = commercial_p >= 0.5
        klass = tariff_class(body, size, commercial)
        if klass == "MOTORCYCLE":
            choice_confidence = body_p
        elif klass == "COMMERCIAL":
            choice_confidence = max(body_p if body.lower() in {"pickup", "van"} else 0.0,
                                    commercial_p)
        else:
            choice_confidence = min(body_p, size_p, 1.0 - commercial_p)
        if choice_confidence < threshold or klass == "REVIEW":
            return Classification(body, size, "REVIEW", choice_confidence, "Perlu cek manual")
        return Classification(body, size, klass, choice_confidence, "Otomatis")
