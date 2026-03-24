"""Infrastructure and structural tests.

These catch deployment, config, and import issues that unit tests miss —
like the Procfile syntax error that bash choked on.
"""

import importlib
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


# ── Procfile / Deployment ──────────────────────────────────────────────

class TestProcfile:
    def test_procfile_exists(self):
        assert (ROOT / "Procfile").is_file()

    def test_procfile_no_bare_parentheses(self):
        """The exact bug that broke us: bash can't handle () in command lines."""
        content = (ROOT / "Procfile").read_text()
        for i, line in enumerate(content.strip().splitlines(), 1):
            # Parentheses are only OK inside quotes
            unquoted = re.sub(r'"[^"]*"', '', line)
            unquoted = re.sub(r"'[^']*'", '', unquoted)
            assert "(" not in unquoted and ")" not in unquoted, (
                f"Procfile line {i} has unquoted parentheses: {line}"
            )

    def test_procfile_entries_are_valid(self):
        content = (ROOT / "Procfile").read_text()
        for line in content.strip().splitlines():
            if not line.strip():
                continue
            assert ":" in line, f"Procfile line missing colon: {line}"
            proc_type, _, command = line.partition(":")
            assert proc_type.strip(), f"Procfile line missing process type: {line}"
            assert command.strip(), f"Procfile line missing command: {line}"

    def test_procfile_web_uses_gunicorn(self):
        content = (ROOT / "Procfile").read_text()
        for line in content.strip().splitlines():
            if line.startswith("web:"):
                assert "gunicorn" in line
                break
        else:
            pytest.skip("No web process in Procfile")


class TestRailway:
    def test_railway_toml_exists(self):
        assert (ROOT / "railway.toml").is_file()

    def test_runtime_txt_exists(self):
        assert (ROOT / "runtime.txt").is_file()

    def test_runtime_specifies_python(self):
        content = (ROOT / "runtime.txt").read_text().strip()
        assert content.startswith("python-")


# ── Requirements ───────────────────────────────────────────────────────

class TestRequirements:
    def test_requirements_exists(self):
        assert (ROOT / "requirements.txt").is_file()

    def test_all_requirements_installed(self):
        """Every package in requirements.txt must be importable."""
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
        for line in content.strip().splitlines():
            pkg_name = re.split(r"[><=!]", line.strip())[0]
            import_name = pkg_map.get(pkg_name, pkg_name)
            try:
                importlib.import_module(import_name)
            except ImportError:
                pytest.fail(f"Package '{pkg_name}' (import as '{import_name}') not installed")

    def test_no_duplicate_requirements(self):
        content = (ROOT / "requirements.txt").read_text()
        names = []
        for line in content.strip().splitlines():
            name = re.split(r"[><=!]", line.strip())[0].lower()
            assert name not in names, f"Duplicate requirement: {name}"
            names.append(name)


# ── Module Imports ─────────────────────────────────────────────────────

class TestImports:
    """Every Python module in the project must import without errors."""

    @pytest.fixture
    def all_py_modules(self):
        """Collect all .py module dotted paths in the project."""
        modules = []
        for py_file in ROOT.rglob("*.py"):
            rel = py_file.relative_to(ROOT)
            parts = list(rel.parts)
            if parts[0] in ("tests", ".venv", "venv", "__pycache__"):
                continue
            if parts[-1] == "__init__.py":
                parts = parts[:-1]
            else:
                parts[-1] = parts[-1].replace(".py", "")
            if parts:
                modules.append(".".join(parts))
        return modules

    def test_config_imports(self):
        importlib.import_module("config.settings")
        importlib.import_module("config.constants")
        importlib.import_module("config.gates")

    def test_db_imports(self):
        importlib.import_module("db.engine")
        importlib.import_module("db.models")
        importlib.import_module("db.repository")

    def test_utils_imports(self):
        importlib.import_module("utils.retry")
        importlib.import_module("utils.logging_config")
        importlib.import_module("utils.market_hours")

    def test_analyzer_imports(self):
        importlib.import_module("analyzers.base")
        importlib.import_module("analyzers.momentum")
        importlib.import_module("analyzers.reversion")
        importlib.import_module("analyzers.risk")
        importlib.import_module("analyzers.decision_support")

    def test_broker_imports(self):
        importlib.import_module("broker.client")
        importlib.import_module("broker.account")
        importlib.import_module("broker.positions")
        importlib.import_module("broker.orders")

    def test_bot_imports(self):
        importlib.import_module("bot.scoring")
        importlib.import_module("bot.gate_check")
        importlib.import_module("bot.learning")
        importlib.import_module("bot.safety")

    def test_signals_imports(self):
        importlib.import_module("signals.base")
        importlib.import_module("signals.congressional")
        importlib.import_module("signals.sec_filings")
        importlib.import_module("signals.earnings")
        importlib.import_module("signals.macro")
        importlib.import_module("signals.health")

    def test_dashboard_imports(self):
        importlib.import_module("dashboard.app")


# ── Database Schema ────────────────────────────────────────────────────

