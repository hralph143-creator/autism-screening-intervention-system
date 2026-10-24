from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services.model_manager import model_status

status = model_status(validate_load="--quick" not in sys.argv)
print(json.dumps(status, ensure_ascii=False, indent=2))
raise SystemExit(0 if status["ready"] else 1)
