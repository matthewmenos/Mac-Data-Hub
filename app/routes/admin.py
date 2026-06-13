import uuid
from functools import wraps
from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, current_app, jsonify)
from ..services.db import global_db

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "admin":
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/")
@admin_required
def dashboard():
    config = current_app.config
    with global_db(config) as db:
        total_orders   = db.execute("SELECT COUNT(*) as c FROM orders").fetchone()["c"]
        total_revenue  = db.execute(
            "SELECT COALESCE(SUM(amount_pesewas),0) as t FROM orders WHERE status='dispatched'"
        ).fetchone()["t"]
        total_resellers = db.execute(
            "SELECT COUNT(*) as c FROM users WHERE role='reseller' AND is_active=1"
        ).fetchone()["c"]
        pending_orders = db.execute(
            "SELECT COUNT(*) as c FROM orders WHERE status='pending'"
        ).fetchone()["c"]
        today_revenue  = db.execute(
            "SELECT COALESCE(SUM(amount_pesewas),0) as t FROM orders "
            "WHERE status='dispatched' AND date(created_at)=date('now')"
        ).fetchone()["t"]
        today_orders   = db.execute(
            "SELECT COUNT(*) as c FROM orders WHERE date(created_at)=date('now')"
        ).fetchone()["c"]
        pending_withdrawals = db.execute(
            "SELECT COUNT(*) as c FROM wallet_withdrawals WHERE status='pending'"
        ).fetchone()["c"]
        total_bundles  = db.execute(
            "SELECT COUNT(*) as c FROM data_bundles WHERE is_active=1"
        ).fetchone()["c"]
        recent_orders  = db.execute(
            """SELECT o.*, b.label as bundle_label, s.store_name
               FROM orders o
               LEFT JOIN data_bundles b ON b.id = o.bundle_id
               LEFT JOIN stores s ON s.id = o.store_id
               ORDER BY o.created_at DESC LIMIT 8"""
        ).fetchall()
        recent_withdrawals = db.execute(
            """SELECT w.*, u.full_name, u.email
               FROM wallet_withdrawals w JOIN users u ON u.id = w.user_id
               WHERE w.status='pending'
               ORDER BY w.created_at ASC LIMIT 5"""
        ).fetchall()
        # Revenue by network (dispatched)
        net_revenue = db.execute(
            """SELECT network, COUNT(*) as cnt,
               COALESCE(SUM(amount_pesewas),0) as rev
               FROM orders WHERE status='dispatched'
               GROUP BY network"""
        ).fetchall()

    return render_template("admin/dashboard.html",
                           total_orders=total_orders,
                           total_revenue=total_revenue,
                           today_revenue=today_revenue,
                           today_orders=today_orders,
                           total_resellers=total_resellers,
                           pending_orders=pending_orders,
                           pending_withdrawals=pending_withdrawals,
                           total_bundles=total_bundles,
                           recent_orders=recent_orders,
                           recent_withdrawals=recent_withdrawals,
                           net_revenue=net_revenue)


@admin_bp.route("/notifications")
@admin_required
def notifications():
    config = current_app.config
    items = []
    with global_db(config) as db:
        pending_orders = db.execute(
            "SELECT COUNT(*) as c FROM orders WHERE status='pending'"
        ).fetchone()["c"]
        pending_withdrawals = db.execute(
            "SELECT COUNT(*) as c FROM wallet_withdrawals WHERE status='pending'"
        ).fetchone()["c"]
        recent_orders = db.execute(
            "SELECT id, customer_phone, network, created_at FROM orders "
            "WHERE status='pending' ORDER BY created_at DESC LIMIT 5"
        ).fetchall()
        recent_withdrawals = db.execute(
            "SELECT w.id, u.full_name, w.amount_pesewas, w.created_at "
            "FROM wallet_withdrawals w JOIN users u ON u.id=w.user_id "
            "WHERE w.status='pending' ORDER BY w.created_at DESC LIMIT 5"
        ).fetchall()

    for o in recent_orders:
        items.append({
            "type": "order",
            "icon": "orange",
            "msg": f"New <strong>{o['network'].upper()}</strong> order for {o['customer_phone']}",
            "time": o["created_at"][:16].replace("T", " "),
            "url": "/admin/orders",
        })
    for w in recent_withdrawals:
        amt = "GHS %.2f" % (w["amount_pesewas"] / 100)
        items.append({
            "type": "withdrawal",
            "icon": "blue",
            "msg": f"<strong>{w['full_name']}</strong> requested {amt} withdrawal",
            "time": w["created_at"][:16].replace("T", " "),
            "url": "/admin/withdrawals",
        })

    total_unread = pending_orders + pending_withdrawals
    return jsonify({"items": items, "unread": total_unread})


