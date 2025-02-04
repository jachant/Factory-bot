from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import messages
from app.config.roles import Role
from app.db.requests import set_user
from app.keyboards import adminKb, masterKb, ownerKb
from app.utils import setup_logger
from app.utils.genexcel import get_disk_link
from app.utils.isowner import is_owner

logger = setup_logger(__name__)
user = Router()


@user.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """/start. Запуск бота.

    Args:
        message (Message): _description_
        state (FSMContext): _description_
    """
    logger.info(f"cmd_start (from_user={message.from_user.id})")
    await state.clear()
    user = await set_user(message.from_user.id)

    if is_owner(str(message.from_user.id)):
        user.role = Role.OWNER

    match user.role:
        case Role.MASTER:
            await message.answer(text=messages.MASTER_INSTRUCTION, reply_markup=masterKb)
        case Role.ADMIN:
            await message.answer(
                text=messages.ADMIN_INSTRUCTION.format(await get_disk_link()), reply_markup=adminKb
            )
        case Role.OWNER:
            await message.answer(
                text=messages.OWNER_INSTRUCTION.format(await get_disk_link()), reply_markup=ownerKb
            )


@user.message(Command("myid"))
async def show_id(message: Message, state: FSMContext):
    """Теневая команда для получения user_id в tg.

    Args:
        message (Message): _description_
        state (FSMContext): _description_
    """
    logger.info(f"show_id (from_user={message.from_user.id})")
    await state.clear()
    await message.answer(messages.YOUR_ID.format(message.from_user.id))


@user.callback_query(F.data == "close_kb")
async def close_list(callback: CallbackQuery, state: FSMContext):
    logger.info(f"close_list (from_user={callback.from_user.id})")
    await state.clear()
    await callback.answer()
    await callback.message.delete()
