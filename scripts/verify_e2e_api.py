from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="在临时数据库中验证真实上传、后台推理、轮询和结果接口")
    parser.add_argument("video", type=Path)
    args = parser.parse_args()
    if not args.video.is_file():
        raise SystemExit(f"视频不存在：{args.video}")
    with tempfile.TemporaryDirectory(prefix="autism-video-e2e-") as temp_dir:
        os.environ["APP_DATA_DIR"] = str(Path(temp_dir) / "data")
        os.environ["APP_ENV"] = "e2e-test"
        from fastapi.testclient import TestClient
        from backend.app.main import app
        from backend.app.core.database import engine

        with TestClient(app) as client:
            assert client.post("/api/auth/initialize", json={"username": "e2eadmin", "password": "Secure123", "confirm_password": "Secure123"}).status_code == 201
            child = client.post("/api/children", json={"nickname": "真实模型验证"}).json()
            with args.video.open("rb") as stream:
                response = client.post(
                    "/api/video-analyses",
                    data={"child_id": child["id"], "consent_confirmed": "true"},
                    files={"file": (args.video.name, stream, "video/mp4")},
                )
            assert response.status_code == 202, response.text
            task_id = response.json()["id"]
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                task = client.get(f"/api/video-analyses/{task_id}").json()
                print(f"任务 #{task_id}: {task['status']} {task['progress']}%")
                if task["status"] in ("COMPLETED", "FAILED", "INTERRUPTED"):
                    break
                time.sleep(0.2)
            assert task["status"] == "COMPLETED", task.get("error_message")
            result = client.get(f"/api/video-analyses/{task_id}/result")
            assert result.status_code == 200, result.text
            payload = result.json()["result"]
            for frame in payload["preview_frames"]:
                frame_response = client.get(f"/api/video-analyses/{task_id}/frames/{frame['filename']}")
                assert frame_response.status_code == 200
            print("端到端验证通过：", payload["summary"])
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
