import uuid
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for
from ..services.db import global_db
from ..services.paystack import initialize_transaction

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def home():
    config = current_app.config
    with global_db(config) as db:
        bundles = db.execute(
            "SELECT * FROM data_bundles WHERE is_active=1 ORDER BY network, volume_mb"
        ).fetchall()
        settings = {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM app_settings").fetchall()}
    return render_template("public/home.html", bundles=bundles, settings=settings)


@public_bp.route("/s/<slug>")
def storefront(slug):
    config = current_app.config
    with global_db(config) as db:
        store = db.execute("SELECT * FROM stores WHERE slug=?", (slug,)).fetchone()
        if not store:
            return render_template("public/404.html"), 404
        pricing = db.execute(
            """SELECT sp.price_pesewas, db.id as bundle_id, db.label, db.network,
                      db.volume_mb, db.validity_days, db.offer_slug
               FROM store_pricing sp
               JOIN data_bundles db ON db.id = sp.bundle_id
               WHERE sp.store_id=? AND db.is_active=1
               ORDER BY db.network, db.volume_mb""",
            (store["id"],)
        ).fetchall()
    return render_template("public/storefront.html", store=store, pricing=pricing)


@public_bp.route("/checkout", methods=["GET", "POST"])
def checkout():
    config = current_app.config
    if request.method == "GET":
        bundle_id = request.args.get("bundle_id")
        store_id = request.args.get("store_id")
        with global_db(config) as db:
            bundle = db.execute("SELECT * FROM data_bundles WHERE id=?", (bundle_id,)).fetchone()
            store = db.execute("SELECT * FROM stores WHERE id=?", (store_id,)).fetchone() if store_id else None
            price_row = None
            if store:
                price_row = db.execute(
                    "SELECT price_pesewas FROM store_pricing WHERE store_id=? AND bundle_id=?",
                    (store_id, bundle_id)
                ).fetchone()
        if not bundle:
            return redirect(url_for("public.home"))
        price = price_row["price_pesewas"] if price_row else bundle["base_price_pesewas"]
        return render_template("public/checkout.html", bundle=bundle, store=store, price=price)

    # POST: initiate Paystack payment
    data = request.get_json()
    bundle_id = data.get("bundle_id")
    store_id = data.get("store_id")
    phone = data.get("phone", "").strip()
    email = data.get("email", "").strip()

    with global_db(config) as db:
        bundle = db.execute("SELECT * FROM data_bundles WHERE id=?", (bundle_id,)).fetchone()
        store = db.execute("SELECT * FROM stores WHERE id=?", (store_id,)).fetchone() if store_id else None
        price_row = None
        if store:
            price_row = db.execute(
                "SELECT price_pesewas FROM store_pricing WHERE store_id=? AND bundle_id=?",
                (store_id, bundle_id)
            ).fetchone()

        price = price_row["price_pesewas"] if price_row else bundle["base_price_pesewas"]
        profit = price - bundle["base_price_pesewas"] if store else 0
        order_id = str(uuid.uuid4())
        reference = f"MDH-{order_id[:8].upper()}"

        db.execute(
            """INSERT INTO orders
               (id, store_id, bundle_id, customer_phone, customer_email, network,
                volume_mb, amount_pesewas, base_cost_pesewas, profit_pesewas,
                paystack_reference, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,'pending')""",
            (order_id, store_id, bundle_id, phone, email,
             bundle["network"], bundle["volume_mb"],
             price, bundle["base_price_pesewas"], profit, reference)
        )

    callback_url = f"{config['APP_URL']}/checkout/verify?ref={reference}"
    result = initialize_transaction(
        config["PAYSTACK_SECRET_KEY"], email, price, reference, callback_url,
        metadata={"order_id": order_id, "phone": phone}
    )
    return jsonify({"authorization_url": result["data"]["authorization_url"],
                    "reference": reference})


@public_bp.route("/checkout/verify")
def checkout_verify():
    ref = request.args.get("ref", "")
    return render_template("public/checkout_verify.html", reference=ref)


@public_bp.route("/apply")
def apply():
    return redirect(url_for("auth.register"))
