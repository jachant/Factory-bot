from datetime import date

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InputMediaDocument,
    Message,
    ReplyKeyboardRemove,
    TelegramObject,
)

from app import keyboards as kb
from app.config import labels, messages
from app.config.db import ActivityLen, FactoryLen, UserLen, WorkerProfileLen
from app.config.roles import Role
from app.db import requests
from app.db.exceptions import AlreadyExistsError, BadFormatError, BadKeyError
from app.db.models import CorrectionLen, User, WorkerProfile
from app.filters import RoleFilter
from app.states import (
    AddMaster,
    ChangeJob,
    ChangeRate,
    EditShift,
    PickActivityCode,
    PickFactory,
    PickWorker,
    SaveReport,
    ShiftReport,
)
from app.utils import setup_logger
from app.utils.chatTools import get_files
from app.utils.genexcel import GeneratorExcel
from app.utils.isowner import is_owner
from app.utils.month import MONTHS, Month, get_month_by_name
from app.utils.uploader import get_disk_link

logger = setup_logger(__name__)

admin = Router()

admin.message.filter(RoleFilter(Role.ADMIN))


# Переход в меню редактирования админов
@admin.message(F.text == labels.ADMIN_EDITING)
async def admin_aditing_keyboard(message: Message, state: FSMContext):
    logger.info(f"admin_aditing_keyboard (from_user={message.from_user.id})")
    await state.clear()
    await message.reply(text=messages.EDITING_MENU, reply_markup=kb.admin_editing_kb)


# Инструкция админа
@admin.message(F.text == labels.ADMIN_INSTRUCTION)
async def owner_instruction(message: Message, state: FSMContext):
    logger.info(f"owner_instruction (from_user={message.from_user.id})")
    await message.reply(
        text=messages.ADMIN_INSTRUCTION.format(await get_disk_link()), reply_markup=kb.adminKb
    )


# Возврат в главное меню админа
@admin.message(F.text == labels.ADMIN_MAIN_MENU)
async def admin_main_menu(message: Message, state: FSMContext):
    logger.info(f"admin_main_menu (from_user={message.from_user.id})")
    await state.clear()
    await message.reply(text=labels.ADMIN_MAIN_MENU, reply_markup=kb.adminKb)


# Управление мастерами
@admin.message(F.text == labels.MASTERS_MANAGE)
@admin.callback_query(F.data == f"return_manage_{Role.MASTER}")
@admin.callback_query(F.data.startswith(f"new_master_return_manage_{Role.WORKER}"))
async def master_manage_menu(event: TelegramObject, state: FSMContext):
    logger.info(f"master_manage_menu (from_user={event.from_user.id})")
    await state.clear()

    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(text=labels.MASTERS_MANAGE, reply_markup=kb.masterManageKb)
    else:
        await event.reply(text=messages.CHOOSE_OPTION, reply_markup=kb.masterManageKb)


# Управление работниками
@admin.callback_query(F.data == f"return_manage_{(Role.WORKER | Role.MASTER)}")
@admin.message(F.text == labels.EMPLOYEE_MANAGE)
async def workers_menu(event: TelegramObject, state: FSMContext):
    logger.info(f"workers_menu (from_user={event.from_user.id})")
    await state.clear()

    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(
            text=labels.EMPLOYEE_MANAGE, reply_markup=kb.workers_manage_kb
        )
    else:
        await event.reply(text=messages.CHOOSE_OPTION, reply_markup=kb.workers_manage_kb)


# Управление заводами
@admin.message(F.text == labels.FACTORIES_MANAGE)
@admin.callback_query(F.data == "return_factories")
async def factories_manage(event: TelegramObject, state: FSMContext):
    logger.info(f"factories_manage (from_user={event.from_user.id})")
    await state.clear()
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(
            text=messages.CHOOSE_OPTION, reply_markup=kb.factories_manage
        )
    else:
        await event.reply(text=messages.CHOOSE_OPTION, reply_markup=kb.factories_manage)


# Редактировать коды деятельности
@admin.message(F.text == labels.EDIT_CODES)
async def activity_code(message: Message, state: FSMContext):
    logger.info(f"activity_code (from_user={message.from_user.id})")
    await state.clear()
    await message.reply(text=messages.ACTIVITY_CODES, reply_markup=kb.activity_code_kb)


# Редактирование отчета о смене
@admin.message(F.text == labels.EDIT_SHIFT)
@admin.callback_query(F.data == "edit_shift_factory_")
async def edit_shift_choose_factory(event: TelegramObject, state: FSMContext):
    logger.info(f"edit_shift_choose_factory (from_user={event.from_user.id})")
    await state.clear()
    reply_markup = await kb.get_factory_list(key="edit_shift_")
    if not reply_markup:
        logger.debug("Нет предприятий")
        if isinstance(event, CallbackQuery):
            await event.message.edit_reply_markup(None)
            await event.answer(labels.NO_FACTORIES, show_alert=True)
        else:
            await event.reply(labels.NO_FACTORIES)
        return
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(
            text=messages.CHOOSE_FACTORY_FOR_EDIT_SHIFT, reply_markup=reply_markup
        )
    else:
        await event.answer(text=messages.CHOOSE_FACTORY_FOR_EDIT_SHIFT, reply_markup=reply_markup)


@admin.callback_query(F.data.startswith("edit_shift_factory_"))
async def edit_shift_choose_master(callback: CallbackQuery, state: FSMContext):
    logger.info(f"edit_shift_choose_master (from_user={callback.from_user.id})")
    factory_id = callback.data.split("_")[-1]

    factory = await requests.get_factory(int(factory_id))
    reply_markup = await kb.factory_master_list(factory_id=factory_id, key="edit_shift_")

    await callback.message.edit_text(
        text=messages.FACTORY_CHOOSE.format(factory.factory_name), reply_markup=None
    )

    if not reply_markup:
        logger.debug("Нет мастеров на предприятии")
        await callback.answer(labels.NO_MASTERTS, show_alert=True)
        return

    await callback.answer()

    await callback.message.answer(
        text=messages.CHOOSE_MASTER_FOR_EDIT_SHIFT, reply_markup=reply_markup
    )


@admin.callback_query(F.data.startswith(f"edit_shift_{Role.MASTER}_"))
async def edit_shift_choose_date(callback: CallbackQuery, state: FSMContext):
    logger.info(f"edit_shift_choose_date (from_user={callback.from_user.id})")
    await callback.answer()
    master_id = callback.data.split("_")[-3]
    factory_id = callback.data.split("_")[-1]
    await state.update_data(factory_id=factory_id, master_id=master_id)
    user = await requests.get_user(int(master_id), use_tg=False)
    await callback.message.edit_text(
        text=messages.MASTER_CHOOSE.format(user.fullname), reply_markup=None
    )
    await state.set_state(EditShift.await_date)
    await callback.message.answer(
        text=messages.ENTER_STATE_DATE,
        reply_markup=await kb.back_to_edit_shift_factory(factory_id),
    )


