import hashlib
import hmac
import requests


PAYSTACK_BASE = "https://api.paystack.co"


def _headers(secret_key: str) -> dict:
    return {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
    }


def add_paystack_charge(amount_pesewas: int) -> tuple[int, int]:
    """
    Return (total_pesewas_to_charge, fee_pesewas).
    Customer pays the 1.5% portion only; seller absorbs the flat GHS 0.50.
    """
    # Customer pays only the 1.5% portion (rounded to nearest pesewa)
    fee = round(amount_pesewas * 0.015)
    total = amount_pesewas + fee
    return total, fee


def initialize_transaction(secret_key: str, email: str, amount_pesewas: int,
                            reference: str, callback_url: str,
                            metadata: dict = None) -> dict:
    """Create a Paystack transaction. amount in pesewas (GHS subunit, 100 pesewas = GHS 1)."""
    payload = {
        "email": email,
        "amount": amount_pesewas,  # Paystack GHS amounts are in pesewas
        "reference": reference,
        "callback_url": callback_url,
        "currency": "GHS",
    }
    if metadata:
        payload["metadata"] = metadata
    resp = requests.post(f"{PAYSTACK_BASE}/transaction/initialize",
                         json=payload, headers=_headers(secret_key), timeout=15)
    resp.raise_for_status()
    return resp.json()


def verify_webhook_signature(secret_key: str, payload_bytes: bytes, signature: str) -> bool:
    expected = hmac.new(secret_key.encode(), payload_bytes, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_transaction(secret_key: str, reference: str) -> dict:
    resp = requests.get(f"{PAYSTACK_BASE}/transaction/verify/{reference}",
                        headers=_headers(secret_key), timeout=15)
    resp.raise_for_status()
    return resp.json()


def initiate_transfer(secret_key: str, amount_pesewas: int, recipient_code: str,
                      reference: str, reason: str = "Wallet withdrawal") -> dict:
    payload = {
        "source": "balance",
        "amount": amount_pesewas,
        "recipient": recipient_code,
        "reference": reference,
        "reason": reason,
        "currency": "GHS",
    }
    resp = requests.post(f"{PAYSTACK_BASE}/transfer",
                         json=payload, headers=_headers(secret_key), timeout=15)
    resp.raise_for_status()
    return resp.json()


def create_transfer_recipient(secret_key: str, name: str, account_number: str,
                              bank_code: str) -> dict:
    payload = {
        "type": "mobile_money",
        "name": name,
        "account_number": account_number,
        "bank_code": bank_code,
        "currency": "GHS",
    }
    resp = requests.post(f"{PAYSTACK_BASE}/transferrecipient",
                         json=payload, headers=_headers(secret_key), timeout=15)
    resp.raise_for_status()
    return resp.json()
