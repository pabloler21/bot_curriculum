# backend/adapter/logger.py
"""
Structured pipeline run logger.

Phase 1a: writes JSON-formatted log lines to stdout via the standard logging module.
Phase 1b: this module's interface stays identical — only the sink changes to Supabase.

Usage:
    logger = PipelineLogger(run_id="...", user_id=None)
    logger.start(cv_text_length=1200, jd_length=500, lang="en")
    logger.stage("adapting", attempt=0)
    logger.end(status=PipelineStatus.COMPLETED, retries=0, duration_ms=4200)
"""
import json
import logging
import time
from typing import Any

from backend.schemas import PipelineStatus

_log = logging.getLogger("aurea.pipeline")


class PipelineLogger:
    """Logs pipeline lifecycle events as structured JSON to stdout."""

    def __init__(self, run_id: str, user_id: str | None = None) -> None:
        self.run_id = run_id
        self.user_id = user_id
        self._wall_start = time.monotonic()

    def _emit(self, event: str, **fields: Any) -> None:
        record = {
            "event": event,
            "run_id": self.run_id,
            "user_id": self.user_id,
            "elapsed_ms": int((time.monotonic() - self._wall_start) * 1000),
            **fields,
        }
        _log.info(json.dumps(record))

    def start(self, cv_text_length: int, jd_length: int, lang: str) -> None:
        self._emit(
            "pipeline_start",
            status=PipelineStatus.CREATED,
            cv_text_length=cv_text_length,
            jd_length=jd_length,
            output_language=lang,
        )

    def stage(self, stage_name: str, **extra: Any) -> None:
        self._emit(f"pipeline_stage_{stage_name}", **extra)

    def end(
        self,
        status: PipelineStatus,
        retries: int = 0,
        duration_ms: int = 0,
        error: str | None = None,
        suspicious_count: int = 0,
    ) -> None:
        self._emit(
            "pipeline_end",
            status=status,
            retries=retries,
            duration_ms=duration_ms,
            suspicious_bullets=suspicious_count,
            error=error,
        )
