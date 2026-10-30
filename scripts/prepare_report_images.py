"""Crop live Gradio screenshots to readable report evidence panels."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCREENSHOTS = ROOT / "report" / "screenshots"

CROPS = {
    "conversation_1_rag.png": (25, 340, 865, 940),
    "conversation_2_booking.png": (25, 0, 865, 910),
    "conversation_3_missing.png": (25, 340, 865, 940),
    "saved_data_evidence.png": (25, 0, 865, 930),
}


def main() -> None:
    for source_name, box in CROPS.items():
        source = SCREENSHOTS / source_name
        target = SCREENSHOTS / source_name.replace(".png", "_report.png")
        with Image.open(source) as image:
            image.crop(box).save(target, optimize=True)
        print(target)


if __name__ == "__main__":
    main()
