from aiogram.types import ContentType, Message


async def get_files(messages: list[Message]) -> list[str]:
    """Получение пути файлов из объектов Message

    Args:
        messages (list[Message]): Список сообщений.

    Returns:
        list: Список путей файлов.
    """
    res = []

    for msg in messages:
        msg_type: ContentType = msg.content_type
        file_info = None
        if msg_type == ContentType.PHOTO:
            file_info = getattr(msg, msg_type.value)[-1]

        if file_info:
            res.append(file_info.file_id)
    return res
