import requests

GIGZHUB_BASE = "https://gigzhub.net/api/v1"

NETWORK_MAP = {
    "mtn": "mtn",
    "telecel": "telecel",
    "airteltigo": "airteltigo",
}


def _headers(api_key: str) -> dict:
    return {"x-api-key": api_key, "Content-Type": "application/json"}


def get_offers(api_key: str) -> list:
    resp = requests.get(f"{GIGZHUB_BASE}/offers",
                        headers=_headers(api_key), timeout=15)
    resp.raise_for_status()
    return resp.json()


def dispatch_bundle(api_key: str, network: str, phone: str,
                    offer_slug: str, volume_mb: int) -> dict:
    network_key = NETWORK_MAP.get(network.lower())
    if not network_key:
        raise ValueError(f"Unsupported network: {network}")
    payload = {"phone": phone, "offerSlug": offer_slug, "volume": volume_mb}
    resp = requests.post(f"{GIGZHUB_BASE}/order/{network_key}",
                         json=payload, headers=_headers(api_key), timeout=30)
    resp.raise_for_status()
    return resp.json()
