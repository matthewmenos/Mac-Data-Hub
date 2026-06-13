import os
import boto3
from botocore.exceptions import ClientError


def _client(config):
    return boto3.client(
        "s3",
        endpoint_url=config["R2_ENDPOINT_URL"],
        aws_access_key_id=config["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=config["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def download_db(config, r2_key: str, local_path: str) -> bool:
    """Download a DB file from R2 to local_path. Returns True if found."""
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    try:
        _client(config).download_file(config["R2_BUCKET_NAME"], r2_key, local_path)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise


def upload_db(config, local_path: str, r2_key: str) -> None:
    """Upload a local DB file to R2."""
    _client(config).upload_file(local_path, config["R2_BUCKET_NAME"], r2_key)
