import uuid
from flask import Blueprint, request, jsonify, current_app
from ..services.db import global_db, user_db
from ..services.paystack import verify_webhook_signature
from ..services.gigzhub import dispatch_bundle

webhook_bp = Blueprint("webhook", __name__)


@webhook_bp.route("/webhook/paystack", methods=["POST"])
def paystack_webhook():
    config = current_app.config
    signature = request.headers.get("x-paystack-signature", "")
    payload_bytes = request.get_data()

    if not verify_webhook_signature(config["PAYSTACK_SECRET_KEY"], payload_bytes, signature):
        return jsonify({"error": "Invalid signature"}), 401

    event = request.get_json()
    if event.get("event") != "charge.success":
        return jsonify({"ok": True}), 200

    data = event["data"]
    reference = data.get("reference", "")
    metadata = data.get("metadata", {})

    # --- Registration payment ---
    if reference.startswith("REG-"):
        _handle_registration(config, reference)
        return jsonify({"ok": True}), 200

    # --- Bundle order payment ---
    _handle_order(config, reference, metadata)
    return jsonify({"ok": True}), 200


def _handle_registration(config, reference: str):
    with global_db(config) as db:
        reg = db.execute(
            "SELECT * FROM reseller_registrations WHERE paystack_reference=? AND status='pending'",
            (reference,)
        ).fetchone()
        if not reg:
            return

        db.execute(
            "UPDATE reseller_registrations SET status='paid' WHERE id=?", (reg["id"],)
        )
        db.execute(
            "UPDATE users SET is_active=1 WHERE id=?", (reg["user_id"],)
        )


def _handle_order(config, reference: str, metadata: dict):
    with global_db(config) as db:
        order = db.execute(
            "SELECT * FROM orders WHERE paystack_reference=? AND status='pending'",
            (reference,)
        ).fetchone()
        if not order:
            return

        # Dispatch bundle via GigzHub
        try:
            result = dispatch_bundle(
                config["GIGZHUB_API_KEY"],
                order["network"],
                order["customer_phone"],
                _get_offer_slug(db, order["bundle_id"]),
                order["volume_mb"]
            )
            gigzhub_id = result.get("id") or result.get("orderId", "")
            status = "dispatched"
        except Exception:
            gigzhub_id = ""
            status = "failed"

        db.execute(
            "UPDATE orders SET status=?, gigzhub_order_id=? WHERE id=?",
            (status, gigzhub_id, order["id"])
        )

        # Credit reseller wallet and mirror to their personal DB
        if status == "dispatched" and order["store_id"] and order["profit_pesewas"] > 0:
            store = db.execute(
                "SELECT user_id FROM stores WHERE id=?", (order["store_id"],)
            ).fetchone()
            if store:
                db.execute(
                    "UPDATE users SET wallet_pesewas = wallet_pesewas + ? WHERE id=?",
                    (order["profit_pesewas"], store["user_id"])
                )
                bundle_row = db.execute(
                    "SELECT label FROM data_bundles WHERE id=?", (order["bundle_id"],)
                ).fetchone()
                label = bundle_row["label"] if bundle_row else order["network"]
                _mirror_order_to_user_db(config, store["user_id"], order, label)


def _mirror_order_to_user_db(config, user_id: str, order, bundle_label: str = ""):
    with user_db(config, user_id) as udb:
        udb.execute(
            """INSERT OR IGNORE INTO orders
               (id, bundle_label, network, customer_phone, amount_pesewas, profit_pesewas, status)
               VALUES (?,?,?,?,?,?,?)""",
            (order["id"], bundle_label, order["network"],
             order["customer_phone"], order["amount_pesewas"],
             order["profit_pesewas"], "dispatched")
        )
        earning_id = str(uuid.uuid4())
        udb.execute(
            "INSERT OR IGNORE INTO earnings (id, order_id, amount_pesewas) VALUES (?,?,?)",
            (earning_id, order["id"], order["profit_pesewas"])
        )


def _get_offer_slug(db, bundle_id: str) -> str:
    row = db.execute("SELECT offer_slug FROM data_bundles WHERE id=?", (bundle_id,)).fetchone()
    return row["offer_slug"] if row else ""
