#!/usr/bin/env python
"""Comprehensive test runner for tradebot-claude.

Run this before every commit/PR to catch issues early.

Usage:
    python run_tests.py          # run all checks
    python run_tests.py --quick  # fast syntax/import checks only
"""

import importlib
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

results = []


def check(name, passed, detail=""):
    status = PASS if passed else FAIL
    results.append((name, status, detail))
    icon = "+" if passed else "!"
    print(f"  [{icon}] {name}" + (f" -- {detail}" if detail and not passed else ""))
    return passed


def run_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── 1. File Structure ──────────────────────────────────────────────────

def check_file_structure():
    run_section("FILE STRUCTURE")
    required_files = [
        "main.py",
        "requirements.txt",
        "Procfile",
        "railway.toml",
        "runtime.txt",
        ".env.example",
        ".gitignore",
        "config/settings.py",
        "config/constants.py",
        "db/schema.sql",
        "db/engine.py",
        "db/repository.py",
        "broker/client.py",
        "broker/orders.py",
        "bot/orchestrator.py",
        "bot/scheduler.py",
        "bot/scoring.py",
        "bot/gate_check.py",
        "bot/exit_manager.py",
        "bot/learning.py",
        "analyzers/momentum.py",
        "analyzers/reversion.py",
        "analyzers/risk.py",
        "analyzers/decision_support.py",
        "signals/health.py",
        "dashboard/app.py",
        "dashboard/templates/base.html",
        "dashboard/static/style.css",
        "dashboard/static/dashboard.js",
    ]
    for f in required_files:
        check(f"exists: {f}", (ROOT / f).is_file(), "MISSING")


# ── 2. Procfile Safety ────────────────────────────────────────────────

def check_procfile():
    run_section("PROCFILE SAFETY")
    content = (ROOT / "Procfile").read_text()
    for i, line in enumerate(content.strip().splitlines(), 1):
        # Strip quoted sections, then check for bare parens
        unquoted = re.sub(r'"[^"]*"', '', line)
        unquoted = re.sub(r"'[^']*'", '', unquoted)
        check(
            f"Procfile line {i}: no bare parentheses",
            "(" not in unquoted and ")" not in unquoted,
            line.strip(),
        )
        # Check for bash-hostile characters
        for ch in [";", "&&", "||", "`", "$("]:
            check(
                f"Procfile line {i}: no '{ch}'",
                ch not in unquoted,
                f"Found '{ch}' which may cause shell issues",
            )
    # Gunicorn factory flag
    for line in content.strip().splitlines():
        if "gunicorn" in line and "create_app" in line:
            check(
                "Procfile gunicorn uses --factory flag",
                "--factory" in line,
                "Must use --factory for app factory pattern",
            )


# ── 3. Requirements ───────────────────────────────────────────────────

def check_requirements():
    run_section("REQUIREMENTS")
    content = (ROOT / "requirements.txt").read_text()
    pkg_map = {
        "alpaca-py": "alpaca",
        "apscheduler": "apscheduler",
        "flask": "flask",
        "gunicorn": "gunicorn",
        "pandas": "pandas",
        "ta": "ta",
        "requests": "requests",
        "python-dotenv": "dotenv",
        "numpy": "numpy",
        "pytz": "pytz",
        "pytest": "pytest",
    }
    seen = set()
    for line in content.strip().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        pkg = re.split(r"[><=!]", line.strip())[0].lower()
        check(f"no duplicate: {pkg}", pkg not in seen, "DUPLICATE")
        seen.add(pkg)
        import_name = pkg_map.get(pkg, pkg)
        try:
            importlib.import_module(import_name)
            check(f"installed: {pkg}", True)
        except ImportError:
            check(f"installed: {pkg}", False, f"pip install {line.strip()}")


# ── 4. Module Imports ─────────────────────────────────────────────────

