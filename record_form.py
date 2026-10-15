"""Форма работы с записью таблицы: ДОБАВИТЬ / ИЗМЕНИТЬ / УДАЛИТЬ / ЗАКРЫТЬ."""
import tkinter as tk
from datetime import datetime
from db import error_text, unique_labels
from tkinter import ttk, messagebox

DT_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
              "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M")


def parse_dt(text):
    for fmt in DT_FORMATS:
        try:
            return datetime.strptime(text.strip(), fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    raise ValueError("неверный формат даты/времени (пример: 2026-09-29 14:30)")


class RecordForm(tk.Toplevel):
    def __init__(self, parent, db, entity, record_id=None, can_edit=True, on_change=None):
        super().__init__(parent)
        self.db, self.entity = db, entity
        self.record_id, self.can_edit, self.on_change = record_id, can_edit, on_change
        self.vars, self.label_to_id, self.id_to_label = {}, {}, {}
        self.resizable(False, False)
        self._set_title()
        
        self._build()
        if record_id is not None:
            self._load()
            
        self._update_buttons()
        self.bind("<Escape>", lambda e: self.destroy())
        self.transient(parent)
        self.update_idletasks()
        self.geometry(f"+{parent.winfo_rootx() + 60}+{parent.winfo_rooty() + 60}")
        self.grab_set()

    def _set_title(self):
        suffix = "новая запись" if self.record_id is None else f"№ {self.record_id}"
        mode = "" if self.can_edit else " (только просмотр)"
        self.title(f"{self.entity.item_title} — {suffix}{mode}")

    def _build(self):
        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        state = "normal" if self.can_edit else "disabled"
        
        for row, f in enumerate(self.entity.fields):
            ttk.Label(body, text=f.label + (" *" if f.required else "")).grid(
                row=row, column=0, sticky="w", pady=5, padx=(0, 12))
            var = tk.StringVar()
            self.vars[f.name] = var
            
            if f.kind == "choice":
                try:
                    pairs = unique_labels(self.db.query(f.lookup_sql)[1])
                except Exception as e:
                    messagebox.showerror("Ошибка", error_text(e), parent=self)
                    pairs = []
                self.label_to_id[f.name] = {lbl: pid for pid, lbl in pairs}
                self.id_to_label[f.name] = {pid: lbl for pid, lbl in pairs}
                values = ([] if f.required else [""]) + [lbl for _, lbl in pairs]
                ttk.Combobox(body, textvariable=var, values=values, width=46,
                             state="readonly" if self.can_edit else "disabled"
                             ).grid(row=row, column=1, sticky="w")
                
            elif f.kind == "datetime":
                box = ttk.Frame(body)
                box.grid(row=row, column=1, sticky="w")
                ttk.Entry(box, textvariable=var, width=26, state=state).pack(side="left")
                b = ttk.Button(box, text="Сейчас", width=8,
                               command=lambda v=var: v.set(self._now()))
                b.pack(side="left", padx=6)
                if not self.can_edit:
                    b.state(["disabled"])
                ttk.Label(box, text="ГГГГ-ММ-ДД ЧЧ:ММ", foreground="gray").pack(side="left")
                
            else:
                ttk.Entry(body, textvariable=var, width=49, state=state).grid(
                    row=row, column=1, sticky="w")

        ttk.Label(body, text="* — обязательное поле", foreground="gray").grid(
            row=len(self.entity.fields), column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.status = ttk.Label(body, text="", foreground="#1a6b1a")
        self.status.grid(row=len(self.entity.fields) + 1, column=0, columnspan=2,
                         sticky="w", pady=(2, 8))

        btns = ttk.Frame(body)
        btns.grid(row=len(self.entity.fields) + 2, column=0, columnspan=2, sticky="e")
        self.b_add = ttk.Button(btns, text="ДОБАВИТЬ", command=self._add)
        self.b_edit = ttk.Button(btns, text="ИЗМЕНИТЬ", command=self._update)
        self.b_del = ttk.Button(btns, text="УДАЛИТЬ", command=self._delete)
        self.b_close = ttk.Button(btns, text="ЗАКРЫТЬ", command=self.destroy)
        for b in (self.b_add, self.b_edit, self.b_del, self.b_close):
            b.pack(side="left", padx=4)

    def _update_buttons(self):
        new = self.record_id is None
        for b, on in ((self.b_add, new), (self.b_edit, not new), (self.b_del, not new)):
            b.state(["!disabled"] if (on and self.can_edit) else ["disabled"])

    def _now(self):
        try:
            return self.db.query("SELECT to_char(localtimestamp(0), 'YYYY-MM-DD HH24:MI:SS')")[1][0][0]
        except Exception:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _load(self):
        e = self.entity
        sel = ", ".join(f.select_expr for f in e.fields)
        try:
            _, rows = self.db.query(f"SELECT {sel} FROM {e.table} WHERE id = %s", (self.record_id,))
        except Exception as ex:
            messagebox.showerror("Ошибка", error_text(ex), parent=self)
            self.after(0, self.destroy)
            return
        
        if not rows:
            messagebox.showwarning("Запись не найдена", "Запись уже удалена.", parent=self)
            self.after(0, self.destroy)
            return
        for f, v in zip(e.fields, rows[0]):
            
            if v is None:
                self.vars[f.name].set("")
            elif f.kind == "choice":
                self.vars[f.name].set(self.id_to_label[f.name].get(v, ""))
            else:
                self.vars[f.name].set(str(v))

    def _collect(self):
        values = []
        for f in self.entity.fields:
            raw = self.vars[f.name].get().strip()
            if not raw:
                if f.required:
                    raise ValueError(f"Поле «{f.label}» обязательно для заполнения.")
                values.append(None)
                continue
            if f.kind == "choice":
                values.append(self.label_to_id[f.name][raw])
            elif f.kind == "datetime":
                try:
                    values.append(parse_dt(raw))
                except ValueError as ex:
                    raise ValueError(f"Поле «{f.label}»: {ex}")
            else:
                if f.max_len and len(raw) > f.max_len:
                    raise ValueError(f"Поле «{f.label}»: не более {f.max_len} символов.")
                values.append(raw)
        return values

    def _notify(self):
        if self.on_change:
            self.on_change()

    def _add(self):
        try:
            vals = self._collect()
        except ValueError as ex:
            messagebox.showwarning("Проверьте данные", str(ex), parent=self)
            return
        
        e = self.entity
        cols = ", ".join(f.name for f in e.fields)
        ph = ", ".join("%s" + f.cast for f in e.fields)
        try:
            new_id = self.db.execute(
                f"INSERT INTO {e.table} ({cols}) VALUES ({ph}) RETURNING id", vals, fetch=True)[0]
        except Exception as ex:
            messagebox.showerror("Не удалось добавить", error_text(ex), parent=self)
            return
        
        for v in self.vars.values():
            v.set("")
        self.status.config(text=f"Запись добавлена (ID {new_id}). Можно вводить следующую.")
        self._notify()

    def _update(self):
        try:
            vals = self._collect()
        except ValueError as ex:
            messagebox.showwarning("Проверьте данные", str(ex), parent=self)
            return
        e = self.entity
        sets = ", ".join(f"{f.name} = %s{f.cast}" for f in e.fields)
        try:
            n = self.db.execute(f"UPDATE {e.table} SET {sets} WHERE id = %s",
                                vals + [self.record_id])
        except Exception as ex:
            messagebox.showerror("Не удалось изменить", error_text(ex), parent=self)
            return
        if n == 0:
            messagebox.showwarning("Запись не найдена", "Запись уже удалена.", parent=self)
            return
        self.status.config(text="Изменения сохранены.")
        self._notify()

    def _delete(self):
        if not messagebox.askyesno("Подтверждение",
                                   f"Удалить запись № {self.record_id}?", parent=self):
            return
        try:
            self.db.execute(f"DELETE FROM {self.entity.table} WHERE id = %s", (self.record_id,))
        except Exception as ex:
            messagebox.showerror("Не удалось удалить", error_text(ex), parent=self)
            return
        self._notify()
        self.destroy()
