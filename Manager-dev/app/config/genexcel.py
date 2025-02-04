from enum import Enum, IntEnum

from app.db.models import Activity, User, WorkerPositionActual, WorkerProfile

FILENAME_TEMPLATE = "Отчёт {} за {} {} на {}.xlsx"

ACTIVITIES = "Коды"
CORRECTIONS = "Исправления"
REPORT = "Отчёт"


class Styles(Enum):
    BORDERS = {"border": 1, "border_color": "black"}
    BOARDLESS = {"border": 0}
    BASIC_CENTER = {
        "text_wrap": True,
        "align": "center",
        "valign": "vcenter",
    } | BORDERS
    BOLD_CENTER = {
        "bold": True,
    } | BASIC_CENTER
    BASIC_CENTER_REPORT = {"font_size": 14} | BASIC_CENTER
    BOLD_CENTER_REPORT = {"font_size": 14} | BOLD_CENTER
    MASTER = {"bg_color": "yellow"} | BOLD_CENTER_REPORT
    BASIC = {
        "text_wrap": True,
        "valign": "vcenter",
        "align": "left",
    }
    BASIC_BOARDERS = BASIC | BORDERS
    HEADER = {
        "text_wrap": True,
        "bold": True,
        "align": "center",
        "valign": "vcenter",
    } | BORDERS
    HEADER_REPORT = {
        "font_size": 14,
    } | HEADER
    ROTATION_90 = {"rotation": 90}
    HEADER_90 = ROTATION_90 | HEADER_REPORT
    LINK = {"font_color": "blue"} | BASIC_CENTER | BOARDLESS
    LINK_90 = LINK | ROTATION_90
    DATETIME = {
        "num_format": "yyyy-mm-dd hh:mm:ss",
        "text_wrap": True,
        "valign": "vcenter",
        "align": "left",
    } | BORDERS
    TOTAL = {"font_color": "red"} | BOLD_CENTER_REPORT | BOARDLESS
    TITLE = {
        "bg_color": "white",
        "bold": True,
        "underline": 1,
        "font_size": 16,
    } | BASIC


class Table:
    DESC = 0
    COLUMN = 1
    ROW = 2

    class Desc:
        MAP = 0
        STYLE = 1


activity_table = {
    Table.DESC: {
        "Код": (Activity.code, None),
        "Длительность": (Activity.duration, Styles.BASIC_CENTER),
        "Описание": (Activity.description, Styles.BASIC_BOARDERS),
    },
    Table.COLUMN: {
        "A:A": 8,
        "B:B": 15,
        "C:C": 40,
    },
}


class CorrectionFields:
    MASTER = "master"
    WORKER = "worker"
    INIT_CODE = "init_code"
    INIT_DATE = "init_date"
    INIT_CODE_ID = "init_code_id"
    NEW_CODE_ID = "new_code_id"
    NEW_CODE = "new_code"
    REASON = "reason"
    NEW_DATE = "new_date"


corrections_table = {
    Table.DESC: {
        "Мастер": (CorrectionFields.MASTER, Styles.BASIC_BOARDERS),
        "Рабочий": (CorrectionFields.WORKER, Styles.BASIC_BOARDERS),
        "Старый код": (CorrectionFields.INIT_CODE, None),
        "Дата выставления": (CorrectionFields.INIT_DATE, Styles.DATETIME),
        "Новый код": (CorrectionFields.NEW_CODE, None),
        "Причина изменения": (CorrectionFields.REASON, Styles.BASIC_BOARDERS),
        "Дата изменения": (CorrectionFields.NEW_DATE, Styles.DATETIME),
    },
    Table.COLUMN: {
        "A:B": 30,
        "C:C": 13,
        "D:D": 20,
        "E:E": 13,
        "F:F": 40,
        "G:G": 20,
    },
}


class ReportColumn(IntEnum):
    NUM = -1
    DAYS = 0
    SHIFT = 1
    HOURS = 2
    RATE = 3
    SALARY = 4


MONTH_HEADER = "Числа месяца ({} {})", Styles.HEADER_REPORT
report_table = {
    Table.DESC: {
        "№": (ReportColumn.NUM, Styles.BASIC_CENTER_REPORT),
        "ФИО": (User.fullname, Styles.BOLD_CENTER_REPORT),
        "Должность": (WorkerProfile.job, Styles.BOLD_CENTER_REPORT),
        ReportColumn.DAYS: (WorkerPositionActual.activity_id, None),
        "Итого смен отработанных": (ReportColumn.SHIFT, Styles.BASIC_CENTER_REPORT),
        "Отработано часов": (ReportColumn.HOURS, Styles.BASIC_CENTER_REPORT),
        "Ставка": (WorkerProfile.rate, Styles.BASIC_CENTER_REPORT),
        "З/П": (ReportColumn.SALARY, Styles.BOLD_CENTER_REPORT),
    },
    Table.COLUMN: {
        "A:A": 8,
        "B:B": 50,
        "C:C": 30,
        ReportColumn.DAYS: 7,
        ReportColumn.SHIFT: 10,
        ReportColumn.HOURS: 10,
        ReportColumn.RATE: 10,
        ReportColumn.SALARY: 20,
    },
    Table.ROW: {0: 40, 1: 40, 2: 40, 3: 80},
}
