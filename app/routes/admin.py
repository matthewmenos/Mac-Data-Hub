import uuid
from functools import wraps
from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, current_app, jsonify)
from ..services.db import global_db
from ..services.push import broadcast_push
from ..services.storage import upload_asset, delete_asset
from ..services.gigzhub import get_offers, get_balance as gigzhub_get_balance
from ..services.paystack import create_transfer_recipient, initiate_transfer

ALLOWED_LOGO_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_LOGO_BYTES = 2 * 1024 * 1024

# Paystack Ghana mobile money bank codes
MOMO_BANK_CODES = {
    "mtn":        "MTN",
    "telecel":    "VDF",
    "airteltigo": "ATL",
}

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


@admin_bp.route("/gigzhub-balance")
@admin_required
def gigzhub_balance():
    """Return GigzHub wallet balance as JSON for the dashboard stat card."""
    config = current_app.config
    try:
        data = gigzhub_get_balance(config["GIGZHUB_API_KEY"])
        return jsonify({"ok": True, "data": data})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502


@admin_bp.route("/notifications")
@admin_required
def notifications():
    config = current_app.config
    items = []
    last_seen = request.args.get("last_seen", "")
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
            all_bundles = [dict(r) for r in db.execute(
                "SELECT * FROM data_bundles ORDER BY network, volume_mb"
            ).fetchall()]
            counts = {
                "total":    db.execute("SELECT COUNT(*) as c FROM data_bundles").fetchone()["c"],
                "active":   db.execute("SELECT COUNT(*) as c FROM data_bundles WHERE is_active=1").fetchone()["c"],
                "inactive": db.execute("SELECT COUNT(*) as c FROM data_bundles WHERE is_active=0").fetchone()["c"],
            }
            return render_template("admin/bundles.html", bundles=all_bundles, counts=counts)

        data = request.get_json() or {}

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
            if not data.get("id"):
                return jsonify({"ok": False, "error": "Missing bundle id."}), 400
            db.execute("DELETE FROM data_bundles WHERE id=?", (data["id"],))
            return jsonify({"ok": True})


@admin_bp.route("/bundles/gigzhub-prices")
@admin_required
def gigzhub_prices():
    config = current_app.config
    api_key = config.get("GIGZHUB_API_KEY", "")
    if not api_key:
        return jsonify({"ok": False, "error": "GigzHub API key not configured."}), 400
    try:
        raw = get_offers(api_key)
        offers = raw.get("offers", []) if isinstance(raw, dict) else raw

        catalog = []
        for o in offers:
            if not isinstance(o, dict):
                continue
            catalog.append({
                "slug":    o.get("offerSlug", ""),
                "name":    o.get("name", ""),
                "isp":     o.get("isp", ""),
                "type":    o.get("type", ""),
                "volumes": o.get("volumes", []),
            })

        return jsonify({"ok": True, "catalog": catalog})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502


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
        if not user:
            return jsonify({"ok": False, "error": "User not found."}), 404
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


