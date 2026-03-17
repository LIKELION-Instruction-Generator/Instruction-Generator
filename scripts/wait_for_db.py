from __future__ import annotations

import sys
import time

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from stt_quiz_service.config import load_settings
from stt_quiz_service.storage.db import build_engine


def main() -> int:
    settings = load_settings()
    timeout_seconds = 60
    deadline = time.time() + timeout_seconds
    last_error: str | None = None

    while time.time() < deadline:
        engine = build_engine(settings.database_url)
        try:
            with engine.connect() as conn:
                conn.execute(text("select 1"))
            print(f"database ready: {settings.database_url}")
            return 0
        except OperationalError as exc:
            last_error = str(exc).splitlines()[0]
            time.sleep(2)
        finally:
            engine.dispose()

    print(f"database not ready after {timeout_seconds}s: {last_error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
