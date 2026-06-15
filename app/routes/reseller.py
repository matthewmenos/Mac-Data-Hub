import uuid
from functools import wraps
from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, current_app, jsonify)
from ..services.db import global_db, user_db
from ..services.storage import upload_asset, delete_asset
from ..services.paystack import create_transfer_recipient, initiate_transfer

MOMO_BANK_CODES = {"mtn": "MTN", "telecel": "VDF", "airteltigo": "ATL"}

ALLOWED_LOGO_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2 MB

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

    recent_orders, total_earned, total_orders = [], 0, 0
    with user_db(config, uid) as udb:
        rows = udb.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 10").fetchall()
        recent_orders = [dict(r) for r in rows]
        row = udb.execute("SELECT COALESCE(SUM(amount_pesewas),0) AS t FROM earnings").fetchone()
        total_earned = row["t"] if row else 0
        cnt = udb.execute("SELECT COUNT(*) as c FROM orders").fetchone()
        total_orders = cnt["c"] if cnt else 0

    return render_template("reseller/dashboard.html",
                           user=user, store=store,
                           recent_orders=recent_orders,
                           total_earned=total_earned,
                           total_orders=total_orders)


@reseller_bp.route("/notifications")
@reseller_required
def notifications():
    config = current_app.config
    uid, user, _ = _ctx(config)
    items = []
    # last_seen lets the client tell us what it already saw, so unread count is accurate
    last_seen = request.args.get("last_seen", "")

    with user_db(config, uid) as udb:
        recent_orders = udb.execute(
            "SELECT id, bundle_label, network, profit_pesewas, created_at "
            "FROM orders ORDER BY created_at DESC LIMIT 8"
        ).fetchall()
        if last_seen:
            unread_count = udb.execute(
                "SELECT COUNT(*) as c FROM orders WHERE created_at > ?", (last_seen,)
            ).fetchone()["c"]
        else:
            unread_count = udb.execute(
                "SELECT COUNT(*) as c FROM orders WHERE created_at >= datetime('now','-24 hours')"
            ).fetchone()["c"]

    for o in recent_orders:
        profit = "GHS %.2f" % (o["profit_pesewas"] / 100)
        items.append({
            "type": "order",
            "icon": "green",
            "msg": f"<strong>{o['bundle_label']}</strong> order — +{profit} profit",
            "time": o["created_at"][:16].replace("T", " "),
            "url": "/dashboard/orders",
        })

    return jsonify({"items": items, "unread": unread_count})


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
        min_row = db.execute(
            "SELECT value FROM app_settings WHERE key='min_withdrawal_pesewas'"
        ).fetchone()
        min_withdrawal = int(min_row["value"]) if min_row else 10000

    return render_template("reseller/wallet.html",
                           user=user, store=store,
                           withdrawals=[dict(r) for r in rows],
                           min_withdrawal=min_withdrawal)


@reseller_bp.route("/wallet/setup-payout", methods=["POST"])
@reseller_required
def setup_payout():
    """Save a permanent Paystack mobile-money recipient for this reseller."""
    config = current_app.config
    uid = session["user_id"]
    data = request.get_json() or {}

    phone = data.get("phone", "").strip()
    account_name = data.get("account_name", "").strip()
    network = data.get("network", "").strip().lower()

    if not phone or not account_name or not network:
        return jsonify({"error": "Phone, account name, and network are required."}), 400
    bank_code = MOMO_BANK_CODES.get(network)
    if not bank_code:
        return jsonify({"error": "Invalid network. Choose mtn, telecel, or airteltigo."}), 400

    try:
        result = create_transfer_recipient(
            config["PAYSTACK_SECRET_KEY"], account_name, phone, bank_code
        )
        recipient_code = result["data"]["recipient_code"]
    except Exception as exc:
        return jsonify({"error": f"Could not create payout recipient: {exc}"}), 502

    with global_db(config) as db:
        db.execute(
            """UPDATE users
               SET payout_recipient_code=?, momo_network=?, momo_number=?
               WHERE id=?""",
            (recipient_code, network, phone, uid)
        )

    return jsonify({"ok": True, "recipient_code": recipient_code})


