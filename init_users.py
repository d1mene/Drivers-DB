"""Создаёт таблицу app_users и двух пользователей."""
import getpass
from db import Database, error_text
import auth

DEFAULTS = [
    ("admin", "admin123", "admin", "администратор (все права)"),
    ("user", "user123", "user", "пользователь (только просмотр)"),
]


def main():
    try:
        db = Database()
        auth.ensure_table(db)
    except Exception as e:
        print("Ошибка:", error_text(e))
        return
    print("Создание пользователей. Enter — оставить значение по умолчанию.\n")
    for def_login, def_pwd, role, descr in DEFAULTS:
        print(f"Роль: {descr}")
        login = input(f"  Логин [{def_login}]: ").strip() or def_login
        pwd = getpass.getpass(f"  Пароль [{def_pwd}]: ") or def_pwd
        auth.create_user(db, login, pwd, role)
        print(f"  -> пользователь «{login}» сохранён\n")
    db.close()
if __name__ == "__main__":
    main()