def check_imports():
    run_section("MODULE IMPORTS")
    modules = [
        "config.settings", "config.constants", "config.gates",
        "db.engine", "db.models", "db.repository",
        "utils.retry", "utils.logging_config", "utils.market_hours",
        "analyzers.base", "analyzers.momentum", "analyzers.reversion",
        "analyzers.risk", "analyzers.decision_support",
        "broker.client", "broker.account", "broker.positions", "broker.orders",
        "bot.scoring", "bot.gate_check", "bot.learning", "bot.safety",
        "bot.scanner", "bot.universe", "bot.orchestrator", "bot.exit_manager",
        "bot.scheduler",
        "signals.base", "signals.congressional", "signals.sec_filings",
        "signals.earnings", "signals.macro", "signals.health",
        "dashboard.app",
    ]
    for mod in modules:
        try:
            importlib.import_module(mod)
            check(f"import {mod}", True)
        except Exception as e:
            check(f"import {mod}", False, str(e))


# ── 5. Config Sanity ──────────────────────────────────────────────────

def check_config():
    run_section("CONFIG SANITY")
    from config.settings import Settings
    s = Settings()
    check("min_final_score > 0", s.min_final_score > 0)
    check("min_reward_risk > 0", s.min_reward_risk > 0)
    check("min_hold_days >= 1", s.min_hold_days >= 1)
    check("max_hold_days > min_hold_days", s.max_hold_days > s.min_hold_days)
    check("learning_rate in (0, 1)", 0 < s.learning_rate < 1)
    check("min_weight in (0, 1)", 0 < s.min_weight < 1)
    check("universe price range valid", s.universe_min_price < s.universe_max_price)

    from config.constants import DEFAULT_WEIGHTS
    total = sum(DEFAULT_WEIGHTS.values())
    check("default weights sum to 1.0", abs(total - 1.0) < 0.001, f"sum={total}")
    check("4 analyzers defined", len(DEFAULT_WEIGHTS) == 4)


# ── 6. Database Schema ────────────────────────────────────────────────

def check_database():
    run_section("DATABASE SCHEMA")
    import sqlite3
    schema = (ROOT / "db" / "schema.sql").read_text()
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(schema)
        check("schema executes cleanly", True)
    except Exception as e:
        check("schema executes cleanly", False, str(e))
        return

    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    for t in ["trades", "analyzer_scores", "weights", "signal_cache", "source_health", "audit_log"]:
        check(f"table exists: {t}", t in tables, "MISSING")

    # Idempotent check
    try:
        conn.executescript(schema)
        check("schema is idempotent (re-runnable)", True)
    except Exception as e:
        check("schema is idempotent (re-runnable)", False, str(e))
    conn.close()


# ── 7. Flask Dashboard ────────────────────────────────────────────────

def check_dashboard():
    run_section("DASHBOARD ROUTES")
    from dashboard.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    routes = [
        ("GET", "/", 200),
        ("GET", "/api/overview", 200),
        ("GET", "/api/health", 200),
        ("GET", "/api/audit", 200),
        ("GET", "/api/weights/history", 200),
        ("GET", "/static/style.css", 200),
        ("GET", "/static/dashboard.js", 200),
    ]
    for method, path, expected in routes:
        resp = client.get(path) if method == "GET" else client.post(path)
        check(f"{method} {path} -> {expected}", resp.status_code == expected,
              f"got {resp.status_code}")


# ── 8. Analyzer Contracts ─────────────────────────────────────────────

def check_analyzer_contracts():
    run_section("ANALYZER CONTRACTS")
    from db.engine import init_db
    init_db()  # Ensure signal_cache table exists for decision_support
    import numpy as np
    import pandas as pd

    np.random.seed(42)
    days = 60
    dates = pd.date_range(end=pd.Timestamp.now(), periods=days, freq="B")
    prices = 5.0 * np.cumprod(1 + np.random.normal(0.001, 0.02, days))
    bars = pd.DataFrame({
        "open": prices * 1.001, "high": prices * 1.015,
        "low": prices * 0.985, "close": prices,
        "volume": np.random.randint(500_000, 3_000_000, days).astype(float),
        "vwap": prices * 0.999,
    }, index=dates)

    from analyzers.momentum import MomentumAnalyzer
    from analyzers.reversion import ReversionAnalyzer
    from analyzers.risk import RiskAnalyzer
    from analyzers.decision_support import DecisionSupportAnalyzer

    for Cls in [MomentumAnalyzer, ReversionAnalyzer, RiskAnalyzer, DecisionSupportAnalyzer]:
        a = Cls()
        check(f"{a.name}: has .name attribute", bool(a.name))
        try:
            result = a.analyze("TEST", bars)
            check(f"{a.name}: score in [0, 1]", 0.0 <= result.score <= 1.0, f"score={result.score}")
            check(f"{a.name}: details is dict", isinstance(result.details, dict))
        except Exception as e:
            check(f"{a.name}: runs without error", False, str(e))

    # Risk analyzer must provide stop/target
    r = RiskAnalyzer().analyze("TEST", bars)
    check("risk: provides stop_price", "stop_price" in r.details)
    check("risk: provides target_price", "target_price" in r.details)
    check("risk: stop < target", r.details.get("stop_price", 0) < r.details.get("target_price", 0))


