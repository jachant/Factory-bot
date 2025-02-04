from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove, TelegramObject

from app import keyboards as kb
from app.config import labels, messages
from app.config.db import UserLen
from app.config.roles import Role
from app.db import requests
from app.db.exceptions import BadKeyError
from app.db.models import User
from app.db.requests import update_user
from app.filters import RoleFilter
from app.states import PickAdmin
from app.utils import setup_logger
from app.utils.isowner import is_owner
from app.utils.uploader import get_disk_link

logger = setup_logger(__name__)

owner = Router()  # Создаем экземпляр Router

owner.message.filter(RoleFilter(Role.OWNER))


@owner.message(F.text == labels.EDITING)
async def editing_menu(message: Message, state: FSMContext):
    logger.info(f"editing_menu (from_user={message.from_user.id})")
    await state.clear()
    await message.reply(text=messages.EDITING_MENU, reply_markup=kb.editingKb)


@owner.message(F.text == labels.MAIN_MENU)
async def back_main_menu(message: Message, state: FSMContext):
    logger.info(f"back_main_menu (from_user={message.from_user.id})")
    await state.clear()
    await message.reply(text=messages.RETURN_TO_MAIN_MENU, reply_markup=kb.ownerKb)


@owner.message(F.text == labels.INSTRUCTION_BUTTON)
async def owner_instruction(message: Message, state: FSMContext):
    logger.info(f"owner_instruction (from_user={message.from_user.id})")
    await message.reply(
        text=messages.OWNER_INSTRUCTION.format(await get_disk_link()), reply_markup=kb.ownerKb
    )


# Управление админами
@owner.message(F.text == labels.ADMIN_MANAGE)
@owner.callback_query(F.data == f"return_manage_{Role.ADMIN}")
async def editing_admins(event: TelegramObject, state: FSMContext):
    logger.info(f"editing_admins (from_user={event.from_user.id})")
    await state.clear()
    # Если событие - это callback_query, то вызываем answer()
    if isinstance(event, CallbackQuery):
        await event.answer()

        await event.message.edit_text(text=messages.CHOOSE_OPTION, reply_markup=kb.adminManageKb)
    else:
        await event.reply(text=messages.CHOOSE_OPTION, reply_markup=kb.adminManageKb)


@owner.callback_query(F.data == "add_admin")
async def add_admin_id(callback: CallbackQuery, state: FSMContext):
    logger.info(f"add_admin_id (from_user={callback.from_user.id})")
    await state.clear()
    await state.set_state(PickAdmin.id)
    await callback.answer()
    await callback.message.edit_text(text=messages.ADMIN_ADD_TEXT, reply_markup=None)
    await callback.message.answer(text=messages.ENTER_ADMIN_ID)


@owner.message(PickAdmin.id)
async def add_admin_name(message: Message, state: FSMContext):
    logger.info(f"add_admin_name (from_user={message.from_user.id})")
    await state.update_data(id=message.text)
    await state.set_state(PickAdmin.name)
    await message.answer(text=messages.ENTER_ADMIN_NAME)


@owner.message(PickAdmin.name)
async def admin_add_confirm(message: Message, state: FSMContext):
    logger.info(f"admin_add_confirm (from_user={message.from_user.id})")
    admin_name = message.text[: UserLen.fullname]
    await state.update_data(name=admin_name)
    try:
        data = await state.get_data()
        user_info = await message.bot.get_chat(data.get("id"))
        await message.answer(
            text=messages.ADMIN_ADD_CONF.format(user_info.username, data.get("name")),
            reply_markup=kb.confirmAdminAdd,
        )
    except TelegramBadRequest:
        logger.debug("tg id не существует")
        await message.answer(text=messages.TG_ID_NOT_EXIST, reply_markup=kb.editingKb)
        await state.clear()
    except Exception as ex:
        logger.error(f"Ошибка добавления админа:\n{ex}")


@owner.callback_query(F.data == "add_admin_denied", PickAdmin.name)
async def add_admin_denied(callback: CallbackQuery, state: FSMContext):
    logger.info(f"add_admin_denied (from_user={callback.from_user.id})")
    await state.clear()
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(text=messages.CANCEL_ADD, reply_markup=kb.editingKb)


