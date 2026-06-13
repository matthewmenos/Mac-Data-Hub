import uuid
from functools import wraps
from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, current_app, jsonify)
from ..services.db import global_db, user_db

reseller_bp = Blueprint("reseller", __name__, url_prefix="/dashboard")


def reseller_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "reseller":
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def _ctx(config):
    uid = session["user_id"]
    with global_db(config) as db:
        user = dict(db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())
        store_row = db.execute("SELECT * FROM stores WHERE user_id=?", (uid,)).fetchone()
        store = dict(store_row) if store_row else None
    return uid, user, store


@reseller_bp.route("/")
@reseller_required
def dashboard():
    config = current_app.config
    uid, user, store = _ctx(config)

    recent_orders, total_earned = [], 0
    with user_db(config, uid) as udb:
        rows = udb.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 10").fetchall()
        recent_orders = [dict(r) for r in rows]
        row = udb.execute("SELECT COALESCE(SUM(amount_pesewas),0) AS t FROM earnings").fetchone()
        total_earned = row["t"] if row else 0

    return render_template("reseller/dashboard.html",
                           user=user, store=store,
                           recent_orders=recent_orders,
                           total_earned=total_earned)


@reseller_bp.route("/orders")
@reseller_required
def orders():
    config = current_app.config
    uid, user, store = _ctx(config)

    with user_db(config, uid) as udb:
        rows = udb.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()

    return render_template("reseller/orders.html",
                           user=user, store=store,
                           orders=[dict(r) for r in rows])


@reseller_bp.route("/pricing", methods=["GET", "POST"])
@reseller_required
def pricing():
    config = current_app.config
    uid, user, store = _ctx(config)

    if not store:
        return redirect(url_for("reseller.dashboard"))

    with global_db(config) as db:
        bundles = [dict(b) for b in db.execute(
            "SELECT * FROM data_bundles WHERE is_active=1 ORDER BY network, volume_mb"
        ).fetchall()]
        existing = {
            r["bundle_id"]: r["price_pesewas"]
            for r in db.execute(
                "SELECT bundle_id, price_pesewas FROM store_pricing WHERE store_id=?",
                (store["id"],)
            ).fetchall()
        }

    if request.method == "POST":
        data = request.get_json()
        with global_db(config) as db:
            for bundle_id, price_str in data.items():
                try:
                    price_pesewas = round(float(price_str) * 100)
                except (ValueError, TypeError):
                    continue
                base = next((b["base_price_pesewas"] for b in bundles if b["id"] == bundle_id), None)
                if base is None or price_pesewas < base:
                    continue
                db.execute(
                    """INSERT INTO store_pricing (id, store_id, bundle_id, price_pesewas)
                       VALUES (?,?,?,?)
                       ON CONFLICT(store_id, bundle_id) DO UPDATE SET price_pesewas=excluded.price_pesewas""",
                    (str(uuid.uuid4()), store["id"], bundle_id, price_pesewas)
                )
        return jsonify({"ok": True})

    return render_template("reseller/pricing.html",
                           user=user, store=store,
                           bundles=bundles, existing=existing)


@reseller_bp.route("/wallet")
@reseller_required
def wallet():
    config = current_app.config
    uid, user, store = _ctx(config)

    with global_db(config) as db:
        rows = db.execute(
            "SELECT * FROM wallet_withdrawals WHERE user_id=? ORDER BY created_at DESC",
            (uid,)
        ).fetchall()

    return render_template("reseller/wallet.html",
                           user=user, store=store,
                           withdrawals=[dict(r) for r in rows])


@reseller_bp.route("/wallet/withdraw", methods=["POST"])
@reseller_required
def withdraw():
    config = current_app.config
    uid = session["user_id"]
    data = request.get_json()

    try:
        amount_pesewas = round(float(data.get("amount", 0)) * 100)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount."}), 400

    mobile = data.get("mobile_number", "").strip()
    network = data.get("network", "").strip()

    with global_db(config) as db:
        user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        min_row = db.execute(
            "SELECT value FROM app_settings WHERE key='min_withdrawal_pesewas'"
        ).fetchone()
        minimum = int(min_row["value"]) if min_row else 10000

        if amount_pesewas < minimum:
            return jsonify({"error": f"Minimum withdrawal is GHS {minimum/100:.2f}."}), 400
        if amount_pesewas > user["wallet_pesewas"]:
            return jsonify({"error": "Insufficient wallet balance."}), 400

        db.execute(
            """INSERT INTO wallet_withdrawals (id, user_id, amount_pesewas, mobile_number, network, status)
               VALUES (?,?,?,?,?,'pending')""",
            (str(uuid.uuid4()), uid, amount_pesewas, mobile, network)
        )
        db.execute(
            "UPDATE users SET wallet_pesewas = wallet_pesewas - ? WHERE id=?",
            (amount_pesewas, uid)
        )

    return jsonify({"ok": True})


@reseller_bp.route("/store", methods=["GET", "POST"])
@reseller_required
def store_settings():
    config = current_app.config
    uid, user, store = _ctx(config)

    if not store:
        return redirect(url_for("reseller.dashboard"))

    if request.method == "POST":
        data = request.get_json()
        store_name = data.get("store_name", "").strip()
        description = data.get("description", "").strip()

        if not store_name:
            return jsonify({"error": "Store name is required."}), 400

        with global_db(config) as db:
            db.execute(
                "UPDATE stores SET store_name=?, description=? WHERE id=?",
                (store_name, description or None, store["id"])
            )
        return jsonify({"ok": True})

    return render_template("reseller/store.html", user=user, store=store)