@admin.message(EditShift.await_date)
async def edit_shift_choose_shift(message: Message, state: FSMContext):
    logger.info(f"edit_shift_choose_shift (from_user={message.from_user.id})")
    data = await state.get_data()
    try:
        # Разбиваем текст на день, месяц, год
        day, month, year = map(int, message.text.split("."))
        formated_date = date(year=year, month=month, day=day)  # Проверяем корректность даты
    except (ValueError, AttributeError):
        # Отправляем сообщение об ошибке
        await message.answer(
            labels.WRONG_DATE,
            reply_markup=await kb.back_to_edit_shift_factory(data.get("factory_id")),
        )
        logger.debug("Введена некорректная дата")
        return

    await state.update_data(date=message.text)

    reply_markup = await kb.get_shift_list(
        data.get("master_id"), data.get("factory_id"), formated_date
    )

    if not reply_markup:
        logger.debug("Нет отчетов в этот день")
        await message.answer(
            labels.NO_SHIFT_FOR_MASTRER,
            reply_markup=await kb.back_to_edit_shift_factory(data.get("factory_id")),
        )
        return
    await state.set_state(EditShift.have_date)
    await message.answer(text=messages.CHOOSE_SHIFT_FOR_EDIT_SHIFT, reply_markup=reply_markup)


@admin.callback_query(F.data.startswith("edit_shift_number_"))
async def edit_shift_choose_worker(callback: CallbackQuery, state: FSMContext):
    logger.info(f"edit_shift_choose_worker (from_user={callback.from_user.id})")
    await callback.answer()
    shift_id = callback.data.split("_")[-1]
    shift_time = callback.data.split("_")[-2]
    await state.update_data(shift_id=shift_id, shift_time=shift_time)
    logger.debug(await state.get_data())

    reply_markup = await kb.get_workers_by_shift(shift_id=shift_id)

    await callback.message.edit_text(
        text=messages.SHIFT_TIME.format(shift_time), reply_markup=None
    )
    await callback.message.answer(text=messages.CHOOSE_WORKER, reply_markup=reply_markup)


@admin.callback_query(F.data.startswith("shift_pos_worker_"))
async def edit_shift_choose_new_activity(callback: CallbackQuery, state: FSMContext):
    logger.info(f"edit_shift_choose_new_activity (from_user={callback.from_user.id})")
    await callback.answer()
    _, _, _, pos_id, old_activity_id, worker_id = callback.data.split("_")
    await state.update_data(pos_id=pos_id, old_activity=old_activity_id, worker_id=worker_id)
    user = await requests.get_user(int(worker_id), use_tg=False)

    reply_markup = await kb.get_activity_list(1, key="edit_shift_")
    activity = await requests.get_activity(int(old_activity_id))
    await callback.message.edit_text(
        text=messages.WORKER_OLD_ACTIVITY.format(user.fullname, activity.code),
        reply_markup=reply_markup,
    )


@admin.callback_query(F.data.startswith("edit_shift_page_actlist_"))
async def edit_shift_choose_new_activity_page(callback: CallbackQuery, state: FSMContext):
    logger.info(f"edit_shift_choose_new_activity_page (from_user={callback.from_user.id})")
    await callback.answer()
    page = callback.data.split("_")[-1]
    reply_markup = await kb.get_activity_list(int(page), key="edit_shift_")
    await callback.message.edit_reply_markup(reply_markup=reply_markup)


@admin.callback_query(F.data.startswith("edit_shift_activity_"))
async def edit_shift_enter_explanation(callback: CallbackQuery, state: FSMContext):
    logger.info(f"edit_shift_enter_explanation (from_user={callback.from_user.id})")
    await callback.answer()
    new_activity_id = callback.data.split("_")[-2]
    await state.update_data(new_activity=new_activity_id)
    await state.set_state(EditShift.explanation)

    new_activity = await requests.get_activity(int(new_activity_id))
    await callback.message.edit_text(
        text=messages.NEW_ACTIVITY.format(new_activity.code), reply_markup=None
    )
    await callback.message.answer(text=messages.ENTER_EXPLANATION)


@admin.message(EditShift.explanation)
async def confirm_edit_shift(message: Message, state: FSMContext):
    logger.info(f"confirm_edit_shift (from_user={message.from_user.id})")
    explanation = message.text[: CorrectionLen.reason]
    await state.update_data(explanation=explanation)
    await state.set_state(EditShift.confirm)

    data = await state.get_data()
    factory_id = data.get("factory_id")
    factory = await requests.get_factory(int(factory_id))
    master_id = data.get("master_id")
    master = await requests.get_user(int(master_id), use_tg=False)
    date = data.get("date")
    shift_time = data.get("shift_time")
    worker_id = data.get("worker_id")
    worker = await requests.get_user(int(worker_id), use_tg=False)
    old_activity_id = data.get("old_activity")
    new_activity_id = data.get("new_activity")
    explanation = data.get("explanation")

    old_activity = await requests.get_activity(int(old_activity_id))
    new_activity = await requests.get_activity(int(new_activity_id))
    text = messages.CONFIRM_SHIFT_EDIT.format(
        factory.factory_name,
        master.fullname,
        date,
        shift_time,
        worker.fullname,
        old_activity.code,
        new_activity.code,
        explanation,
    )

    await message.answer(text=text, reply_markup=kb.confirm_edit_shift)


@admin.callback_query(F.data == "confirm_edit_shift_report")
async def shift_editing(callback: CallbackQuery, state: FSMContext):
    logger.info(f"shift_editing (from_user={callback.from_user.id})")
    await callback.answer()
    data = await state.get_data()
    await state.clear()
    explanation = data.get("explanation")
    pos_id = data.get("pos_id")
    new_activity = data.get("new_activity")

    logger.debug(data)

    await requests.correct_worker_position(
        tg_id=callback.from_user.id,
        worker_position_id=int(pos_id),
        new_activity_id=int(new_activity),
        reason=explanation,
    )

    await callback.message.edit_reply_markup(None)
    await callback.message.answer(text=messages.CHANGE_SAVE)


@admin.callback_query(F.data == "not_confirm_edit_shift_report")
async def shift_edit_not_save(callback: CallbackQuery, state: FSMContext):
    logger.info(f"shift_edit_not_save (from_user={callback.from_user.id})")
    await callback.answer()
    await state.clear()

    await callback.message.edit_reply_markup(None)
    await callback.message.answer(text=messages.REPORT_CHANGE_NOT_SAVE)


