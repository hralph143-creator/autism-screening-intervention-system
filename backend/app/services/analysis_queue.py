from __future__ import annotations

import json
import logging
import queue
import threading
from datetime import datetime
from pathlib import Path

from sqlalchemy import update

from ..core.config import settings
from ..core.database import SessionLocal
from ..models.video_analysis import VideoAnalysis
from .video_analyzer import analyze_video

logger = logging.getLogger(__name__)


class AnalysisQueue:
    def __init__(self) -> None:
        self._queue: queue.Queue[int | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="video-analysis-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._queue.put(None)
        if self._thread:
            self._thread.join(timeout=5)
        self._thread = None

    def enqueue(self, analysis_id: int) -> None:
        self.start()
        self._queue.put(analysis_id)

    def interrupt_stale_tasks(self) -> int:
        with SessionLocal() as db:
            result = db.execute(
                update(VideoAnalysis)
                .where(VideoAnalysis.status.in_(("PENDING", "RUNNING")))
                .values(status="INTERRUPTED", error_message="服务退出前任务尚未完成，可点击重试", updated_at=datetime.utcnow())
            )
            db.commit()
            return int(result.rowcount or 0)

    def _run(self) -> None:
        while not self._stop.is_set():
            analysis_id = self._queue.get()
            try:
                if analysis_id is None:
                    return
                self._process(analysis_id)
            except Exception:
                logger.exception("视频分析工作线程出现异常")
            finally:
                self._queue.task_done()

    def _process(self, analysis_id: int) -> None:
        with SessionLocal() as db:
            record = db.get(VideoAnalysis, analysis_id)
            if not record or record.status != "PENDING":
                return
            record.status = "RUNNING"
            record.progress = 2
            record.started_at = datetime.utcnow()
            record.completed_at = None
            record.error_message = None
            db.commit()
            video_path = Path(record.file_path)
            result_dir = settings.analysis_result_dir / str(record.id)
            metadata = {
                "source_fps": record.source_fps,
                "frame_count": max(1, round(record.duration_seconds * record.source_fps)),
            }

        def progress(value: int) -> None:
            with SessionLocal() as progress_db:
                item = progress_db.get(VideoAnalysis, analysis_id)
                if item and item.status == "RUNNING":
                    item.progress = value
                    progress_db.commit()

        try:
            result = analyze_video(video_path, result_dir, metadata, progress)
        except Exception as exc:
            logger.exception("分析任务 %s 失败", analysis_id)
            with SessionLocal() as db:
                record = db.get(VideoAnalysis, analysis_id)
                if record:
                    record.status = "FAILED"
                    record.progress = 0
                    record.error_message = f"分析失败：{type(exc).__name__}: {str(exc)[:400]}"
                    record.completed_at = datetime.utcnow()
                    db.commit()
            return
        with SessionLocal() as db:
            record = db.get(VideoAnalysis, analysis_id)
            if not record:
                return
            record.status = "COMPLETED"
            record.progress = 100
            record.result_json = json.dumps(result, ensure_ascii=False)
            record.result_dir = str(result_dir.resolve())
            record.completed_at = datetime.utcnow()
            db.commit()


analysis_queue = AnalysisQueue()
