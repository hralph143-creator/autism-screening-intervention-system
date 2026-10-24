from __future__ import annotations

import importlib.metadata
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from ..core.config import settings

POSE_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
FACE_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
MIN_MODEL_BYTES = 500_000


def create_landmarkers(stack: ExitStack | None = None) -> tuple[Any, Any]:
    """创建每个分析任务独占的 VIDEO 模式模型实例，避免跨线程共享状态。"""
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision

    for path in (settings.pose_model_path, settings.face_model_path):
        if not path.is_file() or path.stat().st_size < MIN_MODEL_BYTES:
            raise FileNotFoundError(f"模型文件缺失或不完整：{path.name}")
    # MediaPipe 的 Windows 原生层不能稳定打开含中文的文件路径；传入模型字节可保持项目路径可移植。
    pose_options = vision.PoseLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_buffer=settings.pose_model_path.read_bytes()),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=2,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    face_options = vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_buffer=settings.face_model_path.read_bytes()),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=2,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    pose = vision.PoseLandmarker.create_from_options(pose_options)
    face = vision.FaceLandmarker.create_from_options(face_options)
    if stack is not None:
        return stack.enter_context(pose), stack.enter_context(face)
    return pose, face


def model_status(validate_load: bool = True) -> dict[str, Any]:
    items: dict[str, dict[str, Any]] = {}
    for name, path, url in (
        ("pose", settings.pose_model_path, POSE_MODEL_URL),
        ("face", settings.face_model_path, FACE_MODEL_URL),
    ):
        exists = path.is_file()
        size = path.stat().st_size if exists else 0
        items[name] = {
            "filename": path.name,
            "exists": exists,
            "size_bytes": size,
            "source": url,
            "loadable": None,
        }
    error = None
    all_present = all(item["exists"] and item["size_bytes"] >= MIN_MODEL_BYTES for item in items.values())
    if validate_load and all_present:
        try:
            with ExitStack() as stack:
                create_landmarkers(stack)
            for item in items.values():
                item["loadable"] = True
        except Exception as exc:
            error = f"模型加载失败：{type(exc).__name__}: {exc}"
            for item in items.values():
                item["loadable"] = False
    elif not all_present:
        error = "模型文件尚未完整安装，请运行 scripts/download_models.py"
        for item in items.values():
            item["loadable"] = False if item["exists"] else None
    try:
        version = importlib.metadata.version("mediapipe")
    except importlib.metadata.PackageNotFoundError:
        version = None
        error = "MediaPipe 尚未安装"
    return {
        "ready": all_present and (not validate_load or not error),
        "device": "CPU",
        "mediapipe_version": version,
        "models": items,
        "error": error,
    }
