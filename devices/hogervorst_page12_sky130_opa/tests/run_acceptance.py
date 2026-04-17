from __future__ import annotations

import sys
import unittest
from pathlib import Path


def main() -> int:
    tests_dir = Path(__file__).resolve().parent
    acceptance_dir = tests_dir / "acceptance"
    repo_root = tests_dir.parents[3]

    suite = unittest.defaultTestLoader.discover(
        start_dir=str(acceptance_dir),
        pattern="test*.py",
        top_level_dir=str(repo_root),
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
