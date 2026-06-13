import uuid
from flask import Blueprint, request, jsonify, session, current_app
from ..services.db import global_db
from ..services.push import get_vapid_public_key

push_bp = Blueprint("push", __name__, url_prefix="/push")


@push_bp.route("/vapid-public-key")
def vapid_public_key():
    key = get_vapid_public_key(current_app.config)
    return jsonify({"key": key})


@push_bp.route("/subscribe", methods=["POST"])
def subscribe():
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")
    p256dh   = (data.get("keys") or {}).get("p256dh")
    auth     = (data.get("keys") or {}).get("auth")

    if not endpoint or not p256dh or not auth:
        return jsonify({"error": "Invalid subscription object"}), 400

    user_id = session.get("user_id")  # None for guests

    with global_db(current_app.config) as db:
        existing = db.execute(
            "SELECT id FROM push_subscriptions WHERE endpoint=?", (endpoint,)
        ).fetchone()
        if existing:
            # Update user_id in case they just logged in
            db.execute(
                "UPDATE push_subscriptions SET user_id=? WHERE endpoint=?",
                (user_id, endpoint)
            )
        else:
            db.execute(
                "INSERT INTO push_subscriptions (id, user_id, endpoint, p256dh, auth) "
                "VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), user_id, endpoint, p256dh, auth)
            )

    return jsonify({"ok": True})


@push_bp.route("/unsubscribe", methods=["POST"])
def unsubscribe():
    data     = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")
    if endpoint:
        with global_db(current_app.config) as db:
            db.execute("DELETE FROM push_subscriptions WHERE endpoint=?", (endpoint,))
    return jsonify({"ok": True})
