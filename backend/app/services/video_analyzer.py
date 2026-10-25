from __future__ import annotations

import math
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Callable

import cv2
import mediapipe as mp
import numpy as np

from ..core.config import settings
from .model_manager import create_landmarkers

POSE_CONNECTIONS = (
    (0, 11), (0, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
)
POSE_REQUIRED = (0, 11, 12, 13, 14, 15, 16, 23, 24)
MIN_SHORT_VIDEO_SAMPLES = 8


def _point(landmark) -> np.ndarray:
    return np.array([float(landmark.x), float(landmark.y)], dtype=np.float64)


def _visible(landmark) -> bool:
    return float(getattr(landmark, "visibility", 1.0)) >= 0.5 and float(getattr(landmark, "presence", 1.0)) >= 0.5


def _pose_features(landmarks) -> tuple[np.ndarray, np.ndarray] | None:
    if len(landmarks) < 25 or not all(_visible(landmarks[index]) for index in POSE_REQUIRED):
        return None
    shoulders = (_point(landmarks[11]) + _point(landmarks[12])) / 2
    hips = (_point(landmarks[23]) + _point(landmarks[24])) / 2
    torso_center = (shoulders + hips) / 2
    scale = float(np.linalg.norm(shoulders - hips))
    if scale < 0.025:
        return None
    head = (_point(landmarks[0]) - torso_center) / scale
    arms = np.concatenate([(_point(landmarks[index]) - torso_center) / scale for index in (13, 14, 15, 16)])
    return head, arms


def _face_feature(landmarks) -> np.ndarray | None:
    if len(landmarks) <= 263:
        return None
    left, right = _point(landmarks[33]), _point(landmarks[263])
    scale = float(np.linalg.norm(left - right))
    if scale < 0.015:
        return None
    center = np.mean(np.array([_point(item) for item in landmarks]), axis=0)
    return np.array([center[0] / scale, center[1] / scale, scale], dtype=np.float64)


def _safe_motion(previous: np.ndarray | None, current: np.ndarray | None) -> float | None:
    if previous is None or current is None:
        return None
    value = float(np.linalg.norm(current - previous))
    return round(value, 5) if math.isfinite(value) and value <= 5 else None


def _stats(values: list[float | None]) -> dict[str, float | int | None]:
    valid = np.array([value for value in values if value is not None], dtype=np.float64)
    if not len(valid):
        return {"valid_count": 0, "mean": None, "max": None, "p95": None}
    return {
        "valid_count": int(len(valid)),
        "mean": round(float(np.mean(valid)), 5),
        "max": round(float(np.max(valid)), 5),
        "p95": round(float(np.percentile(valid, 95)), 5),
    }


def _sampling_plan(source_fps: float, frame_count: int) -> tuple[int, int, float]:
    """Keep normal videos lightweight while giving short clips enough evidence."""
    default_step = max(1, int(round(source_fps / settings.analysis_sample_fps)))
    short_video_step = max(1, frame_count // MIN_SHORT_VIDEO_SAMPLES)
    frame_step = min(default_step, short_video_step)
    sampled_total = max(1, math.ceil(frame_count / frame_step))
    effective_sample_fps = min(source_fps, source_fps / frame_step)
    return frame_step, sampled_total, effective_sample_fps


def _quality_level(pose_coverage: float, face_coverage: float) -> str:
    minimum_coverage = min(pose_coverage, face_coverage)
    if minimum_coverage >= 0.7:
        return "良好"
    if minimum_coverage >= 0.4:
        return "可用"
    if max(pose_coverage, face_coverage) >= 0.4:
        return "部分数据可用"
    return "有效数据不足"


def _draw_preview(frame: np.ndarray, poses, faces) -> np.ndarray:
    output = frame.copy()
    height, width = output.shape[:2]
    for landmarks in poses:
        for start, end in POSE_CONNECTIONS:
            if start < len(landmarks) and end < len(landmarks) and _visible(landmarks[start]) and _visible(landmarks[end]):
                p1 = (int(landmarks[start].x * width), int(landmarks[start].y * height))
                p2 = (int(landmarks[end].x * width), int(landmarks[end].y * height))
                cv2.line(output, p1, p2, (58, 197, 167), 2, cv2.LINE_AA)
        for index in POSE_REQUIRED:
            if index < len(landmarks) and _visible(landmarks[index]):
                point = (int(landmarks[index].x * width), int(landmarks[index].y * height))
                cv2.circle(output, point, 3, (245, 184, 65), -1, cv2.LINE_AA)
    for landmarks in faces:
        for landmark in landmarks[::6]:
            point = (int(landmark.x * width), int(landmark.y * height))
            cv2.circle(output, point, 1, (96, 126, 255), -1, cv2.LINE_AA)
    return output


def analyze_video(
    video_path: Path,
    result_dir: Path,
    metadata: dict,
    on_progress: Callable[[int], None] | None = None,
) -> dict:
    started = time.perf_counter()
    result_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError("后台无法重新打开视频")
    source_fps = float(metadata["source_fps"])
    frame_count = int(metadata["frame_count"])
    frame_step, sampled_total, effective_sample_fps = _sampling_plan(source_fps, frame_count)
    preview_targets = {round(index * (sampled_total - 1) / 4) for index in range(5)}
    series: list[dict] = []
    previews: list[dict] = []
    pose_frames = face_frames = multi_pose_frames = multi_face_frames = decode_failures = 0
    previous_head = previous_arms = previous_face = None
    last_timestamp = -1
    sampled_index = 0
    try:
        with ExitStack() as stack:
            pose_landmarker, face_landmarker = create_landmarkers(stack)
            frame_index = 0
            while frame_index < frame_count:
                capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                ok, frame = capture.read()
                if not ok or frame is None:
                    decode_failures += 1
                    frame_index += frame_step
                    sampled_index += 1
                    continue
                timestamp = max(last_timestamp + 1, int(round(frame_index / source_fps * 1000)))
                last_timestamp = timestamp
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
                pose_result = pose_landmarker.detect_for_video(image, timestamp)
                face_result = face_landmarker.detect_for_video(image, timestamp)
                poses = pose_result.pose_landmarks or []
                faces = face_result.face_landmarks or []
                pose_frames += bool(poses)
                face_frames += bool(faces)
                multi_pose_frames += len(poses) > 1
                multi_face_frames += len(faces) > 1
                pose_feature = _pose_features(poses[0]) if len(poses) == 1 else None
                face_feature = _face_feature(faces[0]) if len(faces) == 1 else None
                head = pose_feature[0] if pose_feature else None
                arms = pose_feature[1] if pose_feature else None
                head_motion = _safe_motion(previous_head, head)
                arm_motion = _safe_motion(previous_arms, arms)
                face_motion = _safe_motion(previous_face, face_feature)
                previous_head = head
                previous_arms = arms
                previous_face = face_feature
                series.append({
                    "timestamp_ms": timestamp,
                    "pose_detected": bool(poses),
                    "face_detected": bool(faces),
                    "head_motion": head_motion,
                    "upper_limb_motion": arm_motion,
                    "face_center_motion": face_motion,
                })
                if (sampled_index in preview_targets or len(previews) < 3) and (poses or faces) and len(previews) < 5:
                    filename = f"frame_{len(previews) + 1:02d}.jpg"
                    rendered = _draw_preview(frame, poses[:1], faces[:1])
                    cv2.imwrite(str(result_dir / filename), rendered, [cv2.IMWRITE_JPEG_QUALITY, 88])
                    previews.append({"filename": filename, "timestamp_ms": timestamp})
                sampled_index += 1
                frame_index += frame_step
                if on_progress and sampled_index % 4 == 0:
                    on_progress(min(95, max(5, int(sampled_index / sampled_total * 95))))
    finally:
        capture.release()

    sampled = len(series)
    pose_coverage = pose_frames / sampled if sampled else 0
    face_coverage = face_frames / sampled if sampled else 0
    quality_level = _quality_level(pose_coverage, face_coverage)
    warnings: list[str] = []
    if sampled == 0:
        warnings.append("未获得任何可分析帧")
    if pose_coverage < 0.4:
        warnings.append("人体姿态有效帧较少，姿态运动统计仅供质量参考")
    if face_coverage < 0.4:
        warnings.append("面部有效帧较少，面部轨迹统计仅供质量参考")
    if multi_pose_frames or multi_face_frames:
        warnings.append("部分画面存在多人或多张面孔，相关帧未合并为单人轨迹")
    if decode_failures:
        warnings.append(f"有 {decode_failures} 个采样位置无法解码并已跳过")
    head_values = [item["head_motion"] for item in series]
    arm_values = [item["upper_limb_motion"] for item in series]
    face_values = [item["face_center_motion"] for item in series]
    return {
        "engine": {
            "mediapipe_mode": "VIDEO",
            "device": "CPU",
            "sample_fps": round(effective_sample_fps, 3),
            "configured_sample_fps": settings.analysis_sample_fps,
            "adaptive_short_video_sampling": effective_sample_fps > settings.analysis_sample_fps,
        },
        "summary": {
            "sampled_frames": sampled,
            "pose_valid_frames": pose_frames,
            "face_valid_frames": face_frames,
            "pose_coverage": round(pose_coverage, 4),
            "face_coverage": round(face_coverage, 4),
            "multi_pose_frames": multi_pose_frames,
            "multi_face_frames": multi_face_frames,
            "quality_level": quality_level,
            "processing_seconds": round(time.perf_counter() - started, 3),
        },
        "motion_statistics": {
            "head_location_change": _stats(head_values),
            "upper_limb_change": _stats(arm_values),
            "face_center_change": _stats(face_values),
        },
        "time_series": series,
        "preview_frames": previews,
        "warnings": warnings,
        "calculation_notes": [
            "姿态运动量按肩部与髋部形成的躯干尺度归一化，降低远近变化影响。",
            "仅计算相邻且单人、关键点可信的采样帧；缺失值保留为空，不做跨缺失段插值。",
            "单帧归一化位移大于 5 的不可信跳变按缺失处理。",
        ],
        "disclaimer": "本结果只描述视频中的客观检测覆盖率与运动变化，不构成自闭症诊断、风险预测或医疗建议。",
    }
