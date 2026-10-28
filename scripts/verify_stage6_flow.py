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
    parser.add_argument("--runs", type=int, default=1, choices=range(1, 11), metavar="1-10", help="连续执行次数")
    args = parser.parse_args()
    if not args.video.is_file():
        raise SystemExit(f"视频不存在：{args.video}")

    with tempfile.TemporaryDirectory(prefix="autism-stage6-flow-") as temp_dir:
        os.environ["APP_DATA_DIR"] = str(Path(temp_dir) / "data")
        os.environ["APP_ENV"] = "stage6-acceptance"
        print("[准备] 加载验收环境", flush=True)
        from fastapi.testclient import TestClient
        print("[准备] 加载数据库", flush=True)
        from backend.app.core.database import engine
        print("[准备] 加载应用", flush=True)
        from backend.app.main import app
        print("[准备] 启动临时应用", flush=True)

        results = []
        with TestClient(app) as client:
            print("[准备] 初始化临时管理员", flush=True)
            initialized = client.post("/api/auth/initialize", json={
                "username": "acceptance_admin", "password": "Secure123", "confirm_password": "Secure123",
            })
            assert initialized.status_code == 201, initialized.text
            scenes = ("游戏活动", "家庭日常", "学习活动", "用餐时段", "外出活动")
            roles = ("家长", "其他监护人", "教师", "专业人员", "其他观察者")
            completion_statuses = ("COMPLETED", "PARTIAL", "NOT_COMPLETED", "COMPLETED", "PARTIAL")
            activities = client.get("/api/activities", params={"page_size": 12}).json()["items"]
            assert len(activities) >= args.runs

            for run_number in range(1, args.runs + 1):
                print(f"[流程 {run_number}/{args.runs}] 开始", flush=True)
                if run_number > 1:
                    login = client.post("/api/auth/login", json={
                        "username": "acceptance_admin", "password": "Secure123",
                    })
                    assert login.status_code == 200, login.text

                child_response = client.post("/api/children", json={
                    "nickname": f"验收临时档案{run_number}",
                    "birth_month": f"202{run_number % 3}-0{run_number + 1}",
                    "gender": ("男", "女", "未说明")[(run_number - 1) % 3],
                })
                assert child_response.status_code == 201, child_response.text
                child = child_response.json()
                print(f"[流程 {run_number}/{args.runs}] 已创建档案 {child['child_code']}", flush=True)

                with args.video.open("rb") as stream:
                    upload = client.post("/api/video-analyses", data={
                        "child_id": child["id"], "consent_confirmed": "true",
                    }, files={"file": (f"flow_{run_number}_{args.video.name}", stream, "video/mp4")})
                assert upload.status_code == 202, upload.text
                task_id = upload.json()["id"]
                print(f"[流程 {run_number}/{args.runs}] 视频任务 #{task_id} 已提交", flush=True)
                deadline = time.monotonic() + 120
                last_status = None
                while time.monotonic() < deadline:
                    task_response = client.get(f"/api/video-analyses/{task_id}")
                    assert task_response.status_code == 200, task_response.text
                    task = task_response.json()
                    if task["status"] != last_status:
                        print(f"[流程 {run_number}/{args.runs}] 视频状态：{task['status']}", flush=True)
                        last_status = task["status"]
                    if task["status"] in ("COMPLETED", "FAILED", "INTERRUPTED"):
                        break
                    time.sleep(0.2)
                assert task["status"] == "COMPLETED", task.get("error_message")
                result = client.get(f"/api/video-analyses/{task_id}/result")
                assert result.status_code == 200

                observation = client.post("/api/observations", json={
                    "child_id": child["id"], "video_analysis_id": task_id,
                    "observation_date": date.today().isoformat(),
                    "observation_scene": scenes[run_number - 1], "observer_role": roles[run_number - 1],
                    "observation_data": {
                        "initiates_interaction": ("OFTEN", "SOMETIMES", "NOT_SEEN_THIS_TIME", "UNABLE_TO_JUDGE", "NOT_OBSERVED")[run_number - 1],
                        "responds_to_name": "UNABLE_TO_JUDGE",
                    },
                    "summary_notes": f"第 {run_number} 次完整流程临时记录。",
                })
                assert observation.status_code == 201, observation.text
                print(f"[流程 {run_number}/{args.runs}] 行为观察已保存", flush=True)

                activity = activities[run_number - 1]
                completion_status = completion_statuses[run_number - 1]
                activity_record = client.post("/api/activity-records", json={
                    "child_id": child["id"], "activity_id": activity["id"],
                    "activity_date": date.today().isoformat(), "completion_status": completion_status,
                    "actual_duration_minutes": None if completion_status == "NOT_COMPLETED" else 5 + run_number,
                    "child_response": f"第 {run_number} 次验收流程记录。", "notes": None,
                })
                assert activity_record.status_code == 201, activity_record.text
                print(f"[流程 {run_number}/{args.runs}] 家庭活动已保存", flush=True)

                overview = client.get(f"/api/children/{child['id']}/overview")
                timeline = client.get(f"/api/children/{child['id']}/timeline", params={"page_size": 100})
                filtered_timeline = client.get(
                    f"/api/children/{child['id']}/timeline", params={"record_type": "VIDEO", "page_size": 100}
                )
                report = client.get(f"/api/children/{child['id']}/report")
                assert overview.status_code == timeline.status_code == filtered_timeline.status_code == report.status_code == 200
                assert overview.json()["counts"] == {"video": 1, "observation": 1, "activity": 1}
                assert timeline.json()["total"] == 3
                assert filtered_timeline.json()["total"] == 1
                assert report.json()["counts"] == {"video": 1, "observation": 1, "activity": 1}
                report_text = json.dumps(report.json(), ensure_ascii=False)
                assert "自闭症风险评分" not in report_text and "康复指数" not in report_text

                assert client.post("/api/auth/logout").status_code == 200
                assert client.get(f"/api/children/{child['id']}/report").status_code == 401
                print(f"[流程 {run_number}/{args.runs}] 历史、报告与退出验证通过", flush=True)
                results.append({
                    "run": run_number, "child_code": child["child_code"], "video_task": task_id,
                    "scene": scenes[run_number - 1], "activity": activity["name"], "timeline_total": 3,
                })

            print(json.dumps({
                "status": "passed", "runs_completed": len(results), "runs": results,
                "temporary_data_cleaned": True,
            }, ensure_ascii=False, indent=2))
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
