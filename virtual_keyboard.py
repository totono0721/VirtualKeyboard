"""Virtual keyboard overlay for Windows."""
from __future__ import annotations

import sys

if sys.platform != "win32":
    raise SystemExit("This application must be run on Windows.")

from vk_app import main as run_main  # noqa: E402  (import after platform guard)


if __name__ == "__main__":
    raise SystemExit(run_main())
