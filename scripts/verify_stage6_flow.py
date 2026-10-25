from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="在临时数据库中验证从管理员初始化到综合报告的完整业务流程")
    parser.add_argument("video", type=Path, help="已获授权且可用于验收的 MP4")
    args = parser.parse_args()
    if not args.video.is_file():
        raise SystemExit(f"视频不存在：{args.video}")

    with tempfile.TemporaryDirectory(prefix="autism-stage6-flow-") as temp_dir:
        os.environ["APP_DATA_DIR"] = str(Path(temp_dir) / "data")
        os.environ["APP_ENV"] = "stage6-acceptance"
        from fastapi.testclient import TestClient
        from backend.app.core.database import engine
        from backend.app.main import app

        with TestClient(app) as client:
            initialized = client.post("/api/auth/initialize", json={
                "username": "acceptance_admin", "password": "Secure123", "confirm_password": "Secure123",
            })
            assert initialized.status_code == 201, initialized.text
            child_response = client.post("/api/children", json={
                "nickname": "最终验收临时档案", "birth_month": "2021-06", "gender": "未说明",
            })
            assert child_response.status_code == 201, child_response.text
            child = child_response.json()

            with args.video.open("rb") as stream:
                upload = client.post("/api/video-analyses", data={
                    "child_id": child["id"], "consent_confirmed": "true",
                }, files={"file": (args.video.name, stream, "video/mp4")})
            assert upload.status_code == 202, upload.text
            task_id = upload.json()["id"]
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                task = client.get(f"/api/video-analyses/{task_id}").json()
                if task["status"] in ("COMPLETED", "FAILED", "INTERRUPTED"):
                    break
                time.sleep(0.2)
            assert task["status"] == "COMPLETED", task.get("error_message")
            result = client.get(f"/api/video-analyses/{task_id}/result")
            assert result.status_code == 200

            observation = client.post("/api/observations", json={
                "child_id": child["id"], "video_analysis_id": task_id,
                "observation_date": date.today().isoformat(), "observation_scene": "游戏活动", "observer_role": "家长",
                "observation_data": {"initiates_interaction": "SOMETIMES", "responds_to_name": "UNABLE_TO_JUDGE"},
                "summary_notes": "最终验收临时记录，不保留到正式数据库。",
            })
            assert observation.status_code == 201, observation.text
            activity = client.get("/api/activities", params={"page_size": 1}).json()["items"][0]
            activity_record = client.post("/api/activity-records", json={
                "child_id": child["id"], "activity_id": activity["id"], "activity_date": date.today().isoformat(),
                "completion_status": "PARTIAL", "actual_duration_minutes": 5,
                "child_response": "验收流程记录。", "notes": None,
            })
            assert activity_record.status_code == 201, activity_record.text

            overview = client.get(f"/api/children/{child['id']}/overview")
            timeline = client.get(f"/api/children/{child['id']}/timeline", params={"page_size": 100})
            report = client.get(f"/api/children/{child['id']}/report")
            assert overview.status_code == timeline.status_code == report.status_code == 200
            assert overview.json()["counts"] == {"video": 1, "observation": 1, "activity": 1}
            assert timeline.json()["total"] == 3
            assert report.json()["counts"] == {"video": 1, "observation": 1, "activity": 1}
            report_text = json.dumps(report.json(), ensure_ascii=False)
            assert "自闭症风险评分" not in report_text and "康复指数" not in report_text

            assert client.post("/api/auth/logout").status_code == 200
            assert client.get(f"/api/children/{child['id']}/report").status_code == 401
            print(json.dumps({
                "status": "passed", "video_task": task_id, "timeline_total": timeline.json()["total"],
                "report_counts": report.json()["counts"], "temporary_data_cleaned": True,
            }, ensure_ascii=False, indent=2))
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
