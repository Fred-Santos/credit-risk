"""Runner que pode exigir integração sem aceitar testes ignorados."""
import argparse
from pathlib import Path
import sys
import unittest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--integration-required", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    suite = unittest.defaultTestLoader.discover(str(root / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if args.integration_required and result.skipped:
        print("Integração obrigatória: testes ignorados impedem aprovação.", file=sys.stderr)
        return 1
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
