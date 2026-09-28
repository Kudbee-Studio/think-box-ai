"""Tests for centralized error handling module."""

import unittest
from thinkbox.error_handling import (
    ErrorSeverity,
    ErrorRecoveryStrategy,
    ErrorContext,
    ThinkBoxError,
    ModelCallError,
    MemoryError,
    GovernanceError,
    NetworkError,
    ValidationError,
    with_recovery,
)


class TestErrorContext(unittest.TestCase):
    """Test ErrorContext data class."""

    def test_error_context_creation(self):
        """ErrorContext initializes with proper defaults."""
        ctx = ErrorContext(
            error_type="TestError",
            message="Test message",
            severity=ErrorSeverity.ERROR,
            recovery_strategy=ErrorRecoveryStrategy.FAIL_CLOSED,
            agent_id="agent-001",
            task_id="task-001",
        )

        self.assertEqual(ctx.error_type, "TestError")
        self.assertEqual(ctx.message, "Test message")
        self.assertEqual(ctx.severity, ErrorSeverity.ERROR)
        self.assertIsNotNone(ctx.timestamp)

    def test_error_context_to_dict(self):
        """ErrorContext converts to JSON-serializable dict."""
        ctx = ErrorContext(
            error_type="TestError",
            message="Test",
            severity=ErrorSeverity.WARNING,
            recovery_strategy=ErrorRecoveryStrategy.RETRY,
        )

        data = ctx.to_dict()
        self.assertEqual(data["error_type"], "TestError")
        self.assertEqual(data["severity"], "warning")
        self.assertEqual(data["recovery_strategy"], "retry")
        self.assertIn("timestamp", data)

    def test_error_context_to_json(self):
        """ErrorContext converts to JSON string."""
        ctx = ErrorContext(
            error_type="TestError",
            message="Test",
            severity=ErrorSeverity.ERROR,
            recovery_strategy=ErrorRecoveryStrategy.FAIL_CLOSED,
        )

        json_str = ctx.to_json()
        self.assertIn("TestError", json_str)
        self.assertIn("error", json_str)


class TestThinkBoxError(unittest.TestCase):
    """Test base ThinkBoxError class."""

    def test_thinkbox_error_creation(self):
        """ThinkBoxError initializes properly."""
        error = ThinkBoxError(
            "Test error",
            severity=ErrorSeverity.ERROR,
            recovery_strategy=ErrorRecoveryStrategy.FAIL_CLOSED,
            agent_id="agent-001",
        )

        self.assertEqual(error.message, "Test error")
        self.assertEqual(error.severity, ErrorSeverity.ERROR)
        self.assertEqual(error.agent_id, "agent-001")
        self.assertIsNotNone(error.timestamp)

    def test_thinkbox_error_to_context(self):
        """ThinkBoxError converts to ErrorContext."""
        error = ThinkBoxError(
            "Test",
            severity=ErrorSeverity.WARNING,
            recovery_strategy=ErrorRecoveryStrategy.RETRY,
        )

        ctx = error.to_context()
        self.assertEqual(ctx.error_type, "ThinkBoxError")
        self.assertEqual(ctx.message, "Test")
        self.assertEqual(ctx.severity, ErrorSeverity.WARNING)


class TestModelCallError(unittest.TestCase):
    """Test ModelCallError class."""

    def test_model_call_error_retryable(self):
        """ModelCallError handles retryable flag."""
        error = ModelCallError(
            "Model failed",
            provider="openai",
            model="gpt-4",
            retryable=True,
        )

        self.assertTrue(error.retryable)
        self.assertEqual(error.provider, "openai")
        self.assertEqual(error.recovery_strategy, ErrorRecoveryStrategy.RETRY)

    def test_model_call_error_not_retryable(self):
        """ModelCallError marks non-retryable failures."""
        error = ModelCallError(
            "Authentication failed",
            provider="openai",
            model="gpt-4",
            retryable=False,
        )

        self.assertFalse(error.retryable)
        self.assertEqual(error.recovery_strategy, ErrorRecoveryStrategy.FAIL_CLOSED)


class TestMemoryError(unittest.TestCase):
    """Test MemoryError class."""

    def test_memory_error_defaults(self):
        """MemoryError uses appropriate defaults."""
        error = MemoryError("Memory write failed")

        self.assertEqual(error.severity, ErrorSeverity.WARNING)
        self.assertEqual(error.recovery_strategy, ErrorRecoveryStrategy.RETRY)


class TestGovernanceError(unittest.TestCase):
    """Test GovernanceError class."""

    def test_governance_error_escalates(self):
        """GovernanceError escalates by default."""
        error = GovernanceError(
            "Admission denied",
            reason="insufficient_permissions",
        )

        self.assertEqual(error.severity, ErrorSeverity.WARNING)
        self.assertEqual(error.recovery_strategy, ErrorRecoveryStrategy.ESCALATE)
        self.assertEqual(error.reason, "insufficient_permissions")


class TestNetworkError(unittest.TestCase):
    """Test NetworkError class."""

    def test_network_error_retryable(self):
        """NetworkError is retryable by default."""
        error = NetworkError("Connection timeout")

        self.assertTrue(error.retryable)
        self.assertEqual(error.recovery_strategy, ErrorRecoveryStrategy.RETRY)

    def test_network_error_not_retryable(self):
        """NetworkError can be marked non-retryable."""
        error = NetworkError("Invalid URL", retryable=False)

        self.assertFalse(error.retryable)
        self.assertEqual(error.recovery_strategy, ErrorRecoveryStrategy.FAIL_CLOSED)


class TestValidationError(unittest.TestCase):
    """Test ValidationError class."""

    def test_validation_error_with_field(self):
        """ValidationError tracks field information."""
        error = ValidationError("Invalid value", field="agent_id")

        self.assertEqual(error.field, "agent_id")
        self.assertEqual(error.recovery_strategy, ErrorRecoveryStrategy.FAIL_CLOSED)


class TestRecoveryDecorator(unittest.TestCase):
    """Test with_recovery decorator."""

    def test_retry_strategy_sync(self):
        """Retry strategy retries on failure (sync)."""
        call_count = 0

        @with_recovery(
            strategy=ErrorRecoveryStrategy.RETRY,
            max_retries=3,
        )
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ThinkBoxError("Temporary failure", severity=ErrorSeverity.WARNING)
            return "success"

        result = failing_function()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)

    def test_fallback_strategy_sync(self):
        """Fallback strategy returns fallback value (sync)."""

        @with_recovery(
            strategy=ErrorRecoveryStrategy.FALLBACK,
            fallback="fallback_value",
        )
        def failing_function():
            raise ThinkBoxError("Error")

        result = failing_function()
        self.assertEqual(result, "fallback_value")

    def test_fail_closed_strategy_sync(self):
        """Fail-closed strategy raises exception (sync)."""

        @with_recovery(strategy=ErrorRecoveryStrategy.FAIL_CLOSED)
        def failing_function():
            raise ThinkBoxError("Error")

        with self.assertRaises(ThinkBoxError):
            failing_function()


if __name__ == "__main__":
    unittest.main()
