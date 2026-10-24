from pathlib import Path
import shutil

from ..core.config import settings
from ..models.video_analysis import VideoAnalysis


def remove_analysis_files(record: VideoAnalysis) -> None:
    video_path = Path(record.file_path)
    if video_path.is_file() and video_path.resolve().parent == settings.upload_dir.resolve():
        video_path.unlink()
    if not record.result_dir:
        return
    target = Path(record.result_dir).resolve()
    root = settings.analysis_result_dir.resolve()
    if target != root and target.is_relative_to(root) and target.exists():
        shutil.rmtree(target)
