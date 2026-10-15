"""Пользовательский элемент GridView (на базе ttk.Treeview)."""
import tkinter as tk
from decimal import Decimal
from tkinter import ttk, messagebox

from db import error_text
from record_form import RecordForm


def _sort_key(v):
    if v is None:
        return (0, 0, "")
    if isinstance(v, (int, float, Decimal)):
        return (1, float(v), "")
    return (2, 0, str(v).lower())


class GridView(ttk.Frame):
    """Таблица с поиском, сортировкой по клику на заголовок и открытием
    формы записи (двойной клик / Enter / кнопки)."""

    def __init__(self, master, db, entity, can_edit, extra_actions=()):
        super().__init__(master, padding=6)
        
        self.db, self.entity, self.can_edit = db, entity, can_edit
        self.cols, self.rows = [], []
        self.sort_col, self.sort_desc = None, False

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Поиск:").pack(side="left")
        self.search = tk.StringVar()
        
        self.search.trace_add("write", lambda *_: self.refresh_tree())
        ttk.Entry(bar, textvariable=self.search, width=28).pack(side="left", padx=4)
        ttk.Button(bar, text="Обновить", command=self.load).pack(side="left", padx=4)

        ttk.Button(bar, text="Открыть запись", command=self.open_selected).pack(side="right")
        
        self.btn_new = ttk.Button(bar, text="Новая запись", command=self.open_new)
        self.btn_new.pack(side="right", padx=4)
        
        if not can_edit:
            self.btn_new.state(["disabled"])
        for text, callback in extra_actions:
            b = ttk.Button(bar, text=text,
                           command=lambda cb=callback: self._run_action(cb))
            b.pack(side="right", padx=4)
            if not can_edit:
                b.state(["disabled"])

        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True)
        names = [c[0] for c in entity.columns]
        
        self.tree = ttk.Treeview(wrap, columns=names, show="headings", selectmode="browse")
        
        for name, header, width in entity.columns:
            self.tree.heading(name, text=header, command=lambda c=name: self.sort_by(c))
            self.tree.column(name, width=width, anchor="w", stretch=(name != "id"))
            
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        hs = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        self.status = ttk.Label(self, anchor="w")
        self.status.pack(fill="x", pady=(6, 0))

        self.tree.bind("<Double-1>", lambda e: self.open_selected())
        self.tree.bind("<Return>", lambda e: self.open_selected())
        self.load()

    def load(self):
        try:
            self.cols, self.rows = self.db.query(self.entity.list_sql)
        except Exception as e:
            messagebox.showerror("Ошибка загрузки данных", error_text(e), parent=self)
            return
        self.refresh_tree()

    def refresh_tree(self):
        prev = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        idx = {c: i for i, c in enumerate(self.cols)}
        show = [c[0] for c in self.entity.columns]
        needle = self.search.get().strip().lower()
        rows = self.rows
        
        if needle:
            rows = [r for r in rows
                    if any(needle in str(r[idx[c]] if r[idx[c]] is not None else "").lower()
                           for c in show if c != "id")]
        if self.sort_col:
            i = idx[self.sort_col]
            rows = sorted(rows, key=lambda r: _sort_key(r[i]), reverse=self.sort_desc)
        for r in rows:
            values = ["" if r[idx[c]] is None else r[idx[c]] for c in show]
            self.tree.insert("", "end", iid=str(r[0]), values=values)
        if prev and self.tree.exists(prev[0]):
            self.tree.selection_set(prev[0])
            self.tree.see(prev[0])
        self.status.config(text=f"Записей: {len(rows)} из {len(self.rows)}")
        for name, header, _ in self.entity.columns:
            arrow = (" ▼" if self.sort_desc else " ▲") if name == self.sort_col else ""
            self.tree.heading(name, text=header + arrow)

    def sort_by(self, col):
        if self.sort_col == col:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_col, self.sort_desc = col, False
        self.refresh_tree()

    def selected_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def open_selected(self):
        rid = self.selected_id()
        if rid is None:
            messagebox.showinfo("Запись не выбрана", "Выберите запись в таблице.", parent=self)
            return
        self._open_form(rid)

    def open_new(self):
        self._open_form(None)
        
    def _run_action(self, callback):
        rid = self.selected_id()
        if rid is None:
            messagebox.showinfo("Запись не выбрана", "Выберите запись в таблице.", parent=self)
            return
        callback(self, rid)

    def _open_form(self, rid):
        RecordForm(self.winfo_toplevel(), self.db, self.entity, rid,
                   self.can_edit, on_change=self.load)
