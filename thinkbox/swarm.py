"""Parallel execution engine for ThinkBox AI.

Manages concurrent task execution with speculative middle-out execution.
When a task fails, instantly launches 3 speculative sub-sandboxes with
altered prompt contexts, adopting the first that succeeds.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from .model_client import AsyncModelClient, ModelConfig
from .session import get_current_session


@dataclass
class ExecutionResult:
    task_id: str
    success: bool
    exit_code: int
    output: str
    execution_time_ms: float
    tokens_used: int
    speculative: bool = False
    attempts: int = 1
    session_id: str = ""


@dataclass
class SpeculativeResult:
    parent_task_id: str
    attempts: list[ExecutionResult] = field(default_factory=list)
    winner: ExecutionResult | None = None
    session_id: str = ""


class AsyncWorkerPool:
    def __init__(
        self,
        model_client: AsyncModelClient | None = None,
        max_workers: int = 16,
        max_retries: int = 3,
    ):
        self.model_client = model_client or AsyncModelClient()
        self.max_workers = max_workers
        self.max_retries = max_retries
        self._semaphore = asyncio.Semaphore(max_workers)
        self._results: dict[str, ExecutionResult] = {}
        self._callbacks: list[Callable[[ExecutionResult], None]] = []

    @property
    def results(self) -> dict[str, ExecutionResult]:
        return self._results.copy()

    def on_result(self, callback: Callable[[ExecutionResult], None]) -> None:
        self._callbacks.append(callback)

    async def execute_task(
        self,
        task_id: str,
        prompt: str,
        **kwargs: Any,
    ) -> ExecutionResult:
        async with self._semaphore:
            start = time.monotonic()
            try:
                output = await self.model_client.generate(prompt, **kwargs)
                elapsed = (time.monotonic() - start) * 1000
                result = ExecutionResult(
                    task_id=task_id,
                    success=True,
                    exit_code=0,
                    output=output,
                    execution_time_ms=elapsed,
                    tokens_used=len(output) // 4,
                )
            except Exception as e:
                elapsed = (time.monotonic() - start) * 1000
                result = ExecutionResult(
                    task_id=task_id,
                    success=False,
                    exit_code=1,
                    output=str(e),
                    execution_time_ms=elapsed,
                    tokens_used=0,
                )

            self._results[task_id] = result
            for cb in self._callbacks:
                try:
                    if asyncio.iscoroutinefunction(cb):
                        await cb(result)
                    else:
                        cb(result)
                except Exception:
                    pass

            return result

    async def execute_with_speculation(
        self,
        task_id: str,
        prompt: str,
        **kwargs: Any,
    ) -> SpeculativeResult:
        result = await self.execute_task(task_id, prompt, **kwargs)

        if result.success:
            return SpeculativeResult(parent_task_id=task_id, attempts=[result], winner=result)

        speculative_result = SpeculativeResult(parent_task_id=task_id, attempts=[result])

        async def _speculative_attempt(attempt_id: int, modified_prompt: str) -> ExecutionResult:
            spec_id = f"{task_id}_spec_{attempt_id}"
            return await self.execute_task(spec_id, modified_prompt, **kwargs)

        modified_prompts = [
            f"{prompt}\n\nPrevious attempt failed with: {result.output}. Please fix the error and retry.",
            f"{prompt}\n\nThink step by step. The previous output was incorrect. Focus on accuracy.",
            f"{prompt}\n\nProvide a detailed, step-by-step solution. Ensure correctness.",
        ]

        tasks = [
            _speculative_attempt(i, mp)
            for i, mp in enumerate(modified_prompts)
        ]
        spec_results = await asyncio.gather(*tasks, return_exceptions=False)

        speculative_result.attempts.extend(spec_results)

        for spec in spec_results:
            if spec.success:
                speculative_result.winner = spec
                self._results[task_id] = spec
                break

        if not speculative_result.winner:
            self._results[task_id] = result

        return speculative_result

    async def execute_batch(
        self,
        tasks: list[tuple[str, str]],
        speculative: bool = False,
    ) -> list[ExecutionResult | SpeculativeResult]:
        results = []
        for task_id, prompt in tasks:
            if speculative:
                result = await self.execute_with_speculation(task_id, prompt)
            else:
                result = await self.execute_task(task_id, prompt)
            results.append(result)
        return results

    def get_stats(self) -> dict[str, Any]:
        completed = [r for r in self._results.values() if isinstance(r, ExecutionResult)]
        successful = [r for r in completed if r.success]
        total_time = sum(r.execution_time_ms for r in completed)
        total_tokens = sum(r.tokens_used for r in completed)

        return {
            "total_tasks": len(completed),
            "successful": len(successful),
            "failed": len(completed) - len(successful),
            "total_time_ms": total_time,
            "total_tokens": total_tokens,
            "avg_time_ms": total_time / len(completed) if completed else 0,
            "success_rate": len(successful) / len(completed) if completed else 0,
        }
