import contextlib

class _RaisesContext:
    def __init__(self, expected_exception, match=None):
        self.expected = expected_exception
        self.match = match
        self.exception = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            raise AssertionError(f"{self.expected.__name__} not raised")
        if not issubclass(exc_type, self.expected):
            raise AssertionError(f"Expected {self.expected.__name__}, got {exc_type.__name__}")
        if self.match:
            import re
            if not re.search(self.match, str(exc)):
                raise AssertionError(f"Exception message {exc!r} does not match {self.match!r}")
        self.exception = exc
        return True

def raises(expected_exception, match=None):
    return _RaisesContext(expected_exception, match)
