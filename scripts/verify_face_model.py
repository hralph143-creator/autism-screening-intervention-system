from __future__ import annotations

import argparse
import sys
from contextlib import ExitStack
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services.model_manager import create_landmarkers


def main() -> int:
    parser = argparse.ArgumentParser(description="用真实人像帧验证 VIDEO 模式 Face Landmarker")
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    frame = cv2.imread(str(args.image))
    if frame is None:
        raise SystemExit(f"无法读取图片：{args.image}")
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
    with ExitStack() as stack:
        _pose, face = create_landmarkers(stack)
        result = face.detect_for_video(image, 0)
    if not result.face_landmarks:
        raise SystemExit("真实 Face Landmarker 未检测到面部")
    counts = [len(landmarks) for landmarks in result.face_landmarks]
    print(f"Face Landmarker VIDEO 模式验证通过：检测到 {len(counts)} 张面部，关键点数 {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