@admin_bp.route("/orders/<order_id>/redispatch", methods=["POST"])
@admin_required
def redispatch_order(order_id):
    """Retry a failed order against GigzHub without charging the customer again."""
    config = current_app.config
    from ..services.gigzhub import dispatch_bundle
    from ..services.push import broadcast_push

    with global_db(config) as db:
        order = db.execute(
            "SELECT o.*, b.offer_slug FROM orders o "
            "LEFT JOIN data_bundles b ON b.id=o.bundle_id "
            "WHERE o.id=?", (order_id,)
        ).fetchone()
        if not order:
            return jsonify({"ok": False, "error": "Order not found."}), 404
        if order["status"] not in ("failed", "paid"):
            return jsonify({"ok": False, "error": f"Cannot redispatch a '{order['status']}' order."}), 400

    gigzhub_id = ""
    gigzhub_error = ""
    status = "failed"
    try:
        result = dispatch_bundle(
            config["GIGZHUB_API_KEY"],
            order["network"],
            order["customer_phone"],
            order["offer_slug"] or "",
            order["volume_mb"] or 0,
        )
        data_obj = result.get("data") or result
        gigzhub_id = (
            str(data_obj.get("id", ""))
            or str(data_obj.get("orderId", ""))
            or str(data_obj.get("order_id", ""))
            or str(data_obj.get("reference", ""))
        )
        status = "dispatched"
    except Exception as exc:
        gigzhub_error = str(exc)[:500]
        return jsonify({"ok": False, "error": gigzhub_error}), 502

    with global_db(config) as db:
        db.execute(
            "UPDATE orders SET status=?, gigzhub_order_id=?, gigzhub_error=NULL WHERE id=?",
            (status, gigzhub_id, order_id)
        )
        # Only credit profit if the order was previously failed (not yet credited).
        # If it was already dispatched once, profit was already credited by the webhook.
        if order["store_id"] and order["profit_pesewas"] > 0 and order["status"] == "failed":
            store = db.execute(
                "SELECT user_id FROM stores WHERE id=?", (order["store_id"],)
            ).fetchone()
            if store:
                db.execute(
                    "UPDATE users SET wallet_pesewas = wallet_pesewas + ? WHERE id=?",
                    (order["profit_pesewas"], store["user_id"])
                )

    return jsonify({"ok": True, "gigzhub_id": gigzhub_id})


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
                "total":      db.execute("SELECT COUNT(*) as c FROM wallet_withdrawals").fetchone()["c"],
                "pending":    db.execute("SELECT COUNT(*) as c FROM wallet_withdrawals WHERE status='pending'").fetchone()["c"],
                "processing": db.execute("SELECT COUNT(*) as c FROM wallet_withdrawals WHERE status='processing'").fetchone()["c"],
                "paid":       db.execute("SELECT COUNT(*) as c FROM wallet_withdrawals WHERE status='paid'").fetchone()["c"],
                "failed":     db.execute("SELECT COUNT(*) as c FROM wallet_withdrawals WHERE status='failed'").fetchone()["c"],
            }
            return render_template("admin/withdrawals.html", withdrawals=all_wd, counts=counts)

        data = request.get_json()
        new_status = data["status"]
        wd = db.execute(
            """SELECT w.*, u.full_name, u.email
               FROM wallet_withdrawals w JOIN users u ON u.id = w.user_id
               WHERE w.id=?""",
            (data["id"],)
        ).fetchone()
        if not wd:
            return jsonify({"ok": False, "error": "Withdrawal not found."}), 404

        # Reject path — only allowed while still pending (before Paystack transfer is sent)
        if new_status == "failed":
            if wd["status"] != "pending":
                return jsonify({"ok": False, "error": "Only pending withdrawals can be rejected. Processing withdrawals are handled automatically by Paystack."}), 400
            db.execute("UPDATE wallet_withdrawals SET status='failed' WHERE id=?", (data["id"],))
            db.execute(
                "UPDATE users SET wallet_pesewas = wallet_pesewas + ? WHERE id=?",
                (wd["amount_pesewas"], wd["user_id"])
            )
            try:
                broadcast_push(config, wd["user_id"],
                               "Withdrawal rejected",
                               f"Your GHS {wd['amount_pesewas']/100:.2f} withdrawal was rejected. Your balance has been restored.",
                               "/dashboard/wallet")
            except Exception:
                pass
            return jsonify({"ok": True})

        # Approve path — trigger Paystack transfer
        if new_status == "approved":
            if wd["status"] != "pending":
                return jsonify({"ok": False, "error": "Only pending withdrawals can be approved."}), 400

            bank_code = MOMO_BANK_CODES.get(wd["network"].lower())
            if not bank_code:
                return jsonify({"ok": False, "error": f"Unsupported network: {wd['network']}"}), 400

            try:
                recipient = create_transfer_recipient(
                    config["PAYSTACK_SECRET_KEY"],
                    wd["full_name"],
                    wd["mobile_number"],
                    bank_code,
                )
                recipient_code = recipient["data"]["recipient_code"]

                transfer_ref = f"WD-{data['id'][:8].upper()}"
                transfer = initiate_transfer(
                    config["PAYSTACK_SECRET_KEY"],
                    wd["amount_pesewas"],
                    recipient_code,
                    transfer_ref,
                    reason=f"Wallet withdrawal for {wd['full_name']}",
                )
                transfer_code = transfer["data"].get("transfer_code", "")
                db.execute(
                    "UPDATE wallet_withdrawals SET status='processing', paystack_transfer_code=? WHERE id=?",
                    (transfer_code, data["id"])
                )
                try:
                    broadcast_push(config, wd["user_id"],
                                   "Withdrawal approved",
                                   f"Your GHS {wd['amount_pesewas']/100:.2f} withdrawal is being processed.",
                                   "/dashboard/wallet")
                except Exception:
                    pass
                return jsonify({"ok": True, "status": "processing"})

            except Exception as exc:
                return jsonify({"ok": False, "error": f"Paystack transfer failed: {str(exc)}"}), 502

        return jsonify({"ok": False, "error": "Invalid status."}), 400


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


