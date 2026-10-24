from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core.config import ensure_runtime_dirs, settings
from backend.app.services.model_manager import FACE_MODEL_URL, MIN_MODEL_BYTES, POSE_MODEL_URL, model_status


def download(url: str, destination: Path) -> None:
    partial = destination.with_suffix(destination.suffix + ".part")
    digest = hashlib.sha256()
    total = 0
    print(f"下载 {destination.name} ...")
    try:
        with urllib.request.urlopen(url, timeout=60) as response, partial.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                digest.update(chunk)
                total += len(chunk)
        if total < MIN_MODEL_BYTES:
            raise RuntimeError(f"下载文件异常，仅 {total} 字节")
        partial.replace(destination)
        destination.with_suffix(destination.suffix + ".sha256").write_text(
            f"{digest.hexdigest()}  {destination.name}\n", encoding="utf-8"
        )
        print(f"完成：{destination.name}（{total / 1024 / 1024:.1f} MB，SHA-256 {digest.hexdigest()}）")
    finally:
        if partial.exists():
            partial.unlink()


def main() -> int:
    ensure_runtime_dirs()
    for url, path in ((POSE_MODEL_URL, settings.pose_model_path), (FACE_MODEL_URL, settings.face_model_path)):
        if path.is_file() and path.stat().st_size >= MIN_MODEL_BYTES:
            print(f"已存在：{path.name}，跳过下载")
        else:
            download(url, path)
    status = model_status(validate_load=True)
    if not status["ready"]:
        print(status["error"], file=sys.stderr)
        return 1
    print(f"真实加载验证通过：MediaPipe {status['mediapipe_version']} / CPU / VIDEO mode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
