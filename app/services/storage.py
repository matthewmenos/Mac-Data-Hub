import os
import boto3
from botocore.exceptions import ClientError


def _client(config):
    """R2 client using the shared API token. Works for both buckets."""
    return boto3.client(
        "s3",
        endpoint_url=config["R2_ENDPOINT_URL"],
        aws_access_key_id=config["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=config["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


# ── Private DB bucket ─────────────────────────────────────────

def download_db(config, r2_key: str, local_path: str) -> bool:
    """Download a DB file from the private bucket. Returns True if found."""
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    try:
        _client(config).download_file(config["R2_BUCKET_NAME"], r2_key, local_path)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise


def upload_db(config, local_path: str, r2_key: str) -> None:
    """Upload a local DB file to the private bucket."""
    _client(config).upload_file(local_path, config["R2_BUCKET_NAME"], r2_key)


# ── Public assets bucket ──────────────────────────────────────

def upload_asset(config, file_obj, r2_key: str, content_type: str) -> str:
    """Upload a file-like object to the public assets bucket. Returns the public URL."""
    _client(config).upload_fileobj(
        file_obj,
        config["R2_ASSETS_BUCKET_NAME"],
        r2_key,
        ExtraArgs={"ContentType": content_type},
    )
    return f"{config['R2_ASSETS_PUBLIC_URL'].rstrip('/')}/{r2_key}"


def delete_asset(config, r2_key: str) -> None:
    """Delete an asset from the public assets bucket."""
    try:
        _client(config).delete_object(
            Bucket=config["R2_ASSETS_BUCKET_NAME"],
            Key=r2_key,
        )
    except ClientError:
        pass
