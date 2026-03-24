"""Flask dashboard application factory."""

import json
from flask import Flask, render_template, jsonify

from config.settings import settings
from db.engine import init_db
from db.repository import (
    get_open_trades,
    get_all_trades,
    get_current_weights,
    get_weight_history,
    get_all_source_health,
    get_audit_log,
    initialize_default_weights,
)


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.secret_key = settings.flask_secret_key

    init_db()
    initialize_default_weights()

    # ── Routes ──────────────────────────────────────────────────

    @app.route("/")
    def index():
        return render_template("base.html", page="overview")

    @app.route("/api/overview")
    def api_overview():
        open_trades = get_open_trades()
        all_trades = get_all_trades(limit=20)
        weights = get_current_weights()
        health = get_all_source_health()

        closed = [t for t in all_trades if t.status == "closed"]
        total_pnl = sum(t.pnl_dollars or 0 for t in closed)
        win_count = sum(1 for t in closed if (t.pnl_dollars or 0) > 0)
        loss_count = sum(1 for t in closed if (t.pnl_dollars or 0) <= 0)

        return jsonify({
            "open_positions": [
                {
                    "id": t.id, "symbol": t.symbol, "qty": t.quantity,
                    "entry_price": t.entry_price, "stop": t.stop_price,
                    "target": t.target_price, "score": t.final_score,
                    "entry_time": t.entry_time,
                }
                for t in open_trades
            ],
            "recent_trades": [
                {
                    "id": t.id, "symbol": t.symbol, "status": t.status,
                    "pnl_dollars": t.pnl_dollars, "pnl_pct": t.pnl_pct,
                    "exit_reason": t.exit_reason, "score": t.final_score,
                    "entry_time": t.entry_time, "exit_time": t.exit_time,
                }
                for t in all_trades
            ],
            "weights": weights,
            "health": health,
            "stats": {
                "total_pnl": round(total_pnl, 2),
                "win_count": win_count,
                "loss_count": loss_count,
                "win_rate": round(win_count / max(1, win_count + loss_count) * 100, 1),
                "open_count": len(open_trades),
            },
        })

    @app.route("/api/weights/history")
    def api_weight_history():
        history = get_weight_history(limit=200)
        return jsonify([
            {"analyzer": w.analyzer_name, "weight": w.weight,
             "reason": w.reason, "updated_at": w.updated_at}
            for w in history
        ])

    @app.route("/api/audit")
    def api_audit():
        logs = get_audit_log(limit=100)
        return jsonify(logs)

    @app.route("/api/health")
    def api_health():
        return jsonify({"sources": get_all_source_health()})

    @app.route("/api/trigger/scan", methods=["POST"])
    def trigger_scan():
        """Manual trigger for a scan-and-trade cycle."""
        from bot.orchestrator import trade_once
        from bot.safety import safe_execute
        result = safe_execute(trade_once, fallback={"error": "failed"}, context="manual_scan")
        return jsonify(result)

    @app.route("/api/trigger/refresh", methods=["POST"])
    def trigger_refresh():
        """Manual trigger for signal refresh."""
        from signals.health import refresh_signals
        from bot.safety import safe_execute
        result = safe_execute(refresh_signals, fallback={"error": "failed"}, context="manual_refresh")
        return jsonify(result)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