@owner.callback_query(F.data == "add_admin_confirm", PickAdmin.name)
async def add_admin_confirm(callback: CallbackQuery, state: FSMContext):
    logger.info(f"add_admin_confirm (from_user={callback.from_user.id})")
    data = await state.get_data()
    try:
        tg_id = int(data.get("id"))
        potential_admin = await requests.get_user(tg_id)
        if (potential_admin.role >= Role.ADMIN) or is_owner(str(tg_id)):
            logger.debug("Роль юзера >= админа")
            await callback.message.answer(text=messages.INCORRECT_TG_ID)
            return
        await update_user(tg_id, {User.fullname: data.get("name"), User.role: Role.ADMIN})
        await callback.message.answer(text=messages.CONFIRM_ADD, reply_markup=kb.editingKb)

        await callback.message.bot.send_message(
            chat_id=data.get("id"),
            text=messages.GIVE_ADMIN_ROLE.format(data.get("name")),
            reply_markup=kb.adminKb,
        )
    except BadKeyError:
        logger.debug("Юзер не нажимал /start")
        await callback.message.answer(text=messages.DOESNT_EXIST, reply_markup=kb.editingKb)
    except Exception as ex:
        logger.error(f"Невохможно добавить админа:\n{ex}")
    finally:
        await state.clear()
        await callback.answer()
        await callback.message.edit_reply_markup(reply_markup=None)


@owner.callback_query(F.data == "list_admins")
async def admin_list(callback: CallbackQuery, state: FSMContext):
    logger.info(f"admin_list (from_user={callback.from_user.id})")
    reply_markup = await kb.get_list_by_role(Role.ADMIN, 1, callback.message.bot)
    if not reply_markup:
        logger.debug("Список пуст")
        await callback.answer(labels.EMPTY_LIST, show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(text=labels.ADMIN_LIST, reply_markup=reply_markup)


@owner.callback_query(F.data.startswith(f"page_{Role.ADMIN}_"))
async def show_admin_list_page(callback: CallbackQuery, state: FSMContext):
    logger.info(f"show_admin_list_page (from_user={callback.from_user.id})")
    reply_markup = await kb.get_list_by_role(
        Role.ADMIN, int(callback.data.split("_")[-1]), callback.bot
    )
    if not reply_markup:
        logger.debug("Список пуст")
        await callback.answer(labels.EMPTY_LIST, show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(text=labels.ADMIN_LIST, reply_markup=reply_markup)


@owner.callback_query(F.data.startswith(f"{Role.ADMIN}_"))
async def admin_info(callback: CallbackQuery, state: FSMContext):
    logger.info(f"admin_info (from_user={callback.from_user.id})")
    await callback.answer()
    id = int(callback.data.split("_")[1])
    page = int(callback.data.split("_")[2])

    user = await requests.get_user(id, use_tg=False)
    user_tg_info = await callback.bot.get_chat(user.tg_id)
    await callback.message.edit_text(
        text=messages.ADMIN_INFO.format(user.fullname, user_tg_info.username),
        reply_markup=await kb.manage_people(Role.ADMIN, user_tg_id=user.tg_id, back_page=page),
    )


@owner.callback_query(F.data.startswith(f"dismiss_{Role.ADMIN}_"))
async def dismiss_admin(callback: CallbackQuery, state: FSMContext):
    logger.info(f"dismiss_admin (from_user={callback.from_user.id})")
    await callback.answer()
    user_tg_id = int(callback.data.split("_")[2])

    user = await requests.get_user(user_tg_id)
    user_tg_info = await callback.bot.get_chat(user_tg_id)
    await callback.message.edit_text(
        text=messages.DELETE_ADMIN.format(user.fullname, user_tg_info.username),
        reply_markup=await kb.person_delete(Role.ADMIN, user_tg_id),
    )


@owner.callback_query(F.data.startswith("confirm_dismiss_"))
async def confirm_dismiss_admin(callback: CallbackQuery, state: FSMContext):
    logger.info(f"confirm_dismiss_admin (from_user={callback.from_user.id})")
    await callback.answer()
    user_tg_id = int(callback.data.split("_")[3])

    await requests.update_user(user_tg_id, {User.role: Role.USER})
    try:
        await callback.message.edit_text(text=messages.ADMIN_DELETED, reply_markup=None)
        await callback.bot.send_message(
            chat_id=user_tg_id, text=messages.YOU_DISMISSED, reply_markup=ReplyKeyboardRemove()
        )
    except Exception as ex:
        logger.error(f"confirm_dismiss\n{ex}")
