from aiogram.filters import Filter
from aiogram.types import Message

from app.config.roles import Role
from app.db.exceptions import BadKeyError
from app.db.requests import get_user
from app.utils.isowner import is_owner


class RoleFilter(Filter):
    """Фильтрация сообщений по роли.

    Args:
        role (Role): Роль.
    """

    def __init__(self, role: Role):
        self.role = role

    async def __call__(self, message: Message) -> bool:
        """Фильтрация роли.

        Args:
            message (Message): Объект сообщения.

        Returns:
            bool: Доступность для заданной роли.
        """

        if is_owner(str(message.from_user.id)) and self.role >= Role.ADMIN:
            return True
        try:
            user = await get_user(message.from_user.id)
            # User.role является числом
            return user.role == self.role
        except BadKeyError:
            return False
