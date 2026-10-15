"""Описание таблиц БД для GridView и формы записи."""
from typing import List, Tuple, Optional
from dataclasses import dataclass, field

FIO_SQL = "p.last_name || ' ' || p.first_name || COALESCE(' ' || p.father_name, '')"


@dataclass
class Field:
    name: str
    label: str 
    kind: str = "text"
    required: bool = False
    max_len: Optional[int] = None
    lookup_sql: Optional[str] = None
    cast: str = ""

    @property
    def select_expr(self):
        if self.kind == "datetime":
            return f"to_char({self.name}, 'YYYY-MM-DD HH24:MI:SS')"
        return self.name


@dataclass
class Entity:
    key: str
    group: str
    title: str
    item_title: str
    table: str
    list_sql: str
    columns: List[Tuple[str, str, int]]
    fields: List[Field] = field(default_factory=list)

PERSONAL_LOOKUP = ("SELECT p.id, " + FIO_SQL +
                   " FROM auto_personal p ORDER BY 2, 1")

ENTITIES = {
    "personal": Entity(
        key="personal", group="ref", title="Персонал (водители)",
        item_title= "Сотрудник", table= "auto_personal",
        list_sql=("SELECT id, last_name, first_name, father_name "
                  "FROM auto_personal ORDER BY last_name, first_name, id"),
        columns=[("id", "ID", 60), ("last_name", "Фамилия", 180),
                 ("first_name", "Имя", 150), ("father_name", "Отчество", 180)],
        fields=[
            Field("last_name", "Фамилия", required=True, max_len=30),
            Field("first_name", "Имя", required=True, max_len=30),
            Field("father_name", "Отчество", max_len=30),
        ],
    ),
    "auto": Entity(
        key= "auto", group= "ref", title= "Автомобили",
        item_title="Автомобиль", table="auto",
        list_sql=("SELECT a.id, a.num, a.color, a.mark, "
                  "COALESCE(" + FIO_SQL + ", '—') AS driver "
                  "FROM auto a LEFT JOIN auto_personal p ON p.id = a.personal_id "
                  "ORDER BY a.num, a.id"),
        columns=[("id", "ID", 60), ("num", "Гос. номер", 110),
                 ("color", "Цвет", 110), ("mark", "Марка", 140),
                 ("driver", "Водитель", 260)],
        fields=[
            Field("num", "Гос. номер", required=True, max_len=9),
            Field("color", "Цвет", max_len=30),
            Field("mark", "Марка", max_len=50),
            Field("personal_id", "Водитель", kind="choice", required=True,
                  lookup_sql=PERSONAL_LOOKUP),
        ],
    ),
    "routes": Entity(
        key="routes", group="ref", title="Маршруты",
        item_title="Маршрут", table="routes",
        list_sql="SELECT id, name FROM routes ORDER BY name, id",
        columns=[("id", "ID", 60), ("name", "Маршрут (пункт отбытия - назначения)", 420)],
        fields=[Field("name", "Маршрут", required=True)],
    ),
    "journal": Entity(
        key="journal", group="journal", title="Журнал оператора",
        item_title="Запись журнала", table="journal",
        list_sql=("SELECT j.id, to_char(j.time_out, 'YYYY-MM-DD HH24:MI') AS time_out, "
                  "to_char(j.time_in, 'YYYY-MM-DD HH24:MI') AS time_in, "
                  "CASE WHEN j.time_in IS NULL THEN 'в рейсе' ELSE 'вернулся' END AS status, "
                  "r.name AS route, a.num AS auto, COALESCE(" + FIO_SQL + ", '—') AS driver "
                  "FROM journal j "
                  "LEFT JOIN routes r ON r.id = j.route_id "
                  "LEFT JOIN auto a ON a.id = j.auto_id "
                  "LEFT JOIN auto_personal p ON p.id = a.personal_id "
                  "ORDER BY j.time_out DESC, j.id DESC"),
        columns=[("id", "ID", 60), ("time_out", "Отбытие", 130),
                 ("time_in", "Прибытие", 130), ("status", "Статус", 80),
                 ("route", "Маршрут", 240), ("auto", "Автомобиль", 100),
                 ("driver", "Водитель", 220)],
        fields=[
            Field("auto_id", "Автомобиль", kind="choice", required=True,
                  lookup_sql=("SELECT a.id, a.num || ' — ' || COALESCE(" + FIO_SQL + ", 'без водителя') "
                              "FROM auto a LEFT JOIN auto_personal p ON p.id = a.personal_id "
                              "ORDER BY a.num, a.id")),
            Field("route_id", "Маршрут", kind="choice", required=True,
                  lookup_sql="SELECT id, name FROM routes ORDER BY name, id"),
            Field("time_out", "Время отбытия", kind="datetime", required=True,
                  cast="::timestamptz"),
            Field("time_in", "Время прибытия", kind="datetime", cast="::timestamp"),
        ],
    ),
}
