"""Работа с PostgreSQL: чтение config.ini, подключение, выполнение запросов."""
import configparser
import os

import psycopg2
from psycopg2 import errors

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.ini")


class Database:
    def __init__(self, config_path=CONFIG_PATH):
        cfg = configparser.ConfigParser(interpolation=None)
        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"Не найден файл параметров подключения: {config_path}")

        for enc in ("utf-8-sig", "cp1251"):
            try:
                cfg.read(config_path, encoding=enc)
                break
            except UnicodeDecodeError:
                cfg = configparser.ConfigParser(interpolation=None)
                
        if "database" not in cfg:
            raise ValueError("В config.ini отсутствует секция [database]")
        s = cfg["database"]
        params = dict(
            host=s.get("host", "localhost"),
            port=s.getint("port", 5432),
            dbname=s.get("dbname", "autopark"),
            user=s.get("user", "postgres"),
            password=s.get("password", ""),
            connect_timeout=s.getint("connect_timeout", 5),
            client_encoding="UTF8",
        )
        schema = s.get("schema", "").strip()
        if schema:
            params["options"] = f"-c search_path={schema},public"
        self.dbname = params["dbname"]
        self.host = params["host"]
        self.port = params["port"]
        try:
            self.conn = psycopg2.connect(**params)
        except UnicodeDecodeError as e:
            raise RuntimeError(
                "Не удалось подключиться к PostgreSQL "
                f"(host={self.host}, port={self.port}, dbname={self.dbname}, "
                f"user={params['user']}).\n\nОтвет сервера:\n" + _decode_bytes(e.object)
                + "\n\nЧаще всего это неверный порт, пароль или имя базы.") from None
        except psycopg2.OperationalError as e:
            raise RuntimeError(
                f"Не удалось подключиться (host={self.host}, port={self.port}, "
                f"dbname={self.dbname}, user={params['user']}).\n\n{e}") from None

    def query(self, sql, params=None):
        """SELECT / CALL: возвращает (список_имён_столбцов, список_строк)."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                cols = [d[0] for d in cur.description] if cur.description else []
                rows = cur.fetchall() if cur.description else []
            self.conn.commit()
            return cols, rows
        except Exception:
            self.conn.rollback()
            raise

    def execute(self, sql, params=None, fetch=False):
        """INSERT / UPDATE / DELETE в одной транзакции.
        fetch=True -> вернуть первую строку (для RETURNING), иначе rowcount."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                result = cur.fetchone() if fetch else cur.rowcount
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


def _decode_bytes(b):
    if isinstance(b, str):
        return b
    for enc in ("utf-8", "cp1251", "cp866"):
        try:
            return b.decode(enc).strip()
        except UnicodeDecodeError:
            pass
    return b.decode("utf-8", errors="replace").strip()


def error_text(e):
    if isinstance(e, UnicodeDecodeError):
        return _decode_bytes(e.object)
    """Понятный текст ошибки (в т.ч. сообщения из триггеров RAISE EXCEPTION)."""
    if isinstance(e, psycopg2.Error):
        msg = getattr(getattr(e, "diag", None), "message_primary", None) or str(e)
        if isinstance(e, errors.ForeignKeyViolation):
            return ("Операция невозможна: запись связана с другими записями "
                    "(ссылочная целостность).\n" + msg)
        if isinstance(e, errors.CheckViolation):
            return "Значение не проходит проверку в БД:\n" + msg
        if isinstance(e, errors.UniqueViolation):
            return "Такая запись уже существует:\n" + msg
        if isinstance(e, errors.NotNullViolation):
            return "Не заполнено обязательное поле:\n" + msg
        return msg.strip()
    return str(e)


def unique_labels(rows):
    """[(id, label)] -> [(id, уникальная_подпись)]. Дубли получают суффикс [#id]
    (например, копии маршрутов, которые создаёт ваш триггер при изменении)."""
    counts = {}
    for _, label in rows:
        counts[label] = counts.get(label, 0) + 1
    return [(i, label if counts[label] == 1 else f"{label} [#{i}]")
            for i, label in rows]
