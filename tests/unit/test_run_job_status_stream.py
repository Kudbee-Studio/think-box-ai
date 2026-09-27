"""Unit tests for backend run job status SSE (PR #137)."""

from __future__ import annotations

import asyncio
import unittest

from thinkbox.dashboard_state import ThinkJobEntry, get_dashboard_state
from thinkbox.think_job_stream import ThinkJobStreamLimits, reset_think_job_stream_hub_for_tests

from backend.api.v1.run_job_status_stream import (
    clamp_stream_query_params,
    iter_think_job_status_stream,
)


class TestRunJobStatusStream(unittest.TestCase):
    def setUp(self) -> None:
        reset_think_job_stream_hub_for_tests()
        dash = get_dashboard_state()
        dash.think_jobs.clear()

    def test_clamp_stream_params(self) -> None:
        limits = clamp_stream_query_params(9999, 9999.0, 9999.0)
        self.assertLessEqual(limits.max_events, 64)
        self.assertLessEqual(limits.idle_timeout_s, 120.0)

    def test_stream_emits_hello_and_close_for_terminal_job(self) -> None:
        dash = get_dashboard_state()
        dash.upsert_think_job(
            ThinkJobEntry(
                job_id="engine_stream01",
                goal="done",
                status="completed",
                engine_id="engine_stream01",
                phase="completed",
                receipt_id="rcpt_1",
                experiment_id="tb_exp_1",
                session_id="tb_sess_1",
            )
        )

        async def _collect() -> str:
            chunks: list[str] = []
            limits = ThinkJobStreamLimits(max_events=8, idle_timeout_s=5.0, heartbeat_interval_s=60.0)
            async for frame in iter_think_job_status_stream("engine_stream01", limits=limits):
                chunks.append(frame)
                if "think_job_stream_close" in frame:
                    break
            return "".join(chunks)

        body = asyncio.run(_collect())
        self.assertIn("think_job_stream_hello", body)
        self.assertIn("think_job_stream_close", body)
        self.assertNotIn("governance_token", body)

    def test_stream_status_delta_on_job_update(self) -> None:
        dash = get_dashboard_state()
        dash.upsert_think_job(
            ThinkJobEntry(
                job_id="engine_stream02",
                goal="run",
                status="running",
                engine_id="engine_stream02",
                phase="started",
                tasks_total=2,
                tasks_completed=0,
            )
        )

        async def _collect() -> str:
            chunks: list[str] = []
            limits = ThinkJobStreamLimits(max_events=12, idle_timeout_s=3.0, heartbeat_interval_s=60.0)

            async def _reader() -> None:
                async for frame in iter_think_job_status_stream("engine_stream02", limits=limits):
                    chunks.append(frame)
                    if "think_job_status_delta" in frame and '"completed"' in frame:
                        break

            task = asyncio.create_task(_reader())
            await asyncio.sleep(0.05)
            entry = dash.think_jobs["engine_stream02"]
            entry.status = "completed"
            entry.phase = "completed"
            entry.tasks_completed = 2
            dash.upsert_think_job(entry)
            await asyncio.wait_for(task, timeout=2.0)
            return "".join(chunks)

        body = asyncio.run(_collect())
        self.assertIn("think_job_status_delta", body)


if __name__ == "__main__":
    unittest.main()
