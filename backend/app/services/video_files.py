from __future__ import annotations

import cv2
from pathlib import Path

from ..core.config import settings


class VideoValidationError(ValueError):
    pass


def has_mp4_signature(path: Path) -> bool:
    with path.open("rb") as stream:
        header = stream.read(32)
    return len(header) >= 12 and header[4:8] == b"ftyp"


def inspect_video(path: Path) -> dict[str, float | int]:
    if not has_mp4_signature(path):
        raise VideoValidationError("文件内容不是有效的 MP4 视频")
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise VideoValidationError("无法解码该 MP4 视频")
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if not (0.1 <= fps <= 240 and frame_count > 0):
            raise VideoValidationError("视频帧率或帧数无效")
        duration = frame_count / fps
        if duration <= 0 or duration > settings.max_video_seconds + 0.05:
            raise VideoValidationError(f"视频时长不能超过 {int(settings.max_video_seconds)} 秒")
        if width < 64 or height < 64 or width > 7680 or height > 4320:
            raise VideoValidationError("视频分辨率无效或过大")
        ok, frame = capture.read()
        if not ok or frame is None or frame.size == 0:
            raise VideoValidationError("视频没有可解码的画面")
        capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_count - 1))
        tail_ok, tail = capture.read()
        if frame_count > 2 and (not tail_ok or tail is None):
            raise VideoValidationError("视频尾部损坏，无法完整解码")
        return {
            "duration_seconds": round(duration, 3),
            "width": width,
            "height": height,
            "source_fps": round(fps, 3),
            "frame_count": frame_count,
        }
    finally:
        capture.release()
