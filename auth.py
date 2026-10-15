"""Авторизация: логин и пароль хранятся только в виде хэшей."""
import hashlib
import hmac
import os

ITERATIONS = 200_000

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS app_users (
    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    login_hash VARCHAR(64) NOT NULL UNIQUE,
    salt       VARCHAR(32) NOT NULL,
    pwd_hash   VARCHAR(64) NOT NULL,
    role       VARCHAR(10) NOT NULL CHECK (role IN ('admin', 'user'))
)
"""


def hash_login(login: str) -> str:
    return hashlib.sha256(login.strip().lower().encode("utf-8")).hexdigest()


def make_salt() -> str:
    return os.urandom(16).hex()


def hash_password(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), ITERATIONS
    ).hex()



def create_user(db, login: str, password: str, role: str):
    salt = make_salt()
    db.execute(
        """INSERT INTO app_users (login_hash, salt, pwd_hash, role)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (login_hash) DO UPDATE
           SET salt = EXCLUDED.salt, pwd_hash = EXCLUDED.pwd_hash,
               role = EXCLUDED.role""",
        (hash_login(login), salt, hash_password(password, salt), role),
    )


def authenticate(db, login: str, password: str):
    """Возвращает роль ('admin' / 'user') или None, если вход не удался."""
    _, rows = db.query(
        "SELECT salt, pwd_hash, role FROM app_users WHERE login_hash = %s",
        (hash_login(login),),
    )
    if not rows:
        hash_password(password, "00" * 16)
        return None
    salt, pwd_hash, role = rows[0]
    if hmac.compare_digest(hash_password(password, salt), pwd_hash):
        return role
    return None

def ensure_table(db):
    db.execute(CREATE_TABLE_SQL)
