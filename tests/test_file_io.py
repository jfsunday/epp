"""Tests for E++ file I/O operations."""

import os
import pytest
from epp.errors import EppRuntimeError


@pytest.fixture(autouse=True)
def cleanup_files():
    yield
    for f in ("testout",):
        if os.path.exists(f):
            os.remove(f)


class TestFileIO:
    def test_write_and_read(self, run):
        _, out = run("""
Write hello world to the file testout.
Read the file testout and store it in content.
Say the value of content.
""")
        assert out == ["hello world"]

    def test_write_variable(self, run):
        _, out = run("""
Let data be some test data.
Write the value of data to the file testout.
Read the file testout and store it in result.
Say the value of result.
""")
        assert out == ["some test data"]

    def test_read_missing_file(self, run):
        with pytest.raises(EppRuntimeError, match="not found"):
            run("""
Read the file nonexistent and store it in content.
""")
