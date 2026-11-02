"""One administrator account, throttled across sessions and application instances."""
import hashlib
import hmac
import json
import time


def authenticate_admin(candidate: str, expected: str) -> tuple[bool, str]:
    from services.database import get_db, release_db
    import psycopg2.extras
    if not expected:
        return False, "Configure ADMIN_PASSWORD dans les secrets Streamlit."
    conn = None
    try:
        conn = get_db()
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT pg_advisory_xact_lock(%s)", (735120433,))
                cur.execute("SELECT value FROM admin_settings WHERE key='security:admin_login'")
                row = cur.fetchone()
                state = json.loads(row["value"]) if row else {}
                now = time.time()
                if now < float(state.get("locked_until",0)):
                    return False, "Trop de tentatives. Accès administrateur temporairement verrouillé ; réessaie dans cinq minutes."
                if now - float(state.get("last_attempt",0)) >= 300:
                    state = {}
                valid = bool(candidate) and hmac.compare_digest(hashlib.sha256(candidate.encode()).digest(), hashlib.sha256(expected.encode()).digest())
                count = 0 if valid else int(state.get("attempts",0)) + 1
                state = {"attempts":count,"last_attempt":now,"locked_until":now+300 if count>=5 else 0}
                cur.execute("INSERT INTO admin_settings (key,value) VALUES ('security:admin_login',%s) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value", (json.dumps(state),))
        return (True, "") if valid else (False, "Mot de passe incorrect." if count<5 else "Trop de tentatives. Accès administrateur verrouillé cinq minutes.")
    except Exception as error:
        from services.logger import get_logger
        get_logger("admin_auth").error("Admin authentication failed type=%s",type(error).__name__)
        return False, "Vérification administrateur indisponible. Réessaie plus tard."
    finally:
        if conn is not None: release_db(conn)
