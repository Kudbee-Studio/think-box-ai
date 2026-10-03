"""@evaluated_once: a gate runs once per outermost call, and nothing outlives that call."""

from __future__ import annotations

import os
import threading
import types
import unittest
from unittest import mock

from thinkbox.kilo_eval_scope import evaluated_once


class TestEvaluatedOnce(unittest.TestCase):
    def test_nested_calls_with_the_same_arguments_run_once(self) -> None:
        calls: list[int] = []

        @evaluated_once
        def leaf(x: int) -> dict[str, int]:
            calls.append(x)
            return {"x": x}

        @evaluated_once
        def top() -> list[dict[str, int]]:
            return [leaf(1), leaf(1), leaf(2), leaf(1)]

        self.assertEqual(top(), [{"x": 1}, {"x": 1}, {"x": 2}, {"x": 1}])
        self.assertEqual(calls, [1, 2])

    def test_each_outermost_call_evaluates_afresh(self) -> None:
        # No cache survives a call: a test that edits a file or patches a module between two calls sees the change.
        state = {"n": 0}

        @evaluated_once
        def gate() -> int:
            state["n"] += 1
            return state["n"]

        self.assertEqual([gate(), gate(), gate()], [1, 2, 3])

    def test_the_scope_ends_when_the_outermost_call_raises(self) -> None:
        calls: list[str] = []

        @evaluated_once
        def leaf() -> str:
            calls.append("leaf")
            return "ok"

        @evaluated_once
        def top() -> None:
            leaf()
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            top()
        leaf()
        self.assertEqual(calls, ["leaf", "leaf"], "a stale scope would have answered the second leaf() from the cache")

    def test_an_exception_is_not_cached(self) -> None:
        calls: list[int] = []

        @evaluated_once
        def flaky() -> int:
            calls.append(1)
            raise ValueError("no")

        @evaluated_once
        def top() -> int:
            for _ in range(2):
                with self.assertRaises(ValueError):
                    flaky()
            return 0

        top()
        self.assertEqual(len(calls), 2)

    def test_arguments_are_part_of_the_key(self) -> None:
        calls: list[object] = []

        @evaluated_once
        def leaf(environ: dict[str, str] | None = None, *, flag: bool = False) -> int:
            calls.append((environ and dict(environ), flag))
            return len(calls)

        @evaluated_once
        def top() -> list[int]:
            return [leaf({"A": "1"}), leaf({"A": "1"}), leaf({"A": "2"}), leaf({"A": "1"}, flag=True), leaf(None), leaf(None)]

        self.assertEqual(top(), [1, 1, 2, 3, 4, 4])

    def test_the_whole_environment_is_part_of_the_key(self) -> None:
        # Helpers such as spine_fast_mode_enabled() read os.environ directly, not through an `environ` argument.
        seen: list[str | None] = []

        @evaluated_once
        def leaf() -> str | None:
            seen.append(os.environ.get("KILO_SPINE_FAST"))
            return seen[-1]

        @evaluated_once
        def top() -> list[str | None]:
            first = leaf()
            with mock.patch.dict(os.environ, {"KILO_SPINE_FAST": "1"}):
                second = leaf()
                third = leaf()
            return [first, second, third, leaf()]

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("KILO_SPINE_FAST", None)
            self.assertEqual(top(), [None, "1", "1", None])
        self.assertEqual(seen, [None, "1"], "the environment changed between nested calls, the same inputs did not")

    def test_a_caller_cannot_change_what_later_callers_receive(self) -> None:
        @evaluated_once
        def leaf() -> dict[str, list[int]]:
            return {"items": [1, 2]}

        @evaluated_once
        def top() -> list[dict[str, list[int]]]:
            first = leaf()  # the evaluation itself
            first["items"].append(99)
            second = leaf()  # answered from the cache
            second["items"].append(7)
            second["extra"] = []  # type: ignore[assignment]
            return [first, second, leaf(), leaf()]

        first, second, third, fourth = top()
        self.assertEqual(first, {"items": [1, 2, 99]})
        self.assertEqual(second, {"items": [1, 2, 7], "extra": []})
        self.assertEqual(third, {"items": [1, 2]})
        self.assertEqual(fourth, {"items": [1, 2]})

    def test_unkeyable_arguments_are_evaluated_directly(self) -> None:
        calls: list[int] = []

        @evaluated_once
        def leaf(obj: object) -> int:
            calls.append(1)
            return len(calls)

        @evaluated_once
        def top() -> list[int]:
            token = object()
            return [leaf(token), leaf(token)]

        self.assertEqual(top(), [1, 2])

    def test_an_uncopyable_result_is_returned_but_never_shared(self) -> None:
        calls: list[int] = []

        @evaluated_once
        def leaf() -> types.MappingProxyType[str, int]:
            calls.append(1)
            return types.MappingProxyType({"n": len(calls)})

        @evaluated_once
        def top() -> list[int]:
            return [leaf()["n"], leaf()["n"]]

        self.assertEqual(top(), [1, 2])

    def test_threads_do_not_share_a_scope(self) -> None:
        calls: list[str] = []
        barrier = threading.Barrier(2)

        @evaluated_once
        def leaf() -> str:
            calls.append(threading.current_thread().name)
            return "ok"

        @evaluated_once
        def top() -> None:
            leaf()
            barrier.wait(timeout=10)  # both threads are inside their scope at once
            leaf()

        threads = [threading.Thread(target=top, name=f"t{i}") for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(calls), ["t0", "t1"])

    def test_the_wrapper_keeps_the_name_and_docstring(self) -> None:
        @evaluated_once
        def evaluate_x() -> None:
            """Doc."""

        self.assertEqual(evaluate_x.__name__, "evaluate_x")
        self.assertEqual(evaluate_x.__doc__, "Doc.")


if __name__ == "__main__":
    unittest.main()
