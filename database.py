import sqlite3
import os
import secrets
from typing import Optional, Dict, Any, List

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "cartag.db"))

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                tag_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                activated INTEGER DEFAULT 0,
                vehicle_name TEXT DEFAULT '',
                owner_name TEXT DEFAULT '',
                owner_token TEXT,
                custom_note TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1
            );
        """)
        try:
            conn.execute("ALTER TABLE tags ADD COLUMN owner_name TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE tags ADD COLUMN is_active INTEGER DEFAULT 1")
        except Exception:
            pass
        for col_def in [
            "ALTER TABLE tags ADD COLUMN blood_group TEXT DEFAULT ''",
            "ALTER TABLE tags ADD COLUMN emergency_contact TEXT DEFAULT ''",
            "ALTER TABLE tags ADD COLUMN emergency_phone TEXT DEFAULT ''",
            "ALTER TABLE tags ADD COLUMN backup_phone TEXT DEFAULT ''",
            "ALTER TABLE tags ADD COLUMN dnd_enabled INTEGER DEFAULT 0",
            "ALTER TABLE tags ADD COLUMN dnd_start TEXT DEFAULT '23:00'",
            "ALTER TABLE tags ADD COLUMN dnd_end TEXT DEFAULT '07:00'",
        ]:
            try:
                conn.execute(col_def)
            except Exception:
                pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_id TEXT NOT NULL,
                endpoint TEXT UNIQUE NOT NULL,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_id TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fcm_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_id TEXT NOT NULL,
                fcm_token TEXT NOT NULL,
                device_type TEXT DEFAULT 'android',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tag_id, fcm_token),
                FOREIGN KEY (tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
            );
        """)
        conn.commit()

    # Ensure official pre-printed stickers exist in database ready to be claimed and alerted
    with get_db() as conn:
        for t in ["BUZZ-699277", "BUZZ-792492", "BUZZ-653178", "BUZZ-970927", "BUZZ-563396", "BUZZ-100001", "CAR-D3AEED"]:
            conn.execute(
                """
                INSERT INTO tags (tag_id, activated, vehicle_name) VALUES (?, 1, 'DL3CCM4468')
                ON CONFLICT(tag_id) DO UPDATE SET activated = 1 WHERE activated = 0
                """,
                (t,)
            )
        # Pre-seed active owner phone FCM token across tags so alerts always deliver even after server restart
        phone_token = "d01v4TxvRzK9uAY2UpRW7U:APA91bHqXHYe8Y-JyJwbNO_qqicY_0tubV13hQMmJJyBou-kOsycXZAmZIhQGV1Cc0QPco65nrIfjtjff3R5Nz0hAV07SKuX11UliIrF_WciFmiXex4S-Pc"
        for t in ["BUZZ-699277", "699277", "BUZZ-792492", "792492", "BUZZ-653178", "653178"]:
            try:
                conn.execute(
                    """
                    INSERT INTO fcm_tokens (tag_id, fcm_token, device_type)
                    VALUES (?, ?, 'android')
                    ON CONFLICT DO NOTHING
                    """,
                    (t, phone_token)
                )
            except Exception:
                pass
        conn.commit()

def create_tag(tag_id: str, owner_token: Optional[str] = None) -> str:
    clean_id = tag_id.strip().upper()
    if not clean_id.startswith("BUZZ-") and not clean_id.startswith("CAR-"):
        clean_id = f"BUZZ-{clean_id}"
    if not owner_token:
        owner_token = secrets.token_urlsafe(16)
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO tags (tag_id, owner_token) VALUES (?, ?)",
            (clean_id, owner_token)
        )
        conn.commit()
    return owner_token

def get_tag(tag_id: str) -> Optional[Dict[str, Any]]:
    clean_id = tag_id.strip().upper()
    buzz_id = clean_id if clean_id.startswith("BUZZ-") else f"BUZZ-{clean_id}"
    num_id = clean_id.replace("BUZZ-", "")
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM tags WHERE UPPER(tag_id) = ? OR UPPER(tag_id) = ? OR UPPER(tag_id) = ?",
            (clean_id, buzz_id, num_id)
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

