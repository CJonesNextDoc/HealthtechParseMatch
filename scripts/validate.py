#!/usr/bin/env python3
"""
Local CI validation script.

This script runs the same checks as the CI pipeline locally,
so you can validate your changes before pushing.

Usage:
    python scripts/validate.py
    python scripts/validate.py --fix  # Auto-fix issues where possible
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str, fix_mode: bool = False) -> bool:
    """Run a command and return success status."""
    print(f"\n🔍 {description}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent)

        if result.returncode == 0:
            print(f"✅ {description} passed")
            return True
        else:
            print(f"❌ {description} failed")
            if result.stdout:
                print("STDOUT:", result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
            return False
    except Exception as e:
        print(f"❌ Error running {description}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Local CI validation")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues where possible")
    args = parser.parse_args()

    print("🚀 Running local CI validation...")

    checks = [
        # Code formatting
        (["black", "--check", "--diff", "."], "Code formatting (Black)"),
        # Linting
        (["ruff", "check", "."], "Linting (Ruff)"),
        # Type checking
        (["mypy", "."], "Type checking (mypy)"),
        # Tests
        (["pytest", "--tb=short"], "Unit tests"),
    ]

    if args.fix:
        # Add fix commands
        fix_checks = [
            (["black", "."], "Auto-format code (Black)"),
            (["ruff", "check", ".", "--fix"], "Auto-fix linting issues (Ruff)"),
        ]
        checks = fix_checks + checks

    failed_checks = []

    for cmd, description in checks:
        if not run_command(cmd, description, args.fix):
            failed_checks.append(description)

    if failed_checks:
        print(f"\n❌ {len(failed_checks)} check(s) failed:")
        for check in failed_checks:
            print(f"  - {check}")
        print("\n💡 Run with --fix to auto-fix formatting and linting issues")
        sys.exit(1)
    else:
        print("\n🎉 All checks passed! Ready to commit.")
        sys.exit(0)


if __name__ == "__main__":
    main()
