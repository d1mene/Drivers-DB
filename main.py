"""Автопарк — клиентское GUI-приложение для БД PostgreSQL (tkinter).

Запуск:  python main.py
"""
import tkinter as tk
from tkinter import ttk, messagebox

import auth
from db import Database, error_text
from entities import ENTITIES
from grid_view import GridView
from reports import REPORTS, ReportWindow

ROLE_TEXT = {"admin": "администратор (полный доступ)",
             "user": "пользователь (только просмотр)"}


def mark_arrival(grid, rid):
    """Кнопка журнала: проставить время прибытия = сейчас."""
    try:
        n = grid.db.execute(
            "UPDATE journal SET time_in = localtimestamp(0) WHERE id = %s AND time_in IS NULL",
            (rid,))
    except Exception as e:
        messagebox.showerror("Не удалось отметить прибытие", error_text(e), parent=grid)
        return
    if n == 0:
        messagebox.showinfo("Уже отмечено", "У этой записи время прибытия уже заполнено.", parent=grid)
    grid.load()


EXTRA_ACTIONS = {"journal": [("Отметить прибытие", mark_arrival)]}


class LoginDialog(tk.Toplevel):
    MAX_ATTEMPTS = 3

    def __init__(self, master, db):
        super().__init__(master)
        
        self.db, self.role, self.attempts = db, None, 0
        self.title("Автопарк — вход")
        self.resizable(False, False)
        frm = ttk.Frame(self, padding=22)
        frm.pack()
        ttk.Label(frm, text="Вход в систему", font=("TkDefaultFont", 15, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(0, 14))
        self.login_var, self.pwd_var = tk.StringVar(), tk.StringVar()
        ttk.Label(frm, text="Логин:").grid(row=1, column=0, sticky="w", pady=4)
        e1 = ttk.Entry(frm, textvariable=self.login_var, width=26)
        e1.grid(row=1, column=1, pady=4)
        ttk.Label(frm, text="Пароль:").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=self.pwd_var, show="*", width=26).grid(row=2, column=1, pady=4)
        btns = ttk.Frame(frm)
        btns.grid(row=3, column=0, columnspan=2, pady=(14, 0))
        ttk.Button(btns, text="Войти", command=self.submit).pack(side="left", padx=4)
        ttk.Button(btns, text="Отмена", command=self.destroy).pack(side="left", padx=4)
        self.bind("<Return>", lambda e: self.submit())
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_reqwidth()) // 2
        y = (self.winfo_screenheight() - self.winfo_reqheight()) // 3
        self.geometry(f"+{x}+{y}")
        e1.focus_set()
        self.grab_set()

    def submit(self):
        login, pwd = self.login_var.get(), self.pwd_var.get()
        if not login.strip() or not pwd:
            messagebox.showwarning("Вход", "Введите логин и пароль.", parent=self)
            return
        try:
            role = auth.authenticate(self.db, login, pwd)
        except Exception as e:
            messagebox.showerror(
                "Ошибка БД",
                error_text(e) + "\n\nЕсли таблицы app_users нет — запустите init_users.py",
                parent=self)
            return
        if role:
            self.role = role
            self.destroy()
            return
        self.attempts += 1
        self.pwd_var.set("")
        if self.attempts >= self.MAX_ATTEMPTS:
            messagebox.showerror("Доступ запрещён", "Превышено число попыток входа.", parent=self)
            self.destroy()
        else:
            messagebox.showerror(
                "Ошибка входа",
                f"Неверный логин или пароль.\nОсталось попыток: {self.MAX_ATTEMPTS - self.attempts}",
                parent=self)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.withdraw()
        self.title("Автопарк")
        self.geometry("760x460")
        self.db, self.role, self.windows = None, None, {}
        self.status = ttk.Label(self, anchor="w", relief="sunken", padding=(6, 2))
        self.status.pack(side="bottom", fill="x")
        
        body = ttk.Frame(self, padding=30)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Автопарк", font=("TkDefaultFont", 24, "bold")).pack(pady=(40, 6))
        ttk.Label(body, text="Учёт рейсовых перевозок пассажиров\n\n"
                             "Используйте меню: СПРАВОЧНИКИ · ЖУРНАЛЫ · ОТЧЕТЫ",
                  justify="center").pack()
        self.protocol("WM_DELETE_WINDOW", self.quit_app)

    def start(self):
        try:
            self.db = Database()
        except Exception as e:
            messagebox.showerror(
                "Ошибка подключения к БД",
                error_text(e) + "\n\nПроверьте параметры в файле config.ini (host, port, dbname, user, password)")
            self.destroy()
            return
        self.enter_session()

    def enter_session(self):
        self.withdraw()
        dlg = LoginDialog(self, self.db)
        self.wait_window(dlg)
        
        if not dlg.role:
            self.quit_app()
            return
        
        self.role = dlg.role
        self.build_menu()
        self.status.config(
            text=f"Роль: {ROLE_TEXT[self.role]}   |   БД: {self.db.dbname}@{self.db.host}")
        self.deiconify()

    def switch_user(self):
        self.close_windows()
        self.enter_session()

    def close_windows(self):
        for w in list(self.windows.values()):
            if w.winfo_exists():
                w.destroy()
        self.windows.clear()

    def quit_app(self):
        if self.db:
            self.db.close()
        self.destroy()

    def build_menu(self):
        bar = tk.Menu(self)
        refs, journals, reps, system = (tk.Menu(bar, tearoff=False) for _ in range(4))
        for key, ent in ENTITIES.items():
            (refs if ent.group == "ref" else journals).add_command(
                label=ent.title, command=lambda k=key: self.open_grid(k))
            
        for key, spec in REPORTS.items():
            reps.add_command(label=spec["title"], command=lambda k=key: self.open_report(k))
            
        system.add_command(label="Сменить пользователя", command=self.switch_user)
        system.add_separator()
        system.add_command(label="Выход", command=self.quit_app)
        bar.add_cascade(label="СПРАВОЧНИКИ", menu=refs)
        bar.add_cascade(label="ЖУРНАЛЫ", menu=journals)
        bar.add_cascade(label="ОТЧЕТЫ", menu=reps)
        bar.add_cascade(label="СИСТЕМА", menu=system)
        self.config(menu=bar)

    def _show(self, key, factory):
        w = self.windows.get(key)
        if w is not None and w.winfo_exists():
            w.deiconify()
            w.lift()
            w.focus_force()
            return
        self.windows[key] = factory()

    def open_grid(self, key):
        ent = ENTITIES[key]

        def factory():
            win = tk.Toplevel(self)
            win.title(ent.title)
            win.geometry("960x520")
            GridView(win, self.db, ent, can_edit=(self.role == "admin"),
                     extra_actions=EXTRA_ACTIONS.get(key, ())).pack(fill="both", expand=True)
            return win

        self._show("grid:" + key, factory)

    def open_report(self, key):
        self._show("report:" + key, lambda: ReportWindow(self, self.db, key))


if __name__ == "__main__":
    app = App()
    app.after(50, app.start)
    app.mainloop()
