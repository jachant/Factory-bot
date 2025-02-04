import os
from asyncio import sleep
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

import yadisk

from app.db.models import Factory
from app.utils import setup_logger
from app.utils.month import MONTHS

logger = setup_logger(__name__)


@asynccontextmanager
async def yadisk_session() -> AsyncGenerator[yadisk.AsyncClient, None]:
    client = yadisk.AsyncClient(token=os.getenv("TOKEN_YADISK"))
    yield client


TELEGRAM_API = f"https://api.telegram.org/file/bot{os.getenv('TOKEN_BOT')}/"
DESTINATION = "app:/{company}/{factory}/{master}/{year}/{month}/{day}/{time}/{number}.png"

ATTEMPTS_PHOTO_UPLOAD = 10
ATTEMPTS_SLEEP_SEC = 5


async def create_subfolders(session: yadisk.AsyncClient, destination: str):
    LIKELY_DIR = 5
    dirs = destination.split("/")[1:-1]
    likely = dirs[:LIKELY_DIR]

    filepath = "app:/"
    subpath = filepath + "/".join(likely)

    if not await session.is_dir(subpath):
        pre_subpath = filepath
        for dir in likely:
            pre_subpath += dir + "/"
            if not await session.is_dir(pre_subpath):
                await session.mkdir(pre_subpath)

    filepath = subpath
    for i in range(LIKELY_DIR, len(dirs)):
        filepath += "/" + dirs[i]
        if not await session.is_dir(filepath):
            await session.mkdir(filepath)

    if not await session.is_public_dir(filepath):
        await session.publish(filepath)
    meta = await session.get_meta(filepath, fields="public_url")
    return meta.FIELDS.get("public_url")


async def upload_photos(
    photo_paths: list[str], factory: Factory, username: str, current: datetime
) -> str:
    logger.info(f"Загрузка фото {photo_paths} на диск")

    link = ""

    for i, path in enumerate(photo_paths):
        destination = DESTINATION.format(
            company=factory.company_name,
            factory=factory.factory_name,
            master=username,
            year=current.year,
            month=MONTHS.get(current.month),
            day=current.strftime("%d"),
            time=current.strftime("%H-%M-%S"),
            number=i + 1,
        )
        attempts = 0
        while attempts < ATTEMPTS_PHOTO_UPLOAD:
            attempts += 1
            try:
                async with yadisk_session() as session:
                    if not i:
                        link = await create_subfolders(session, destination)
                        if not link:
                            raise Exception("Пустая ссылка на диск с табелем")
                    await session.upload_url(TELEGRAM_API + path, destination)
            except Exception as e:
                logger.error(
                    f"Не удалось загрузить фото ({path}) на Яндекс Диск. \
Пробуем ещё раз ({attempts}/{ATTEMPTS_PHOTO_UPLOAD})...\n:{e}"
                )
                await sleep(ATTEMPTS_SLEEP_SEC)
            else:
                break
        if attempts == ATTEMPTS_PHOTO_UPLOAD:
            logger.debug("Досрочное завершение цикла по загрузке фото")
            break

    return link


disk_link_hash = ""


async def get_disk_link() -> str:
    logger.info("Получение ссылки на диск")
    global disk_link_hash
    if disk_link_hash:
        logger.debug("Ссылка на диск существует, возвращаем хеш")
        return disk_link_hash
    try:
        async with yadisk_session() as session:
            if not await session.is_public_dir("app:/"):
                await session.publish("app:/")
            meta = await session.get_meta("app:/", fields="public_url")
            disk_link_hash = meta.FIELDS.get("public_url", "")
            return disk_link_hash
    except Exception as ex:
        logger.error(f"Не удалось получить ссылку на диск:\n{ex}")
        return ""