@admin_bp.route("/bundles", methods=["GET", "POST", "PUT", "DELETE"])
@admin_required
def bundles():
    config = current_app.config
    with global_db(config) as db:
        if request.method == "GET":
            all_bundles = db.execute(
                "SELECT * FROM data_bundles ORDER BY network, volume_mb"
            ).fetchall()
            counts = {
                "total":    db.execute("SELECT COUNT(*) as c FROM data_bundles").fetchone()["c"],
                "active":   db.execute("SELECT COUNT(*) as c FROM data_bundles WHERE is_active=1").fetchone()["c"],
                "inactive": db.execute("SELECT COUNT(*) as c FROM data_bundles WHERE is_active=0").fetchone()["c"],
            }
            return render_template("admin/bundles.html", bundles=all_bundles, counts=counts)

        data = request.get_json()

        if request.method == "POST":
            bundle_id = str(uuid.uuid4())
            db.execute(
                """INSERT INTO data_bundles
                   (id, network, offer_slug, label, volume_mb, validity_days,
                    base_price_pesewas, guest_price_pesewas, is_active)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (bundle_id, data["network"], data["offer_slug"], data["label"],
                 int(data["volume_mb"]), int(data["validity_days"]),
                 int(data["base_price_pesewas"]),
                 int(data.get("guest_price_pesewas", data["base_price_pesewas"])),
                 int(data.get("is_active", 1)))
            )
            return jsonify({"ok": True, "id": bundle_id})

        if request.method == "PUT":
            db.execute(
                """UPDATE data_bundles SET network=?, offer_slug=?, label=?, volume_mb=?,
                   validity_days=?, base_price_pesewas=?, guest_price_pesewas=?, is_active=?
                   WHERE id=?""",
                (data["network"], data["offer_slug"], data["label"],
                 int(data["volume_mb"]), int(data["validity_days"]),
                 int(data["base_price_pesewas"]),
                 int(data.get("guest_price_pesewas", data["base_price_pesewas"])),
                 int(data.get("is_active", 1)),
                 data["id"])
            )
            return jsonify({"ok": True})

        if request.method == "DELETE":
            db.execute("DELETE FROM data_bundles WHERE id=?", (data["id"],))
            return jsonify({"ok": True})


@admin_bp.route("/resellers")
@admin_required
def resellers():
    config = current_app.config
    with global_db(config) as db:
        all_resellers = db.execute(
            """SELECT u.*, s.slug, s.store_name,
               (SELECT COUNT(*) FROM orders o JOIN stores st ON st.id=o.store_id WHERE st.user_id=u.id) as order_count
               FROM users u LEFT JOIN stores s ON s.user_id = u.id
               WHERE u.role='reseller' ORDER BY u.created_at DESC"""
        ).fetchall()
        counts = {
            "total":    db.execute("SELECT COUNT(*) as c FROM users WHERE role='reseller'").fetchone()["c"],
            "active":   db.execute("SELECT COUNT(*) as c FROM users WHERE role='reseller' AND is_active=1").fetchone()["c"],
            "inactive": db.execute("SELECT COUNT(*) as c FROM users WHERE role='reseller' AND is_active=0").fetchone()["c"],
        }
    return render_template("admin/resellers.html", resellers=all_resellers, counts=counts)


@admin_bp.route("/resellers/<user_id>/toggle", methods=["POST"])
@admin_required
def toggle_reseller(user_id):
    config = current_app.config
    with global_db(config) as db:
        user = db.execute("SELECT is_active FROM users WHERE id=?", (user_id,)).fetchone()
        new_state = 0 if user["is_active"] else 1
        db.execute("UPDATE users SET is_active=? WHERE id=?", (new_state, user_id))
    return jsonify({"ok": True, "is_active": new_state})


@admin_bp.route("/orders")
@admin_required
def orders():
    config = current_app.config
    with global_db(config) as db:
        all_orders = db.execute(
            """SELECT o.*, b.label as bundle_label, s.store_name
               FROM orders o
               LEFT JOIN data_bundles b ON b.id = o.bundle_id
               LEFT JOIN stores s ON s.id = o.store_id
               ORDER BY o.created_at DESC"""
        ).fetchall()
        counts = {
            "total":      db.execute("SELECT COUNT(*) as c FROM orders").fetchone()["c"],
            "dispatched": db.execute("SELECT COUNT(*) as c FROM orders WHERE status='dispatched'").fetchone()["c"],
            "pending":    db.execute("SELECT COUNT(*) as c FROM orders WHERE status='pending'").fetchone()["c"],
            "failed":     db.execute("SELECT COUNT(*) as c FROM orders WHERE status='failed'").fetchone()["c"],
        }
    return render_template("admin/orders.html", orders=all_orders, counts=counts)


@admin_bp.route("/withdrawals", methods=["GET", "POST"])
@admin_required
def withdrawals():
    config = current_app.config
    with global_db(config) as db:
        if request.method == "GET":
            all_wd = db.execute(
                """SELECT w.*, u.full_name, u.email, u.phone
                   FROM wallet_withdrawals w JOIN users u ON u.id = w.user_id
                   ORDER BY CASE w.status WHEN 'pending' THEN 0 ELSE 1 END, w.created_at DESC"""
            ).fetchall()
            counts = {
                "total":   db.execute("SELECT COUNT(*) as c FROM wallet_withdrawals").fetchone()["c"],
                "pending": db.execute("SELECT COUNT(*) as c FROM wallet_withdrawals WHERE status='pending'").fetchone()["c"],
                "paid":    db.execute("SELECT COUNT(*) as c FROM wallet_withdrawals WHERE status='paid'").fetchone()["c"],
                "failed":  db.execute("SELECT COUNT(*) as c FROM wallet_withdrawals WHERE status='failed'").fetchone()["c"],
            }
            return render_template("admin/withdrawals.html", withdrawals=all_wd, counts=counts)

        data = request.get_json()
        db.execute(
            "UPDATE wallet_withdrawals SET status=? WHERE id=?",
            (data["status"], data["id"])
        )
        return jsonify({"ok": True})


@admin_bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    config = current_app.config
    with global_db(config) as db:
        if request.method == "POST":
            data = request.get_json()
            for key, value in data.items():
                db.execute(
                    "INSERT INTO app_settings (key, value) VALUES (?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, str(value))
                )
            return jsonify({"ok": True})
        all_settings = {r["key"]: r["value"] for r in
                        db.execute("SELECT key, value FROM app_settings").fetchall()}
    return render_template("admin/settings.html", settings=all_settings)