class TestDatabase:
    def test_schema_file_exists(self):
        assert (ROOT / "db" / "schema.sql").is_file()

    def test_schema_creates_all_tables(self):
        import sqlite3
        schema = (ROOT / "db" / "schema.sql").read_text()
        conn = sqlite3.connect(":memory:")
        conn.executescript(schema)

        tables = [
            r[0] for r in
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        ]
        expected = ["trades", "analyzer_scores", "weights", "signal_cache", "source_health", "audit_log"]
        for t in expected:
            assert t in tables, f"Missing table: {t}"
        conn.close()

    def test_schema_is_idempotent(self):
        """Running schema twice must not error (CREATE IF NOT EXISTS)."""
        import sqlite3
        schema = (ROOT / "db" / "schema.sql").read_text()
        conn = sqlite3.connect(":memory:")
        conn.executescript(schema)
        conn.executescript(schema)  # second run must not fail
        conn.close()

    def test_init_db_and_default_weights(self):
        import sqlite3
        import tempfile, os
        # Use a local temp dir to avoid Windows permission issues
        tmp_dir = os.path.join(ROOT, "data", ".test_tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        db_path = os.path.join(tmp_dir, "test.db")
        try:
            from db.engine import init_db
            init_db(db_path)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            assert "trades" in tables
            conn.close()
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)
            if os.path.exists(tmp_dir):
                os.rmdir(tmp_dir)


# ── Config / Environment ──────────────────────────────────────────────

class TestConfig:
    def test_env_example_exists(self):
        assert (ROOT / ".env.example").is_file()

    def test_env_example_has_required_keys(self):
        content = (ROOT / ".env.example").read_text()
        required = ["ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ALPACA_BASE_URL"]
        for key in required:
            assert key in content, f".env.example missing required key: {key}"

    def test_settings_loads_without_env(self):
        """Settings must load with defaults even if env vars are empty."""
        from config.settings import Settings
        s = Settings()
        assert s.min_final_score > 0
        assert s.max_hold_days > 0
        assert s.learning_rate > 0

    def test_default_weights_sum_to_one(self):
        from config.constants import DEFAULT_WEIGHTS
        total = sum(DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"Default weights sum to {total}, expected 1.0"

    def test_gitignore_excludes_secrets(self):
        content = (ROOT / ".gitignore").read_text()
        assert ".env" in content
        assert "*.db" in content or "data/*.db" in content


# ── Flask App ──────────────────────────────────────────────────────────

class TestFlaskApp:
    @pytest.fixture
    def client(self):
        from dashboard.app import create_app
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_index_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_api_overview_returns_json(self, client):
        resp = client.get("/api/overview")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "open_positions" in data
        assert "stats" in data
        assert "weights" in data

    def test_api_health_returns_json(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "sources" in data

    def test_api_audit_returns_json(self, client):
        resp = client.get("/api/audit")
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_api_weights_history_returns_json(self, client):
        resp = client.get("/api/weights/history")
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_static_css_serves(self, client):
        resp = client.get("/static/style.css")
        assert resp.status_code == 200

    def test_static_js_serves(self, client):
        resp = client.get("/static/dashboard.js")
        assert resp.status_code == 200


# ── Analyzer Contracts ─────────────────────────────────────────────────

class TestAnalyzerContracts:
    """All analyzers must follow the same interface contract."""

    @pytest.fixture
    def bars(self, sample_bars):
        return sample_bars

    def test_all_analyzers_return_0_to_1(self, bars):
        from analyzers.momentum import MomentumAnalyzer
        from analyzers.reversion import ReversionAnalyzer
        from analyzers.risk import RiskAnalyzer
        from analyzers.decision_support import DecisionSupportAnalyzer

        for Cls in [MomentumAnalyzer, ReversionAnalyzer, RiskAnalyzer, DecisionSupportAnalyzer]:
            a = Cls()
            result = a.analyze("TEST", bars)
            assert 0.0 <= result.score <= 1.0, f"{Cls.name} returned score {result.score}"
            assert isinstance(result.details, dict), f"{Cls.name} details is not a dict"

    def test_all_analyzers_have_name(self):
        from analyzers.momentum import MomentumAnalyzer
        from analyzers.reversion import ReversionAnalyzer
        from analyzers.risk import RiskAnalyzer
        from analyzers.decision_support import DecisionSupportAnalyzer

        names = set()
        for Cls in [MomentumAnalyzer, ReversionAnalyzer, RiskAnalyzer, DecisionSupportAnalyzer]:
            a = Cls()
            assert a.name, f"{Cls.__name__} has no name"
            assert a.name not in names, f"Duplicate analyzer name: {a.name}"
            names.add(a.name)

    def test_risk_analyzer_provides_stop_and_target(self, bars):
        from analyzers.risk import RiskAnalyzer
        result = RiskAnalyzer().analyze("TEST", bars)
        assert "stop_price" in result.details
        assert "target_price" in result.details
        assert result.details["stop_price"] < result.details["target_price"]
