import asyncio
from typing import Any, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

from app.utils import setup_logger

logger = setup_logger(__name__)


class AlbumMiddleware(BaseMiddleware):
    """Middleware для обработки альбомов.

    Args:
        BaseMiddleware (_type_): _description_
    """

    def __init__(self, latency: float = 0.5):
        """Инициализация middleware для обработки альбомов.

        Args:
            latency (float, optional): Задержка между сообщениями в группе. Defaults to 0.5.
        """
        logger.info("Инициализация middleware для обработки альбомов")
        self.latency = latency
        self.album_data: Dict[str, list] = {}
        super().__init__()

    async def __call__(self, handler: Callable, event: Message, data: Dict[str, Any]):
        if not event.media_group_id:
            return await handler(event, data)
        logger.info("Обнаружено медиа в сообщении")
        try:
            self.album_data[event.media_group_id].append(event)

        except KeyError:
            logger.info("Добавление первого медиа")
            self.album_data[event.media_group_id] = [event]
            await asyncio.sleep(self.latency)

            data["is_last"] = True
            data["album"] = self.album_data[event.media_group_id]

            return await handler(event, data)

    async def after(self, handler, event: Message, data: Dict[str, Any]):
        if event.media_group_id and data.get("is_last"):
            logger.info("Освобождение данных")
            del self.album_data[event.media_group_id]