# ── 9. Python Syntax ──────────────────────────────────────────────────

def check_syntax():
    run_section("PYTHON SYNTAX")
    py_files = list(ROOT.rglob("*.py"))
    py_files = [f for f in py_files if ".venv" not in str(f) and "venv" not in str(f)]
    errors = 0
    for f in py_files:
        try:
            compile(f.read_text(encoding="utf-8"), str(f), "exec")
        except SyntaxError as e:
            check(f"syntax: {f.relative_to(ROOT)}", False, f"line {e.lineno}: {e.msg}")
            errors += 1
    if errors == 0:
        check(f"all {len(py_files)} .py files have valid syntax", True)


# ── 10. Pytest Suite ──────────────────────────────────────────────────

def check_pytest():
    run_section("PYTEST SUITE")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=120,
    )
    # Parse results
    lines = result.stdout.strip().splitlines()
    for line in lines:
        if "PASSED" in line:
            test_name = line.split("::")[1].split(" ")[0] if "::" in line else line
            check(f"pytest: {test_name}", True)
        elif "FAILED" in line:
            test_name = line.split("::")[1].split(" ")[0] if "::" in line else line
            check(f"pytest: {test_name}", False)
        elif "ERROR" in line and "collecting" not in line.lower():
            check(f"pytest: {line.strip()}", False)

    passed = result.returncode == 0
    check("pytest suite: all passed", passed, f"exit code {result.returncode}")
    if not passed:
        # Print last 15 lines of output for debugging
        for line in lines[-15:]:
            print(f"    {line}")


# ── 11. Security Basics ──────────────────────────────────────────────

def check_security():
    run_section("SECURITY BASICS")
    gitignore = (ROOT / ".gitignore").read_text()
    check(".gitignore excludes .env", ".env" in gitignore)
    check(".gitignore excludes *.db", "*.db" in gitignore or "data/*.db" in gitignore)

    # No hardcoded secrets in source
    secret_patterns = [
        r'ALPACA_API_KEY\s*=\s*["\'][A-Za-z0-9]{10,}',
        r'SECRET_KEY\s*=\s*["\'][A-Za-z0-9]{20,}',
        r'password\s*=\s*["\'][^"\']{8,}',
    ]
    for py_file in ROOT.rglob("*.py"):
        if ".venv" in str(py_file):
            continue
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        for pattern in secret_patterns:
            if re.search(pattern, content):
                check(
                    f"no hardcoded secrets in {py_file.relative_to(ROOT)}",
                    False, f"matches pattern: {pattern}",
                )
                break
    check("no hardcoded secrets found in .py files", True)


# ── MAIN ──────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 60)
    print("  TRADEBOT-CLAUDE TEST SUITE")
    print("=" * 60)

    quick = "--quick" in sys.argv

    check_file_structure()
    check_procfile()
    check_syntax()
    check_requirements()
    check_imports()
    check_config()
    check_database()
    check_security()

    if not quick:
        check_analyzer_contracts()
        check_dashboard()
        check_pytest()

    # Summary
    passed = sum(1 for _, s, _ in results if s == PASS)
    failed = sum(1 for _, s, _ in results if s == FAIL)
    total = len(results)

    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed}/{total} passed, {failed} failed")
    print(f"{'='*60}")

    if failed:
        print("\n  FAILURES:")
        for name, status, detail in results:
            if status == FAIL:
                print(f"    [!] {name}: {detail}")
        print()
        sys.exit(1)
    else:
        print("\n  All checks passed!\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