@admin_bp.route("/settings/logo", methods=["POST"])
@admin_required
def upload_site_logo():
    config = current_app.config
    file = request.files.get("logo")
    if not file or not file.filename:
        return jsonify({"error": "No file provided."}), 400

    content_type = file.content_type or ""
    if content_type not in ALLOWED_LOGO_TYPES:
        return jsonify({"error": "Only JPEG, PNG, WebP or GIF images are allowed."}), 400

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_LOGO_BYTES:
        return jsonify({"error": "Image must be under 2 MB."}), 400

    ext = content_type.split("/")[-1].replace("jpeg", "jpg")
    r2_key = f"site/logo.{ext}"

    try:
        url = upload_asset(config, file, r2_key, content_type)
    except Exception as e:
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500

    with global_db(config) as db:
        db.execute(
            "INSERT INTO app_settings (key, value) VALUES ('site_logo_url', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (url,)
        )
    return jsonify({"ok": True, "logo_url": url})


@admin_bp.route("/settings/logo/remove", methods=["POST"])
@admin_required
def remove_site_logo():
    config = current_app.config
    for ext in ("jpg", "png", "webp", "gif"):
        delete_asset(config, f"site/logo.{ext}")
    with global_db(config) as db:
        db.execute("DELETE FROM app_settings WHERE key='site_logo_url'")
    return jsonify({"ok": True})


@admin_bp.route("/broadcast", methods=["POST"])
@admin_required
def broadcast():
    config = current_app.config
    data  = request.get_json() or {}
    title = (data.get("title") or "").strip()
    body  = (data.get("body")  or "").strip()
    if not title or not body:
        return jsonify({"ok": False, "error": "Title and message are required."}), 400

    # 1. Persist to broadcasts table so the notification bell picks it up
    broadcast_id = str(uuid.uuid4())
    try:
        with global_db(config) as db:
            db.execute(
                "INSERT INTO broadcasts (id, title, body) VALUES (?,?,?)",
                (broadcast_id, title, body),
            )
    except Exception as exc:
        current_app.logger.exception("Broadcast DB error")
        return jsonify({"ok": False, "error": str(exc)}), 500

    # 2. Fire push notifications — best-effort, never blocks the response
    sent = 0
    try:
        from ..services.push import _send_push_raw, _get_or_create_vapid, _build_claims
        from pywebpush import WebPushException

        vapid, _ = _get_or_create_vapid(config)
        claims   = _build_claims(config)
        icon     = "/static/icons/icon-192.png"

        with global_db(config) as db:
            subs = [dict(r) for r in db.execute(
                """SELECT ps.id, ps.endpoint, ps.p256dh, ps.auth
                   FROM push_subscriptions ps
                   JOIN users u ON u.id = ps.user_id
                   WHERE u.role='reseller' AND u.is_active=1"""
            ).fetchall()]

        stale_ids = []
        for row in subs:
            sub = {"endpoint": row["endpoint"], "keys": {"p256dh": row["p256dh"], "auth": row["auth"]}}
            try:
                _send_push_raw(vapid, claims, sub, title, body, "/dashboard", icon, notif_type="broadcast")
                sent += 1
            except WebPushException:
                stale_ids.append(row["id"])
            except Exception:
                pass

        if stale_ids:
            with global_db(config) as db:
                for sid in stale_ids:
                    db.execute("DELETE FROM push_subscriptions WHERE id=?", (sid,))
    except Exception:
        current_app.logger.exception("Broadcast push error (non-fatal)")

    return jsonify({"ok": True, "sent_to": sent})
