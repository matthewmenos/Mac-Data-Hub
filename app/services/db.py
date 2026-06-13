import os
import sqlite3
from contextlib import contextmanager
from .storage import download_db, upload_db
from ..models.schema_global import GLOBAL_SCHEMA
from ..models.schema_user import USER_SCHEMA


def _global_r2_key():
    return "global.db"


def _user_r2_key(user_id: str):
    return f"users/{user_id}.db"


def _global_local_path(config) -> str:
    return os.path.join(config["DB_CACHE_DIR"], config["GLOBAL_DB_NAME"])


def _user_local_path(config, user_id: str) -> str:
    return os.path.join(config["DB_CACHE_DIR"], config["USERS_DB_DIR"], f"{user_id}.db")


def init_global_db(config) -> None:
    """Pull global.db from R2 (or create fresh) and apply schema."""
    local = _global_local_path(config)
    if not os.path.exists(local):
        found = download_db(config, _global_r2_key(), local)
        if not found:
            # First run — create and seed
            _apply_schema(local, GLOBAL_SCHEMA)
            upload_db(config, local, _global_r2_key())
    else:
        _apply_schema(local, GLOBAL_SCHEMA)


def init_user_db(config, user_id: str) -> None:
    """Pull or create a per-reseller DB and apply schema."""
    local = _user_local_path(config, user_id)
    if not os.path.exists(local):
        found = download_db(config, _user_r2_key(user_id), local)
        if not found:
            _apply_schema(local, USER_SCHEMA)
            upload_db(config, local, _user_r2_key(user_id))
    else:
        _apply_schema(local, USER_SCHEMA)


def _apply_schema(db_path: str, schema: str) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema)
        conn.commit()


@contextmanager
def global_db(config):
    """Context manager: open global DB, yield connection, upload on clean exit."""
    local = _global_local_path(config)
    conn = sqlite3.connect(local)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
        upload_db(config, local, _global_r2_key())
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def user_db(config, user_id: str):
    """Context manager: open a reseller's personal DB, yield connection, upload on clean exit."""
    local = _user_local_path(config, user_id)
    if not os.path.exists(local):
        init_user_db(config, user_id)
    conn = sqlite3.connect(local)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
        upload_db(config, local, _user_r2_key(user_id))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
