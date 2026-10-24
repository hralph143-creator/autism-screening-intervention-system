from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services.video_analyzer import analyze_video
from backend.app.services.video_files import inspect_video


def main() -> int:
    parser = argparse.ArgumentParser(description="用真实 MediaPipe 模型验证一个本地 MP4，不写入业务数据库")
    parser.add_argument("video", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "manual_model_verification")
    args = parser.parse_args()
    metadata = inspect_video(args.video)
    result = analyze_video(args.video, args.output, metadata, lambda value: print(f"进度 {value}%"))
    print(json.dumps({"video": metadata, "summary": result["summary"], "statistics": result["motion_statistics"], "warnings": result["warnings"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
