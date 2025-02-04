from datetime import date

MONTHS = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}


def get_month_by_name(name: str) -> int:
    return next(
        (key for key, value in MONTHS.items() if value.lower() == name.strip().lower()), None
    )


class Month:
    class Next:
        def __init__(self):
            current = date.today()
            self._month = current.month
            self._year = current.year

            if self._month == 12:
                self._month = 1
                self._year += 1
            else:
                self._month += 1

        @property
        def month(self) -> int:
            return self._month

        @property
        def year(self) -> int:
            return self._year

    class Current:
        def __init__(self):
            current = date.today()
            self._month = current.month
            self._year = current.year

        @property
        def month(self) -> int:
            return self._month

        @property
        def year(self) -> int:
            return self._year

    class Prev:
        def __init__(self):
            current = date.today()
            self._month = current.month
            self._year = current.year

            if self._month == 1:
                self._month = 12
                self._year -= 1
            else:
                self._month -= 1

        @property
        def month(self) -> int:
            return self._month

        @property
        def year(self) -> int:
            return self._year
