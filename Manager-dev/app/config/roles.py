from enum import IntEnum


class Role(IntEnum):
    """Класс IntEnum ролей пользователей."""

    USER = 1
    WORKER = 2
    MASTER = 4
    ADMIN = 16
    OWNER = 32

    @property
    def name(self):
        """Переопределение property.

        Returns:
            str: Name in lower case
        """
        return super().name.lower()