# Выгрузка отчёта
@admin.message(F.text == labels.SAVE_REPORT)
@admin.callback_query(F.data == "reportreturn_factories")
async def save_report(event: TelegramObject, state: FSMContext):
    logger.info(f"save_report (from_user={event.from_user.id})")
    await state.clear()
    factories = await requests.get_factories()
    if not factories:
        if isinstance(event, CallbackQuery):
            await event.message.reply(text=messages.NO_FACTORIES)
        else:
            await event.reply(text=messages.NO_FACTORIES)
        return
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.edit_text(text=labels.SAVE_REPORT, reply_markup=None)
        await event.message.reply(
            text=messages.CHOOSE_MONTH, reply_markup=await kb.report_date_list()
        )
    else:
        await event.reply(text=messages.CHOOSE_MONTH, reply_markup=await kb.report_date_list())


@admin.callback_query(F.data.startswith("reportdate_"))
async def choose_report_date(callback: CallbackQuery, state: FSMContext):
    logger.info(f"choose_report_date (from_user={callback.from_user.id})")
    await state.clear()
    await callback.answer()
    data = callback.data.split("_")
    if len(data) == 3:
        await callback.message.edit_text(
            text=messages.CHOOSEN_MONTH.format(MONTHS.get(int(data[2])).lower()), reply_markup=None
        )
        await state.set_data({SaveReport.year: int(data[1]), SaveReport.month: int(data[2])})
        await state.set_state(SaveReport.factory_id)
        await callback.message.answer(
            text=messages.CHOOSE_FACTORY_REPORT, reply_markup=await kb.get_factory_list("report")
        )
    else:
        await callback.message.edit_text(
            text=messages.CHOOSEN_MONTH.format(labels.ANOTHER.lower()), reply_markup=None
        )
        await state.set_state(SaveReport.year)
        await callback.message.answer(text=messages.TYPE_MONTH)


@admin.message(SaveReport.year)
async def input_year_month(message: Message, state: FSMContext):
    logger.info(f"input_year_month (from_user={message.from_user.id})")
    data = message.text.split()
    if len(data) != 2:
        await state.clear()
        await message.reply(text=messages.INCORRECT_DATA)
        return
    try:
        year = int(data[0])
        month = get_month_by_name(data[1])
        if not month:
            raise ValueError
        await state.set_data({SaveReport.year: year, SaveReport.month: month})
        await state.set_state(SaveReport.factory_id)
        await message.answer(
            text=messages.CHOOSE_FACTORY_REPORT, reply_markup=await kb.get_factory_list("report")
        )
    except Exception:
        logger.debug("Неправильный формат даты")
        await state.clear()
        await message.reply(text=messages.INCORRECT_DATA)


@admin.callback_query(F.data.startswith("reportfactory_"), StateFilter(SaveReport.factory_id))
async def choose_factory_report(callback: CallbackQuery, state: FSMContext):
    logger.info(f"choose_factory_report (from_user={callback.from_user.id})")
    await callback.answer()
    await callback.message.edit_text(text=messages.REPORT_PROCESS, reply_markup=None)
    data = await state.get_data()
    await state.clear()
    factory_id = callback.data.split("_")[1]
    objs = []
    try:
        if factory_id:
            excel = GeneratorExcel(
                int(factory_id), data.get(SaveReport.year), data.get(SaveReport.month)
            )
            objs.append((await excel.generate(), excel))
        else:
            factories = await requests.get_factories()
            for factory in factories:
                excel = GeneratorExcel(
                    factory.id, data.get(SaveReport.year), data.get(SaveReport.month)
                )
                objs.append((await excel.generate(), excel))
        media_group = []
        for obj in objs:
            filepath = obj[0]
            media_group.append(InputMediaDocument(media=FSInputFile(filepath)))
        await callback.bot.send_media_group(chat_id=callback.from_user.id, media=media_group)

    except Exception as ex:
        logger.error(f"Невозможно отправить отчёт:\n{ex}")
        await callback.message.answer(text=messages.CANT_GENERATE_REPORT)
    finally:
        logger.debug("Очищение сгенерированных файлов")
        for obj in objs:
            await obj[1].free()


# ---


# Удаление работника
@admin.callback_query(F.data.startswith("denied_dismiss_"))
async def denied_dismiss(callback: CallbackQuery, state: FSMContext):
    logger.info(f"denied_dismiss (from_user={callback.from_user.id})")
    await callback.answer()
    await callback.message.edit_text(text=messages.DISMISS_DENIED, reply_markup=None)


# Управление мастерами
@admin.callback_query(F.data.startswith("new_master_return_factories"))
@admin.callback_query(F.data == "add_master")
async def add_master(callback: CallbackQuery, state: FSMContext):
    logger.info(f"add_master (from_user={callback.from_user.id})")
    await state.clear()
    reply_markup = await kb.get_list_by_role(
        role=Role.WORKER, cur_page=1, bot=callback.bot, key="new_master_"
    )
    if not reply_markup:
        logger.debug("Нет работников")
        await callback.answer(labels.NO_WORKERS, show_alert=True)
        return
    if not await requests.get_factories():
        logger.debug("Нет заводов")
        await callback.answer(labels.NO_FACTORIES, show_alert=True)
        return
    await callback.answer()
    await state.set_state(AddMaster.id)
    await callback.message.edit_text(text=messages.CHOOSE_NEW_MASTER, reply_markup=reply_markup)


@admin.callback_query(F.data.startswith(f"new_master_{Role.WORKER}_"))
async def add_master_choose_worker(callback: CallbackQuery, state: FSMContext):
    logger.info(f"add_master_choose_worker (from_user={callback.from_user.id})")
    await callback.answer()
    id = callback.data.split("_")[3]
    await state.update_data(id=id)
    await state.set_state(AddMaster.factory_id)
    reply_markup = await kb.get_factory_list(key="new_master_")
    await callback.message.edit_text(
        text=messages.CHOOSE_FACTORY_FOR_MASTER, reply_markup=reply_markup
    )


