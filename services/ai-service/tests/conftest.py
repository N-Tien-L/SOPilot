"""Shared pytest configuration (fakes live in ``fakes.py``)."""
from __future__ import annotations

import asyncio
import sys

if sys.platform == "win32":
    # psycopg's async driver needs a selector loop; Windows defaults to Proactor.
    def pytest_asyncio_loop_factories(config, item):  # noqa: ANN001, ANN201 - pytest hook
        return {"selector": asyncio.SelectorEventLoop}