def activate_tag(tag_id: str, vehicle_name: str, custom_note: str = "", allow_create: bool = False) -> Optional[str]:
    tag = get_tag(tag_id)
    if not tag:
        if not allow_create:
            return None
        clean_id = tag_id.strip().upper()
        if not clean_id.startswith("BUZZ-") and not clean_id.startswith("CAR-"):
            clean_id = f"BUZZ-{clean_id}"
        owner_token = secrets.token_urlsafe(16)
        with get_db() as conn:
            conn.execute(
                "INSERT INTO tags (tag_id, activated, vehicle_name, owner_token, custom_note) VALUES (?, 1, ?, ?, ?)",
                (clean_id, vehicle_name, owner_token, custom_note)
            )
            conn.commit()
        return owner_token
    else:
        canonical_id = tag["tag_id"]
        owner_token = tag["owner_token"] or secrets.token_urlsafe(16)
        with get_db() as conn:
            conn.execute(
                "UPDATE tags SET activated = 1, vehicle_name = ?, owner_token = ?, custom_note = ? WHERE tag_id = ?",
                (vehicle_name, owner_token, custom_note, canonical_id)
            )
            conn.commit()
        return owner_token

def update_tag_profile(tag_id: str, vehicle_name: str, owner_name: str = "", custom_note: str = ""):
    with get_db() as conn:
        conn.execute(
            """
            UPDATE tags 
            SET vehicle_name = ?, owner_name = ?, custom_note = ?
            WHERE tag_id = ?
            """,
            (vehicle_name, owner_name, custom_note, tag_id)
        )
        conn.commit()

def update_emergency_profile(tag_id: str, blood_group: str = "", emergency_contact: str = "", emergency_phone: str = "", backup_phone: str = "", dnd_enabled: int = 0, dnd_start: str = "23:00", dnd_end: str = "07:00"):
    with get_db() as conn:
        conn.execute(
            """
            UPDATE tags
            SET blood_group = ?, emergency_contact = ?, emergency_phone = ?, backup_phone = ?, dnd_enabled = ?, dnd_start = ?, dnd_end = ?
            WHERE tag_id = ?
            """,
            (blood_group, emergency_contact, emergency_phone, backup_phone, dnd_enabled, dnd_start, dnd_end, tag_id)
        )
        conn.commit()

def toggle_tag_active(tag_id: str) -> int:
    with get_db() as conn:
        row = conn.execute("SELECT is_active FROM tags WHERE tag_id = ?", (tag_id,)).fetchone()
        current_state = row["is_active"] if (row and row["is_active"] is not None) else 1
        new_state = 0 if current_state == 1 else 1
        conn.execute("UPDATE tags SET is_active = ? WHERE tag_id = ?", (new_state, tag_id))
        conn.commit()
        return new_state