@reseller_bp.route("/wallet/withdraw", methods=["POST"])
@reseller_required
def withdraw():
    config = current_app.config
    uid = session["user_id"]
    data = request.get_json() or {}

    try:
        amount_pesewas = round(float(data.get("amount", 0)) * 100)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount."}), 400

    with global_db(config) as db:
        user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        min_row = db.execute(
            "SELECT value FROM app_settings WHERE key='min_withdrawal_pesewas'"
        ).fetchone()
        minimum = int(min_row["value"]) if min_row else 10000

        if not user["payout_recipient_code"]:
            return jsonify({"error": "Set up your payout profile first before withdrawing."}), 400
        if amount_pesewas < minimum:
            return jsonify({"error": f"Minimum withdrawal is GHS {minimum/100:.2f}."}), 400
        if amount_pesewas > user["wallet_pesewas"]:
            return jsonify({"error": "Insufficient wallet balance."}), 400

        wd_id = str(uuid.uuid4())
        reference = f"WD-{wd_id[:8].upper()}"

        # Deduct balance FIRST (defensive: prevents double-spend)
        db.execute(
            "UPDATE users SET wallet_pesewas = wallet_pesewas - ? WHERE id=?",
            (amount_pesewas, uid)
        )
        # Record the withdrawal as processing immediately
        db.execute(
            """INSERT INTO wallet_withdrawals
               (id, user_id, amount_pesewas, mobile_number, network, status, paystack_transfer_code)
               VALUES (?,?,?,?,?,'processing',?)""",
            (wd_id, uid, amount_pesewas,
             user["momo_number"], user["momo_network"], reference)
        )

    # Hit Paystack AFTER the DB commit — rollback on any failure
    try:
        initiate_transfer(
            config["PAYSTACK_SECRET_KEY"],
            amount_pesewas,
            user["payout_recipient_code"],
            reference,
            reason="Mac Data Hub wallet withdrawal"
        )
    except Exception as exc:
        # Rollback: refund the deducted balance and mark failed
        with global_db(config) as db:
            db.execute(
                "UPDATE users SET wallet_pesewas = wallet_pesewas + ? WHERE id=?",
                (amount_pesewas, uid)
            )
            db.execute(
                "UPDATE wallet_withdrawals SET status='failed' WHERE id=?",
                (wd_id,)
            )
        return jsonify({"error": f"Transfer failed. Your balance has been restored. ({exc})"}), 502

    return jsonify({"ok": True, "message": "Transfer initiated. Funds will arrive shortly."})


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


@reseller_bp.route("/store/logo", methods=["POST"])
@reseller_required
def upload_logo():
    config = current_app.config
    uid, user, store = _ctx(config)

    if not store:
        return jsonify({"error": "Store not found."}), 404

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
    r2_key = f"logos/{store['id']}.{ext}"

    try:
        url = upload_asset(config, file, r2_key, content_type)
    except Exception as e:
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500

    with global_db(config) as db:
        db.execute("UPDATE stores SET logo_url=? WHERE id=?", (url, store["id"]))

    return jsonify({"ok": True, "logo_url": url})


@reseller_bp.route("/store/logo/remove", methods=["POST"])
@reseller_required
def remove_logo():
    config = current_app.config
    uid, user, store = _ctx(config)

    if not store:
        return jsonify({"error": "Store not found."}), 404

    # Best-effort delete from assets bucket for each possible extension
    for ext in ("jpg", "png", "webp", "gif"):
        delete_asset(config, f"logos/{store['id']}.{ext}")

    with global_db(config) as db:
        db.execute("UPDATE stores SET logo_url=NULL WHERE id=?", (store["id"],))

    return jsonify({"ok": True})