# пролистывание страницы
@admin.callback_query(F.data.startswith(f"new_master_page_{Role.WORKER}_"))
async def add_master_choose_factory_scrolling(callback: CallbackQuery, state: FSMContext):
    logger.info(f"add_master_choose_factory_scrolling (from_user={callback.from_user.id})")
    reply_markup = await kb.get_list_by_role(
        Role.WORKER, int(callback.data.split("_")[-1]), callback.bot, key="new_master_"
    )
    if not reply_markup:
        logger.debug("Список пуст")
        await callback.answer(labels.EMPTY_LIST, show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(text=messages.CHOOSE_NEW_MASTER, reply_markup=reply_markup)


@admin.callback_query(F.data.startswith("new_master_factory_"))
async def add_master_enter_tg_id(callback: CallbackQuery, state: FSMContext):
    logger.info(f"add_master_enter_tg_id (from_user={callback.from_user.id})")
    await callback.answer()
    await state.update_data(factory_id=callback.data.split("_")[3])
    await state.set_state(AddMaster.tg_id)
    await callback.message.edit_text(text=messages.ENTER_MASTER_ID, reply_markup=None)


@admin.message(AddMaster.tg_id)
async def confirm_new_master(message: Message, state: FSMContext):
    logger.info(f"confirm_new_master (from_user={message.from_user.id})")
    await state.update_data(tg_id=message.text)
    data = await state.get_data()
    await state.clear()
    user = await requests.get_user(int(data.get("id")), use_tg=False)
    factory = await requests.get_factory(int(data.get("factory_id")))
    try:
        potential_master = await requests.get_user(int(data.get("tg_id")))
        if potential_master.role >= Role.ADMIN or is_owner(data.get("tg_id")):
            logger.debug("Роль юзера >= админа")
            await message.answer(text=messages.INCORRECT_TG_ID, reply_markup=None)
            return
        elif potential_master.role == Role.USER or potential_master.id == user.id:
            logger.debug("Юзер удовлетворяет всем условиями")
            chat = await message.bot.get_chat(data.get("tg_id"))
            text = messages.CONFIRM_ADD_MASTER.format(
                user.fullname, factory.factory_name, chat.username
            )
        else:
            logger.debug("Юзер с таким id уже существует")
            await message.answer(
                text=messages.ALREADY_EXISTS_USER.format(potential_master.fullname),
                reply_markup=None,
            )
            return
    except ValueError as ex:
        logger.warning(f"Некорректный tg id:\n{ex}")
        await message.answer(text=messages.INCORRECT_TG_ID, reply_markup=None)
        return

    except Exception as ex:
        logger.warning(f"Юзер не нажимал /start:\n{ex}")
        await message.answer(text=messages.DOESNT_EXIST, reply_markup=None)
        return

    reply_markup = await kb.confirm_add_master(
        data.get("id"),
        data.get("factory_id"),
        data.get("tg_id"),
    )
    await message.answer(text=text, reply_markup=reply_markup)


@admin.callback_query(F.data.startswith("confirm_add_master_"))
async def add_master_confirmed(callback: CallbackQuery, state: FSMContext):
    logger.info(f"add_master_confirmed (from_user={callback.from_user.id})")
    _, _, _, id, factory_id, tg_id = callback.data.split("_")
    print(id, tg_id, factory_id)
    try:
        await requests.update_user(
            int(id), {User.tg_id: int(tg_id), User.role: Role.MASTER}, use_tg=False
        )
        await requests.set_factory_to_master(int(id), int(factory_id))
        await callback.message.answer(text=messages.CONFIRM_ADD)
        user = await requests.get_user(int(id), use_tg=False)

        await callback.message.bot.send_message(
            chat_id=tg_id,
            text=messages.GIVE_MASTER_ROLE.format(user.fullname),
            reply_markup=kb.masterKb,
        )
    except BadKeyError:
        logger.debug("Юзер не нажимал /start")
        await callback.message.answer(text=messages.DOESNT_EXIST, reply_markup=None)
    except Exception as ex:
        logger.error(f"Невозможно добавить мастера:\n{ex}")
    finally:
        await state.clear()
        await callback.answer()
        await callback.message.edit_reply_markup(reply_markup=None)


@admin.callback_query(F.data.startswith("master_factory_edit_return_factories"))
@admin.callback_query(F.data == "list_master")
async def master_list(callback: CallbackQuery, state: FSMContext):
    logger.info(f"master_list (from_user={callback.from_user.id})")
    reply_markup = await kb.get_list_by_role(role=Role.MASTER, cur_page=1, bot=callback.bot)
    if not reply_markup:
        logger.debug("Список пуст")
        await callback.answer(labels.EMPTY_LIST, show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(text=labels.MASTER_LIST, reply_markup=reply_markup)


@admin.callback_query(F.data.startswith(f"{Role.MASTER}_"))
async def master_info(callback: CallbackQuery, state: FSMContext):
    logger.info(f"master_info (from_user={callback.from_user.id})")
    await callback.answer()

    data = callback.data.split("_")
    id = data[1]
    back_page = data[2]
    factory_id = data[3] if len(data) == 4 else None

    user = await requests.get_user(int(id), use_tg=False)
    factory = await requests.get_factory_by_user(int(id))
    chat = await callback.bot.get_chat(user.tg_id)
    text = messages.MASTER_INFO.format(user.fullname, chat.username, factory.factory_name)
    reply_markup = await kb.master_info_kb(Role.MASTER, id, back_page, factory_id)

    await callback.message.edit_text(text=text, reply_markup=reply_markup)


@admin.callback_query(F.data.startswith(f"page_{Role.MASTER}_"))
async def show_worker_list_page(callback: CallbackQuery, state: FSMContext):
    logger.info(f"show_worker_list_page (from_user={callback.from_user.id})")
    reply_markup = await kb.get_list_by_role(
        Role.MASTER, int(callback.data.split("_")[-1]), callback.bot
    )
    if not reply_markup:
        logger.debug("Список пуст")
        await callback.answer(labels.EMPTY_LIST, show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(text=labels.MASTER_LIST, reply_markup=reply_markup)


@admin.callback_query(F.data.startswith("edit_master_factory_"))
async def edit_master_factory_list(callback: CallbackQuery, state: FSMContext):
    logger.info(f"edit_master_factory_list (from_user={callback.from_user.id})")
    await callback.answer()
    await callback.message.edit_reply_markup(None)
    await state.clear()
    id = callback.data.split("_")[-1]

    await state.set_state(AddMaster.id)
    await state.update_data(id=id)
    await callback.message.answer(
        text=messages.EDIT_FACTORY_FOR_MASTER,
        reply_markup=await kb.get_factory_list(key="master_factory_edit_"),
    )


@admin.callback_query(F.data.startswith("master_factory_edit_factory_"))
async def confirm_edit_master_factory(callback: CallbackQuery, state: FSMContext):
    logger.info(f"confirm_edit_master_factory (from_user={callback.from_user.id})")
    await callback.answer()

    factory_id = callback.data.split("_")[-1]
    data = await state.get_data()
    id = data.get("id")
    await state.clear()
    user = await requests.get_user(int(id), use_tg=False)
    factory_old = await requests.get_factory_by_user(int(id))
    factory_new = await requests.get_factory(int(factory_id))

    reply_markup = await kb.confirm_edit_factory(id, factory_id)
    text = messages.EDIT_MASTER_FACTORY_CONFIRM.format(
        user.fullname, factory_old.factory_name, factory_new.factory_name
    )

    await callback.message.edit_text(text=text, reply_markup=reply_markup)


@admin.callback_query(F.data.startswith("confirm_edit_master_factory_"))
async def edit_master_factory_confirm(callback: CallbackQuery, state: FSMContext):
    logger.info(f"edit_master_factory_confirm (from_user={callback.from_user.id})")
    await callback.answer()

    id = callback.data.split("_")[-2]
    factory_id = callback.data.split("_")[-1]

    await requests.set_factory_to_master(int(id), int(factory_id))
    await callback.message.edit_text(text=messages.CONFIRM_CHANGE_FACTORY, reply_markup=None)


@admin.callback_query(F.data.startswith("remove_master_"))
async def delete_master_confirm(callback: CallbackQuery, state: FSMContext):
    logger.info(f"delete_master_confirm (from_user={callback.from_user.id})")
    await callback.answer()

    id = callback.data.split("_")[-1]
    user = await requests.get_user(int(id), use_tg=False)
    factory = await requests.get_factory_by_user(int(id))
    chat = await callback.bot.get_chat(user.tg_id)
    text = messages.CONFIRM_DELETE_MASTER.format(
        user.fullname, chat.username, factory.factory_name
    )

    await callback.message.edit_text(text=text, reply_markup=await kb.confirm_master_delete(id))


@admin.callback_query(F.data.startswith("confirm_delete_master_"))
async def remove_master(callback: CallbackQuery, state: FSMContext):
    logger.info(f"remove_master (from_user={callback.from_user.id})")
    await callback.answer()
    await callback.message.edit_reply_markup(None)

    id = callback.data.split("_")[-1]
    await requests.update_user(int(id), {User.role: Role.WORKER}, use_tg=False)
    user = await requests.get_user(int(id), use_tg=False)

    try:
        await callback.message.answer(text=messages.MASTER_REMOVED)
        await callback.bot.send_message(
            chat_id=user.tg_id, text=messages.YOU_DISMISSED, reply_markup=ReplyKeyboardRemove()
        )
    except Exception as ex:
        logger.error(f"Не удалось удалить мастера\n{ex}")


# Управление заводами
# Добавить завод
@admin.callback_query(F.data == "add_factory")
async def add_factory_company(callback: CallbackQuery, state: FSMContext):
    logger.info(f"add_factory_company (from_user={callback.from_user.id})")
    await callback.answer()
    await state.set_state(PickFactory.company_name)
    await callback.message.edit_text(text=messages.FACTORY_ADD_TEXT, reply_markup=None)
    await callback.message.answer(text=messages.ENTER_COMPANY_NAME)


@admin.message(PickFactory.company_name)
async def add_factory_name(message: Message, state: FSMContext):
    logger.info(f"add_factory_name (from_user={message.from_user.id})")
    company_name = message.text[: FactoryLen.company_name]
    await state.update_data(company_name=company_name)
    await state.set_state(PickFactory.factory_name)
    await message.answer(text=messages.ENTER_FACTORY_NAME)


@admin.message(PickFactory.factory_name)
async def add_factory_confirm(message: Message, state: FSMContext):
    logger.info(f"add_factory_confirm (from_user={message.from_user.id})")
    factory_name = message.text[: FactoryLen.factory_name]
    await state.update_data(factory_name=factory_name)

    data = await state.get_data()
    await message.answer(
        text=messages.FACTORY_ADD_CONFIRM.format(
            data.get("company_name"), data.get("factory_name")
        ),
        reply_markup=kb.confirm_factory_add,
    )


@admin.callback_query(F.data == "add_denied")
async def add_denied(callback: CallbackQuery, state: FSMContext):
    logger.info(f"add_denied (from_user={callback.from_user.id})")
    await state.clear()
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(text=messages.CANCEL_ADD)


@admin.callback_query(F.data == "add_factory_confirm")
async def add_factory(callback: CallbackQuery, state: FSMContext):
    logger.info(f"add_factory (from_user={callback.from_user.id})")
    await callback.answer()

    data = await state.get_data()
    try:
        await requests.set_factory(data.get("company_name"), data.get("factory_name"))
        await callback.message.answer(text=messages.CONFIRM_ADD, reply_markup=None)
    except AlreadyExistsError:
        logger.debug("Предприятие уже существует")
        await callback.message.answer(text=messages.ALREADY_EXISTS_FACTORY, reply_markup=None)
    finally:
        await callback.message.edit_reply_markup(reply_markup=None)
        await state.clear()


# Список заводов
@admin.callback_query(F.data == "factory_list")
async def factory_list(callback: CallbackQuery, state: FSMContext):
    logger.info(f"factory_list (from_user={callback.from_user.id})")
    reply_markup = await kb.get_factory_list()

    if not reply_markup:
        logger.debug("Список пуст")
        await callback.answer(labels.EMPTY_LIST, show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(text=labels.FACTORY_LIST, reply_markup=reply_markup)


@admin.callback_query(F.data.startswith("factory_"))
async def factory_info(callback: CallbackQuery, state: FSMContext):
    logger.info(f"factory_info (from_user={callback.from_user.id})")
    await callback.answer()
    fact_id = int(callback.data.split("_")[1])
    factory = await requests.get_factory(fact_id)
    await callback.message.edit_text(
        text=messages.FACTORY_INFO.format(factory.company_name, factory.factory_name),
        reply_markup=await kb.manage_factory(fact_id=fact_id),
    )


@admin.callback_query(F.data.startswith("delete_factory_"))
async def delete_factory(callback: CallbackQuery, state: FSMContext):
    logger.info(f"delete_factory (from_user={callback.from_user.id})")
    await callback.answer()
    fact_id = int(callback.data.split("_")[2])
    factory = await requests.get_factory(fact_id)
    await callback.message.edit_text(
        text=messages.CONFIRM_DELETE_FACT.format(factory.company_name, factory.factory_name),
        reply_markup=await kb.confirm_delete_fact(fact_id=fact_id),
    )


@admin.callback_query(F.data.startswith("confirm_delete_factory_"))
async def confirm_delete_fact(callback: CallbackQuery, state: FSMContext):
    logger.info(f"confirm_delete_fact (from_user={callback.from_user.id})")
    await callback.answer()
    fact_id = int(callback.data.split("_")[3])
    await requests.delete_factory(fact_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(text=messages.FACTORY_DELETED)


@admin.callback_query(F.data.startswith("master_list_factory_"))
async def master_list_by_factory(callback: CallbackQuery, state: FSMContext):
    factory_id = callback.data.split("_")[-1]
    reply_markup = await kb.factory_master_list(factory_id=factory_id)
    factory = await requests.get_factory(int(factory_id))

    if not reply_markup:
        await callback.answer(labels.EMPTY_LIST, show_alert=True)
        return

    await callback.message.edit_text(
        text=messages.MASTERS_BY_FACTORY.format(factory.factory_name), reply_markup=reply_markup
    )


# Редактировать коды деятельности
# Добавить название кода деятельности
@admin.callback_query(F.data == "add_activity_code")
async def add_activity_code(callback: CallbackQuery, state: FSMContext):
    logger.info(f"add_activity_code (from_user={callback.from_user.id})")
    await state.clear()
    await callback.answer()
    await state.set_state(PickActivityCode.code)
    await callback.message.edit_text(text=messages.ADD_ACTIVITY_CODE, reply_markup=None)
    await callback.message.answer(text=messages.ENTER_ACTIVITY_CODE)


# Добавить длительность к активности
@admin.message(PickActivityCode.code)
async def add_activity_duration(message: Message, state: FSMContext):
    logger.info(f"add_activity_duration (from_user={message.from_user.id})")
    await state.update_data(code=message.text[: ActivityLen.code])
    await state.set_state(PickActivityCode.duration)
    await message.answer(text=messages.ENTER_ACTIVITY_DURATION)


# Добавить пояснение к активности
@admin.message(PickActivityCode.duration)
async def add_activity_description(message: Message, state: FSMContext):
    logger.info(f"add_activity_description (from_user={message.from_user.id})")
    await state.update_data(duration=message.text)
    await state.set_state(PickActivityCode.description)
    await message.answer(text=messages.ENTER_ACTIVITY_DESCRIPTION)


# Добавить цвет активности
@admin.message(PickActivityCode.description)
async def add_activity_color(message: Message, state: FSMContext):
    logger.info(f"add_activity_color (from_user={message.from_user.id})")
    await state.update_data(description=message.text[: ActivityLen.description])
    await state.set_state(PickActivityCode.color)
    await message.answer(text=messages.ENTER_ACTIVITY_COLOR, disable_web_page_preview=True)


# Подтверждение добавления кода активности
@admin.message(PickActivityCode.color)
async def confirm_activity_code(message: Message, state: FSMContext):
    logger.info(f"confirm_activity_code (from_user={message.from_user.id})")
    await state.update_data(color=message.text)
    data = await state.get_data()
    await message.answer(
        text=messages.CONFIRM_ADD_ACTIVITY.format(
            data.get("code"),
            data.get("duration"),
            data.get("description"),
            data.get("color"),
        ),
        reply_markup=kb.confirm_add_activity_kb,
    )


@admin.callback_query(F.data == "add_activity_confirm")
async def add_activity(callback: CallbackQuery, state: FSMContext):
    logger.info(f"add_activity (from_user={callback.from_user.id})")
    await callback.answer()
    data = await state.get_data()
    await state.clear()
    res_reply = messages.CONFIRM_ADD
    try:
        await requests.set_activity(
            data.get("code"),
            float(data.get("duration")),
            data.get("description"),
            data.get("color"),
        )
    except AlreadyExistsError:
        res_reply = messages.ALREADY_EXISTS_CODE
    except BadFormatError:
        res_reply = messages.INCORRECT_DATA
    except ValueError:
        res_reply = messages.BAD_DURATION
    except Exception as ex:
        logger.critical(f"Ошибка добавления кода:\n{ex}")
        res_reply = messages.UNEXPECTED_ERROR
    finally:
        logger.debug(res_reply)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(text=res_reply, reply_markup=None)


@admin.callback_query(F.data == "list_activity_code")
async def activity_list(callback: CallbackQuery, state: FSMContext):
    logger.info(f"activity_list (from_user={callback.from_user.id})")
    reply_markup = await kb.get_activity_list(1)
    if not reply_markup:
        logger.debug("Список пуст")
        await callback.answer(labels.EMPTY_LIST, show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(text=labels.LIST_CODE_BUTTON, reply_markup=reply_markup)


@admin.callback_query(F.data == "return_manage_actlist")
async def activity_return(callback: CallbackQuery, state: FSMContext):
    logger.info(f"activity_return (from_user={callback.from_user.id})")
    await callback.answer()
    await callback.message.edit_text(text=labels.EDIT_CODES, reply_markup=kb.activity_code_kb)


@admin.callback_query(F.data.startswith("activity_"))
async def activity_info(callback: CallbackQuery, state: FSMContext):
    logger.info(f"activity_info (from_user={callback.from_user.id})")
    await callback.answer()

    id = callback.data.split("_")[1]
    back_page = callback.data.split("_")[2]

    activity = await requests.get_activity(int(id))

    info = messages.ACTIVITY_INFO.format(
        activity.code, activity.duration, activity.description, activity.color
    )

    await callback.message.edit_text(
        text=info, reply_markup=await kb.manage_activity(id=id, back_page=back_page)
    )


@admin.callback_query(F.data.startswith("page_actlist_"))
async def act_page(callback: CallbackQuery, state: FSMContext):
    logger.info(f"act_page (from_user={callback.from_user.id})")
    await callback.answer()
    reply_markup = await kb.get_activity_list(int(callback.data.split("_")[2]))
    await callback.message.edit_text(text=labels.LIST_CODE_BUTTON, reply_markup=reply_markup)


@admin.callback_query(F.data.startswith("delete_activity_"))
async def confirm_delete_activity(callback: CallbackQuery, state: FSMContext):
    logger.info(f"confirm_delete_activity (from_user={callback.from_user.id})")
    await callback.answer()

    id = callback.data.split("_")[2]
    activity = await requests.get_activity(int(id))

    reply_markup = await kb.activity_delete(id)
    text = messages.DELETE_ACTIVITY.format(
        activity.code, activity.duration, activity.description, activity.color
    )

    await callback.message.edit_text(text=text, reply_markup=reply_markup)


@admin.callback_query(F.data.startswith("confirm_delete_activity_"))
async def delete_activity(callback: CallbackQuery, state: FSMContext):
    logger.info(f"delete_activity (from_user={callback.from_user.id})")
    await callback.answer()

    id = callback.data.split("_")[3]

    await requests.delete_activity(int(id))

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(text=messages.ACTIVITY_DELETED)


# Управление работниками
@admin.callback_query(F.data == "add_worker")
async def add_worker(callback: CallbackQuery, state: FSMContext):
    logger.info(f"add_worker (from_user={callback.from_user.id})")
    await state.clear()
    await callback.answer()
    await state.set_state(PickWorker.name)

    await callback.message.edit_text(text=messages.WORKER_ADDING, reply_markup=None)
    await callback.message.answer(text=messages.ENTER_WORKER_NAME)


@admin.message(PickWorker.name)
async def add_worker_name(message: Message, state: FSMContext):
    logger.info(f"add_worker_name (from_user={message.from_user.id})")
    await state.update_data(name=message.text[: UserLen.fullname])
    await state.set_state(PickWorker.job)
    await message.answer(text=messages.ENTER_WORKER_JOB)


@admin.message(PickWorker.job)
async def add_worker_job(message: Message, state: FSMContext):
    logger.info(f"add_worker_job (from_user={message.from_user.id})")
    await state.update_data(job=message.text[: WorkerProfileLen.job])
    await state.set_state(PickWorker.rate)
    await message.answer(text=messages.ENTER_WORKERS_RATE)


@admin.message(PickWorker.rate)
async def add_worker_rate(message: Message, state: FSMContext):
    logger.info(f"add_worker_rate (from_user={message.from_user.id})")
    await state.update_data(rate=message.text)
    data = await state.get_data()
    text = messages.CONFIRM_ADD_WORKER.format(data.get("name"), data.get("job"), data.get("rate"))
    await message.answer(text=text, reply_markup=kb.confirm_add_worker_kb)


@admin.callback_query(F.data == "add_worker_confirm", PickWorker.rate)
async def confirm_worker_add(callback: CallbackQuery, state: FSMContext):
    logger.info(f"confirm_worker_add (from_user={callback.from_user.id})")
    data = await state.get_data()
    await state.clear()
    await callback.message.edit_reply_markup(None)
    try:
        await requests.set_profile(data.get("name"), data.get("job"), float(data.get("rate")))
        await callback.message.answer(text=messages.CONFIRM_ADD)
    except Exception as ex:
        logger.error(ex)
        await callback.message.answer(text=messages.INCORRECT_DATA)
        await callback.message.answer(
            text=labels.EMPLOYEE_MANAGE, reply_markup=kb.workers_manage_kb
        )


@admin.callback_query(F.data == "list_workers")
async def workers_list(callback: CallbackQuery, state: FSMContext):
    logger.info(f"workers_list (from_user={callback.from_user.id})")
    await state.clear()
    reply_markup = await kb.get_list_by_role(
        role=(Role.WORKER | Role.MASTER), cur_page=1, bot=callback.bot
    )
    if not reply_markup:
        logger.debug("Список пуст")
        await callback.answer(labels.EMPTY_LIST, show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(text=labels.WORKERS_LIST, reply_markup=reply_markup)


@admin.callback_query(F.data.startswith(f"page_{(Role.WORKER | Role.MASTER)}_"))
async def show_admin_list_page(callback: CallbackQuery, state: FSMContext):
    logger.info(f"show_admin_list_page (from_user={callback.from_user.id})")
    reply_markup = await kb.get_list_by_role(
        (Role.WORKER | Role.MASTER), int(callback.data.split("_")[-1]), callback.bot
    )
    if not reply_markup:
        logger.debug("Список пуст")
        await callback.answer(labels.EMPTY_LIST, show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(text=labels.WORKERS_LIST, reply_markup=reply_markup)


@admin.callback_query(F.data.startswith(f"{(Role.WORKER | Role.MASTER)}_"))
async def worker_info(callback: CallbackQuery, state: FSMContext):
    logger.info(f"worker_info (from_user={callback.from_user.id})")
    await callback.answer()

    id = callback.data.split("_")[1]
    logger.debug(callback.data)
    back_page = callback.data.split("_")[2]
    user = await requests.get_user(int(id), use_tg=False)
    profile = await requests.get_profile(int(id))

    reply_markup = await kb.manage_worker((Role.WORKER | Role.MASTER), id, back_page)
    text = messages.WORKER_INFO.format(user.fullname, profile.job, profile.rate)
    next_month = Month.Next()
    next_profile = await requests.get_profile(int(id), next_month.year, next_month.month)
    if not (next_profile.job == profile.job and next_profile.rate == profile.rate):
        text += "\n\n" + messages.NEXT_PROFILE.format(next_profile.job, next_profile.rate)

    await callback.message.edit_text(text=text, reply_markup=reply_markup)


# подтверждение удаления
@admin.callback_query(F.data.startswith(f"delete_{(Role.WORKER | Role.MASTER)}_"))
async def confirm_delete_worker(callback: CallbackQuery, state: FSMContext):
    logger.info(f"confirm_delete_worker (from_user={callback.from_user.id})")
    await callback.answer()

    id = callback.data.split("_")[2]
    user = await requests.get_user(int(id), use_tg=False)
    profile = await requests.get_profile(int(id))

    text = messages.CONFIRM_DELETE_WORKER.format(user.fullname, profile.job, profile.rate)
    reply_markup = await kb.confirm_worker_delete(id)
    await callback.message.edit_text(text=text, reply_markup=reply_markup)


#  удаление работника
@admin.callback_query(F.data.startswith("confirm_delete_worker_"))
async def delete_worker(callback: CallbackQuery, state: FSMContext):
    logger.info(f"delete_worker (from_user={callback.from_user.id})")
    await callback.answer()

    id = callback.data.split("_")[-1]
    await requests.update_user(int(id), {User.role: Role.USER}, use_tg=False)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(text=messages.WORKER_DELETED)


# ввод новой стаки
@admin.callback_query(F.data.startswith("edit_rate_"))
async def edit_rate_enter(callback: CallbackQuery, state: FSMContext):
    logger.info(f"edit_rate_enter (from_user={callback.from_user.id})")
    await callback.answer()
    await state.clear()

    await state.set_state(ChangeRate.id)
    await state.update_data(id=callback.data.split("_")[-1])
    await state.set_state(ChangeRate.new_rate)

    await callback.message.edit_reply_markup(None)
    await callback.message.answer(text=messages.ENTER_WORKERS_RATE)


# подтверждение новой ставки
@admin.message(ChangeRate.new_rate)
async def confirm_new_rate(message: Message, state: FSMContext):
    logger.info(f"confirm_new_rate (from_user={message.from_user.id})")
    await state.update_data(new_rate=message.text)
    data = await state.get_data()
    logger.debug(data)
    await state.clear()
    user = await requests.get_user(id=int(data.get("id")), use_tg=False)
    profile = await requests.get_profile(int(data.get("id")))

    text = messages.CHANGE_RATE.format(
        user.fullname, profile.job, profile.rate, data.get("new_rate")
    )
    reply_markup = await kb.confirm_rate_change(data.get("id"), data.get("new_rate"))
    await message.answer(text=text, reply_markup=reply_markup)


# изменение ставки после подтверждения
@admin.callback_query(F.data.startswith("confirm_change_rate_"))
async def change_rate(callback: CallbackQuery, state: FSMContext):
    logger.info(f"change_rate (from_user={callback.from_user.id})")
    await callback.answer()
    await callback.message.edit_reply_markup(None)
    id = callback.data.split("_")[3]
    new_rate = callback.data.split("_")[4]

    try:
        await requests.change_profile(int(id), {WorkerProfile.rate: float(new_rate)})
        await callback.message.answer(text=messages.CONFIRM_CHANGE_RATE)
    except Exception as ex:
        logger.warning(f"Не удалось изменить ставку:\n{ex}")
        await callback.message.answer(text=messages.INCORRECT_DATA)


# ввод новой профессии
@admin.callback_query(F.data.startswith("edit_job_"))
async def edit_job_enter(callback: CallbackQuery, state: FSMContext):
    logger.info(f"edit_job_enter (from_user={callback.from_user.id})")
    await callback.answer()
    await state.clear()

    await state.set_state(ChangeJob.id)
    await state.update_data(id=callback.data.split("_")[-1])
    await state.set_state(ChangeJob.new_job)

    await callback.message.edit_reply_markup(None)
    await callback.message.answer(text=messages.ENTER_WORKER_JOB)


# подтверждение новой профессии
@admin.message(ChangeJob.new_job)
async def confirm_job_rate(message: Message, state: FSMContext):
    logger.info(f"confirm_job_rate (from_user={message.from_user.id})")
    await state.update_data(new_job=message.text[: WorkerProfileLen.job])
    data = await state.get_data()
    logger.debug(data)
    await state.clear()
    user = await requests.get_user(id=int(data.get("id")), use_tg=False)
    profile = await requests.get_profile(int(data.get("id")))

    text = messages.CHANGE_JOB.format(
        user.fullname,
        profile.job,
        data.get("new_job"),
        profile.rate,
    )
    reply_markup = await kb.confirm_job_change(data.get("id"), data.get("new_job"))
    await message.answer(text=text, reply_markup=reply_markup)


# изменение профессии после подтверждения
@admin.callback_query(F.data.startswith("confirm_change_job_"))
async def change_job(callback: CallbackQuery, state: FSMContext):
    logger.info(f"change_job (from_user={callback.from_user.id})")
    await callback.answer()
    await callback.message.edit_reply_markup(None)
    id = callback.data.split("_")[3]
    new_job = callback.data.split("_")[4]

    try:
        await requests.change_profile(int(id), {WorkerProfile.job: new_job})
        await callback.message.answer(text=messages.CONFIRM_CHANGE_JOB)
    except Exception as ex:
        logger.warning(f"Не удалось изменить работу:\n{ex}")
        await callback.message.answer(text=messages.INCORRECT_DATA)


@admin.callback_query(F.data.startswith("denied_change_"))
async def denied_change(callback: CallbackQuery, state: FSMContext):
    logger.info(f"denied_change (from_user={callback.from_user.id})")
    await callback.answer()
    await callback.message.edit_text(text=messages.CAHNGE_DENIED, reply_markup=None)
    await callback.message.edit_text(text=messages.CAHNGE_DENIED, reply_markup=None)


# Создать смену за админа
@admin.message(F.text == labels.CREATE_SHIFT)
@admin.callback_query(F.data == "create_shift_by_admin")
async def create_shift_by_admin(event: TelegramObject, state: FSMContext):
    logger.info(f"create_shift_by_admin (from_user={event.from_user.id})")
    await state.clear()
    await state.set_state(ShiftReport.date)
    if isinstance(event, Message):
        await event.reply(text=messages.SHIFT_CREATING_BY_ADMIN)
        await event.answer(text=messages.ENTER_DATE_FOR_SHIFT, reply_markup=kb.denie_shift)
    elif isinstance(event, CallbackQuery):
        await event.message.edit_text(
            text=messages.ENTER_DATE_FOR_SHIFT, reply_markup=kb.denie_shift
        )


@admin.message(ShiftReport.date)
@admin.callback_query(F.data == "enter_shift_date")
async def enter_shift_date(event: TelegramObject, state: FSMContext):
    logger.info(f"enter_shift_date (from_user={event.from_user.id})")
    reply_markup = await kb.get_factory_list("shift_by_admin_")
    if not reply_markup:
        await state.clear()
        logger.debug("Список пуст")
    if isinstance(event, Message):
        if not reply_markup:
            await event.answer(labels.NO_FACTORIES)
            return
        try:
            day, month, year = map(int, event.text.split("."))
            formated_date = date(year=year, month=month, day=day)
            logger.debug(formated_date)
        except (ValueError, AttributeError):
            await event.answer(labels.WRONG_DATE, reply_markup=kb.denie_shift)
            logger.debug("Введена некорректная дата")
            return

        await state.update_data(date=event.text)
        await state.set_state(ShiftReport.master_activity)
        await event.answer(text=messages.SHIFT_DATE.format(event.text))

        await event.answer(text=messages.CHOOSE_FACTORY_FOR_SHIFT, reply_markup=reply_markup)
    elif isinstance(event, CallbackQuery):
        await event.answer()
        if not reply_markup:
            await event.message.answer(labels.NO_FACTORIES)
            return
        await event.message.edit_text(
            text=messages.CHOOSE_FACTORY_FOR_SHIFT, reply_markup=reply_markup
        )


@admin.callback_query(F.data.startswith("shift_by_admin_factory_"))
async def choose_factory_admin_shift(callback: CallbackQuery, state: FSMContext):
    logger.info(f"choose_factory_admin_shift (from_user={callback.from_user.id})")

    factory_id = callback.data.split("_")[-1]
    await state.update_data(factory_id=factory_id)
    factory = await requests.get_factory(int(factory_id))

    data = await state.get_data()
    logger.debug(data)

    await callback.message.edit_text(
        text=messages.SHIFT_FACTORY.format(factory.factory_name), reply_markup=None
    )

    reply_markup = await kb.get_list_by_role(Role.MASTER, 1, callback.bot, "shift_by_admin_")

    if not reply_markup:
        logger.debug("Список пуст")
        await callback.answer(labels.NO_MASTERTS, show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(text=messages.CHOOSE_MASTRE_FOR_SHIFT, reply_markup=reply_markup)


@admin.callback_query(F.data.startswith(f"shift_by_admin_page_{Role.MASTER}_"))
async def page_master_for_shift_list(callback: CallbackQuery, state: FSMContext):
    logger.info(f"page_master_for_shift_list (from_user={callback.from_user.id})")
    await callback.answer()
    await callback.message.edit_reply_markup(
        reply_markup=await kb.get_list_by_role(
            role=Role.MASTER,
            cur_page=int(callback.data.split("_")[-1]),
            bot=callback.bot,
            key="shift_by_admin_",
        )
    )


@admin.callback_query(F.data.startswith(f"shift_by_admin_{Role.MASTER}_"))
async def master_for_shift_list(callback: CallbackQuery, state: FSMContext):
    logger.info(f"master_for_shift_list (from_user={callback.from_user.id})")

    master_id = callback.data.split("_")[-2]
    master = await requests.get_user(int(master_id), use_tg=False)

    await state.update_data(master_id=master.id)

    reply_markup = reply_markup = await kb.get_activity_list(cur_page=1, key="master_shift_")

    if not reply_markup:
        await callback.answer(labels.EMPTY_LIST)
        return
    await callback.answer()

    await callback.message.edit_text(
        text=messages.SHIFT_MASTER.format(master.fullname), reply_markup=None
    )

    await callback.message.answer(text=messages.CHOOSE_MASTER_ACTIVITY, reply_markup=reply_markup)
