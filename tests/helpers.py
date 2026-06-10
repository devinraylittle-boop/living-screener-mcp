from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import Settings
from app.factory import create_container


class TempContainer:
    def __enter__(self):
        self.temp = TemporaryDirectory(ignore_cleanup_errors=True)
        self.container = create_container(Settings(database_path=Path(self.temp.name) / "test.sqlite3"))
        return self.container

    def __exit__(self, exc_type, exc, tb):
        self.temp.cleanup()