def save_subscription(tag_id: str, endpoint: str, p256dh: str, auth: str):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO subscriptions (tag_id, endpoint, p256dh, auth)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(endpoint) DO UPDATE SET
                tag_id = excluded.tag_id,
                p256dh = excluded.p256dh,
                auth = excluded.auth
            """,
            (tag_id, endpoint, p256dh, auth)
        )
        conn.commit()

def get_subscriptions(tag_id: str) -> List[Dict[str, Any]]:
    clean_id = tag_id.replace("BUZZ-", "")
    buzz_id = f"BUZZ-{clean_id}"
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM subscriptions WHERE tag_id = ? OR tag_id = ? OR tag_id = ?", (tag_id, buzz_id, clean_id))
        return [dict(row) for row in cursor.fetchall()]

def save_fcm_token(tag_id: str, fcm_token: str, device_type: str = "android"):
    clean_id = tag_id.strip().upper()
    buzz_id = clean_id if clean_id.startswith("BUZZ-") else f"BUZZ-{clean_id}"
    num_id = clean_id.replace("BUZZ-", "")
    with get_db() as conn:
        for t in set([clean_id, buzz_id, num_id]):
            try:
                conn.execute(
                    """
                    INSERT INTO fcm_tokens (tag_id, fcm_token, device_type, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(tag_id, fcm_token) DO UPDATE SET
                        device_type = excluded.device_type,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (t, fcm_token, device_type)
                )
            except Exception:
                # Fallback for old schema where fcm_token had UNIQUE(fcm_token)
                try:
                    conn.execute(
                        """
                        INSERT INTO fcm_tokens (tag_id, fcm_token, device_type, updated_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(fcm_token) DO UPDATE SET
                            tag_id = excluded.tag_id,
                            device_type = excluded.device_type,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (t, fcm_token, device_type)
                    )
                except Exception:
                    pass
        conn.commit()

def get_fcm_tokens(tag_id: str) -> List[str]:
    clean_id = tag_id.replace("BUZZ-", "").strip().upper()
    buzz_id = f"BUZZ-{clean_id}"
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT DISTINCT fcm_token FROM fcm_tokens WHERE UPPER(tag_id) = ? OR UPPER(tag_id) = ? OR UPPER(tag_id) = ?",
            (tag_id.strip().upper(), buzz_id, clean_id)
        )
        tokens = [row["fcm_token"] for row in cursor.fetchall() if row["fcm_token"]]
        return list(dict.fromkeys(tokens))

def delete_subscription(endpoint: str):
    with get_db() as conn:
        conn.execute("DELETE FROM subscriptions WHERE endpoint = ?", (endpoint,))
        conn.commit()

def delete_invalid_fcm_token(fcm_token: str):
    with get_db() as conn:
        conn.execute("DELETE FROM fcm_tokens WHERE fcm_token = ?", (fcm_token,))
        conn.commit()

def delete_fcm_token(fcm_token: str, tag_id: Optional[str] = None):
    with get_db() as conn:
        if tag_id:
            clean_id = tag_id.replace("BUZZ-", "").strip().upper()
            buzz_id = f"BUZZ-{clean_id}"
            conn.execute(
                "DELETE FROM fcm_tokens WHERE fcm_token = ? AND (UPPER(tag_id) = ? OR UPPER(tag_id) = ? OR UPPER(tag_id) = ?)",
                (fcm_token, tag_id.strip().upper(), buzz_id, clean_id)
            )
        else:
            conn.execute("DELETE FROM fcm_tokens WHERE fcm_token = ?", (fcm_token,))
        conn.commit()

def log_alert(tag_id: str, alert_type: str, message: str = ""):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO alerts (tag_id, alert_type, message) VALUES (?, ?, ?)",
            (tag_id, alert_type, message)
        )
        conn.commit()

def get_recent_alerts(tag_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    clean_id = tag_id.replace("BUZZ-", "")
    buzz_id = f"BUZZ-{clean_id}"
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM alerts WHERE tag_id = ? OR tag_id = ? OR tag_id = ? ORDER BY id DESC LIMIT ?",
            (tag_id, buzz_id, clean_id, limit)
        )
        return [dict(row) for row in cursor.fetchall()]

def clear_alerts(tag_id: str) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM alerts WHERE tag_id = ?", (tag_id,))
        conn.commit()

def get_admin_stats() -> Dict[str, Any]:
    with get_db() as conn:
        total_tags = conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
        activated = conn.execute("SELECT COUNT(*) FROM tags WHERE activated = 1").fetchone()[0]
        total_alerts = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        recent_cars = conn.execute(
            """
            SELECT t.tag_id, t.vehicle_name, t.activated, t.created_at, t.custom_note,
                   (SELECT COUNT(*) FROM alerts a WHERE a.tag_id = t.tag_id) as alert_count
            FROM tags t
            ORDER BY t.activated DESC, t.created_at DESC
            """
        ).fetchall()
        return {
            "total_stickers": total_tags,
            "activated_cars": activated,
            "total_alerts": total_alerts,
            "cars": [dict(r) for r in recent_cars]
        }

# Initialize tables
init_db()
