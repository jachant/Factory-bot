from datetime import date, datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ContentType, Message, TelegramObject

from app import keyboards as kb
from app.config import labels, messages
from app.config.roles import Role
from app.db import requests
from app.db.models import Activity, User
from app.filters import RoleFilter
from app.roles.admin import admin
from app.states import ShiftReport
from app.utils import setup_logger
from app.utils.chatTools import get_files

logger = setup_logger(__name__)
master = Router()

master.message.filter(RoleFilter(Role.MASTER))


# Затычка, чтобы не мигала кнопка
@master.callback_query(F.data == "_")
async def button_stop(callback: CallbackQuery, state: FSMContext):
    logger.info(f"button_stop (from_user={callback.from_user.id})")
    await callback.answer()


@master.message(F.text == labels.MASTER_INSTRUCION_BUTTON)
async def owner_instruction(message: Message, state: FSMContext):
    logger.info(f"owner_instruction (from_user={message.from_user.id})")
    await message.reply(text=messages.MASTER_INSTRUCTION, reply_markup=kb.masterKb)


@master.callback_query(F.data == "master_shift_return_manage_actlist")
@master.message(F.text == labels.SHIFT_REPORET)
async def auto_select_factory(event: TelegramObject, state: FSMContext):
    logger.info(f"auto_select_factory (from_user={event.from_user.id})")
    await state.clear()

    activities = await requests.get_activities()
    workers = await requests.get_users_by_role(Role.WORKER)
    logger.debug(activities)
    logger.debug(workers)

    if not activities or not workers:
        if isinstance(event, CallbackQuery):
            await event.answer()
            await event.message.edit_text(text=messages.EMPTY_MASTER_ACTIVITY, reply_markup=None)
        else:
            await event.answer(text=messages.EMPTY_MASTER_ACTIVITY)
        return

    user = await requests.get_user(event.from_user.id)
    factory = await requests.get_factory_by_user(user.id)

    await state.set_state(ShiftReport.master_id)
    await state.update_data(master_id=user.id)

    await state.set_state(ShiftReport.factory_id)
    await state.update_data(factory_id=factory.id)

    await state.update_data(date="")

    logger.debug(await state.get_data())

    prev_shift = await requests.get_shift_by_date(user_id=user.id, factory_id=factory.id)
    logger.debug(prev_shift)

    if prev_shift:
        if isinstance(event, CallbackQuery):
            await event.answer()
            await event.message.edit_text(text=messages.SHIFT_SET_UP, reply_markup=kb.shifh_set_up)
        else:
            await event.reply(text=messages.AUTO_SELECT_FACTORY.format(factory.factory_name))
            await event.answer(text=messages.SHIFT_SET_UP, reply_markup=kb.shifh_set_up)
    else:
        if isinstance(event, CallbackQuery):
            await state.clear()
            await event.message.edit_reply_markup(None)
            await event.answer(labels.SHIFT_CREATE_DENIED, show_alert=True)
            return
        else:
            await event.reply(text=messages.AUTO_SELECT_FACTORY.format(factory.factory_name))
            await state.set_state(ShiftReport.master_activity)
            reply_markup = await kb.get_activity_list(cur_page=1, key="master_shift_")

            if not reply_markup:
                await event.answer(labels.EMPTY_LIST)
                return

            await event.answer(text=messages.CHOOSE_MASTER_ACTIVITY, reply_markup=reply_markup)


@master.callback_query(F.data == "shift_set_up")
async def shift_set_up(callback: CallbackQuery, state: FSMContext):
    logger.info(f"shift_set_up (from_user={callback.from_user.id})")
    await callback.answer()
    await callback.message.edit_text(
        text=messages.CONFIRM_PREV_SHIFT, reply_markup=kb.confirm_prev_shift
    )


@master.callback_query(F.data == "shift_not_set_up")
async def shift_not_set_up(callback: CallbackQuery, state: FSMContext):
    logger.info(f"shift_not_set_up (from_user={callback.from_user.id})")
    logger.debug(callback.data)
    await state.set_state(ShiftReport.master_activity)
    data = await state.get_data()
    if not len(data.get("workers_activities_list", [])):
        await state.update_data(workers_activities_list=[])
    reply_markup = await kb.get_activity_list(cur_page=1, key="master_shift_")

    if not reply_markup:
        await state.clear()
        await callback.answer(messages.EMPTY_MASTER_ACTIVITY, show_alert=True)
        return

    await callback.answer()

    await callback.message.edit_text(
        text=messages.CHOOSE_MASTER_ACTIVITY, reply_markup=reply_markup
    )


@master.callback_query(F.data.startswith("master_shift_page_actlist_"))
async def page_shift_master_actlist(callback: CallbackQuery, state: FSMContext):
    logger.info(f"page_shift_master_actlist (from_user={callback.from_user.id})")
    await callback.answer()

    reply_markup = await kb.get_activity_list(
        cur_page=int(callback.data.split("_")[-1]), key="master_shift_"
    )

    await callback.message.edit_reply_markup(reply_markup=reply_markup)


@master.callback_query(F.data.startswith("master_shift_activity_"))
async def master_shift_activity(callback: CallbackQuery, state: FSMContext):
    logger.info(f"master_shift_activity (from_user={callback.from_user.id})")
    await callback.answer()
    activity_id = callback.data.split("_")[-2]
    await state.update_data(master_activity=activity_id)
    activity = await requests.get_activity(int(activity_id))
    await callback.message.edit_text(
        text=messages.CONFIRM_MASTER_ACTIVITY_SHIFT.format(activity.code),
        reply_markup=kb.confirm_master_shift_activity,
    )


@master.callback_query(F.data.startswith("not_add"))
@master.callback_query(F.data.startswith("edit_not_save_shift_"))
@master.callback_query(F.data.startswith("confirm_edit_worker_by_master_"))
@master.callback_query(F.data.startswith("not_confirm_edit_worker_by_master_"))
@master.callback_query(F.data.startswith("shift_choose_activity_activity_"))
@master.callback_query(F.data.startswith("confirm_master_shift_activity_"))
async def shift_choose_woker(callback: CallbackQuery, state: FSMContext):
    logger.info(f"shift_choose_woker (from_user={callback.from_user.id})")
    logger.debug(callback.data)
    await state.set_state(ShiftReport.temp_worker)
    number = callback.data.split("_")[-1]
    data = await state.get_data()
    logger.debug(data)
    if callback.data.startswith("confirm_master_shift_activity_"):
        temp_data = await state.get_data()
        master_id = str(temp_data.get("master_id"))
        master_activity_id = temp_data.get("master_activity")
        workers_activities_list = temp_data.get("workers_activities_list", [])

        # Найти индекс мастера
        worker_index = next(
            (index for index, item in enumerate(workers_activities_list) if item[0] == master_id),
            None,
        )

        if worker_index is None:
            # Если мастер не найден (т.е. смена ещё не настроена), добавить
            workers_activities_list.append([str(master_id), master_activity_id])
        else:
            # Если мастер найден (т.е. смена уже настроена), обновить активность
            workers_activities_list[worker_index] = [str(master_id), master_activity_id]
            number = str(len(workers_activities_list))

        logger.debug(workers_activities_list)

        # Обновить данные в состоянии
        await state.update_data(workers_activities_list=workers_activities_list)

    if callback.data.startswith("not_add"):
        logger.debug("not add activity")
        temp_data = await state.get_data()
        temp_worker = temp_data.get("temp_worker")
        workers_activities_list = temp_data.get("workers_activities_list", [])

        # Проверяем наличие мастера в списке и удаляем
        worker_index = next(
            (
                index
                for index, item in enumerate(workers_activities_list)
                if item[0] == temp_worker
            ),
            None,
        )
        if worker_index is not None:
            number = str(int(number) - 1)
            del workers_activities_list[worker_index]
            await state.update_data(workers_activities_list=workers_activities_list)
            logger.debug(f"Worker {temp_worker} removed from workers_activities_list")

        await callback.message.edit_text(text=messages.CANCEL_ADD, reply_markup=None)

    if callback.data.startswith("confirm_edit_worker_by_master_"):
        worker_number = callback.data.split("_")[-2]
        temp_data = await state.get_data()
        temp_activity_id = temp_data.get("temp_activity")
        activity = await requests.get_activity(int(temp_activity_id))
        workers_activities_list = temp_data.get("workers_activities_list", [])
        workers_activities_list[int(worker_number)][1] = temp_activity_id
        await callback.message.edit_text(
            text=messages.EDIT_WORKER_ACTIVITY_SHIFT.format(activity.code), reply_markup=None
        )

    if callback.data.startswith("not_confirm_edit_worker_by_master_"):
        await callback.message.edit_text(text=messages.EDITING_DENIED, reply_markup=None)

    if callback.data.startswith("edit_not_save_shift_"):
        await callback.message.edit_reply_markup(None)
        await callback.message.answer(text=messages.CONTINUE_EDITING)

    if callback.data.startswith("shift_choose_activity_activity_"):
        await state.update_data(temp_activity=callback.data.split("_")[-3])
        temp_data = await state.get_data()
        temp_worker = temp_data.get("temp_worker")
        temp_activity_id = temp_data.get("temp_activity")
        activity = await requests.get_activity(int(temp_activity_id))
        temp_activity = activity.code
        workers_activities_list = temp_data.get("workers_activities_list", [])

        worker_index = next(
            (
                index
                for index, item in enumerate(workers_activities_list)
                if item[0] == temp_worker
            ),
            None,
        )

        if worker_index is not None:
            logger.debug("shift - worker editing")
            reply_markup = await kb.confirm_edit_worker_by_master(
                worker_index=worker_index, number=number
            )
            prev_activity = await requests.get_activity(
                int(workers_activities_list[worker_index][1])
            )
            text = messages.EDIT_WORKER_SHIFT_BY_MASTER.format(prev_activity.code, temp_activity)

            await callback.message.edit_text(text=text, reply_markup=reply_markup)
            return
        else:
            workers_activities_list.append([temp_worker, temp_activity_id])

            await state.update_data(workers_activities_list=workers_activities_list)
            await callback.message.edit_text(
                text=messages.ACTIVITY_NUMBER.format(number, temp_activity), reply_markup=None
            )
            number = str(int(number) + 1)

            logger.debug(await state.get_data())

    reply_markup = await kb.get_list_by_role(
        role=Role.WORKER,
        cur_page=1,
        bot=callback.bot,
        key="shift_choose_worker_",
        end="_" + number,
    )
    if callback.data.startswith("confirm_master_shift_activity_"):
        logger.debug("1st worker")
        activity = await requests.get_activity(int(temp_data.get("master_activity")))
        await callback.message.edit_text(
            text=messages.MASTER_ACTIVITY_SHIFT.format(activity.code),
            reply_markup=None,
        )

    if not reply_markup:
        await state.clear()
        await callback.answer(messages.EMPTY_MASTER_ACTIVITY, show_alert=True)
        return

    await callback.message.answer(
        text=messages.CHOOSE_WORKER_SHIFT.format(number),
        reply_markup=reply_markup,
    )


@master.callback_query(F.data.startswith("shift_choose_worker_page_"))
async def page_shift_choose_woker(callback: CallbackQuery, state: FSMContext):
    logger.info(f"page_shift_choose_woker (from_user={callback.from_user.id})")
    number = callback.data.split("_")[-1]
    back_page = callback.data.split("_")[-2]

    await callback.answer()
    reply_markup = await kb.get_list_by_role(
        role=Role.WORKER,
        cur_page=int(back_page),
        bot=callback.bot,
        key="shift_choose_worker_",
        end="_" + number,
    )
    await callback.message.edit_text(
        text=messages.CHOOSE_WORKER_SHIFT.format(number), reply_markup=reply_markup
    )


@master.callback_query(F.data.startswith(f"shift_choose_worker_{Role.WORKER}"))
async def shift_choose_activity(callback: CallbackQuery, state: FSMContext):
    logger.info(f"shift_choose_activity (from_user={callback.from_user.id})")
    number = callback.data.split("_")[-1]
    worker_id = callback.data.split("_")[-3]
    await state.update_data(temp_worker=worker_id)
    user = await requests.get_user(id=int(worker_id), use_tg=False)

    logger.debug(await state.get_data())

    reply_markup = await kb.get_activity_list(
        cur_page=1, key="shift_choose_activity_", end="_" + number
    )

    if not reply_markup:
        await state.clear()
        await callback.answer(messages.EMPTY_MASTER_ACTIVITY, show_alert=True)
        return

    await callback.message.edit_text(
        text=messages.WORKER_NUMBER.format(number, user.fullname), reply_markup=None
    )
    await callback.message.answer(
        text=messages.CHOOSE_ACTIVITY_SHIFT.format(number), reply_markup=reply_markup
    )


@master.callback_query(F.data.startswith("shift_choose_activity_page_actlist_"))
async def page_shift_choose_activity(callback: CallbackQuery, state: FSMContext):
    logger.info(f"page_shift_choose_activity (from_user={callback.from_user.id})")
    await callback.answer()
    logger.debug(callback.data)
    end = callback.data.split("_")[-1]
    back_page = callback.data.split("_")[-2]

    reply_markup = await kb.get_activity_list(
        cur_page=int(back_page), key="shift_choose_activity_", end="_" + end
    )

    await callback.message.edit_reply_markup(reply_markup=reply_markup)


@master.callback_query(F.data.startswith("save_shift_choise_"))
async def save_shift_choise(callback: CallbackQuery, state: FSMContext):
    logger.info(f"save_shift_choise (from_user={callback.from_user.id})")
    await callback.answer()

    number = callback.data.split("_")[-1]
    data = await state.get_data()
    workers_activities_list = data.get("workers_activities_list", [])

    text = messages.SHIFT_HEADER_TOTAL

    for i in range(len(workers_activities_list)):
        user = await requests.get_user(int(workers_activities_list[i][0]), use_tg=False)
        activity = await requests.get_activity(int(workers_activities_list[i][1]))
        text += messages.WORKER_ACTIVITY_PAIR.format(user.fullname, activity.code)

    await callback.message.edit_text(text=text, reply_markup=await kb.confirm_shift_menu(number))


@master.callback_query(F.data.startswith("denie_shift"))
async def denie_shift(callback: CallbackQuery, state: FSMContext):
    logger.info(f"denie_shift (from_user={callback.from_user.id})")
    await callback.answer(labels.SAVE_SHIFT_DENIED, show_alert=True)
    await callback.message.edit_reply_markup(None)


@master.callback_query(F.data == "write_shift")
async def write_shift(callback: CallbackQuery, state: FSMContext):
    logger.info(f"write_shift (from_user={callback.from_user.id})")
    await callback.answer()

    data = await state.get_data()
    logger.debug(await state.get_state())
    logger.debug(data)

    await state.set_state(ShiftReport.shift_photo)
    await callback.message.edit_reply_markup(None)

    logger.debug(await state.get_state())

    await callback.message.answer(text=messages.ADD_PHOTO)


@master.message(ShiftReport.shift_photo)
@admin.message(ShiftReport.shift_photo)
async def get_shift_photo(message: Message, state: FSMContext, album: list = None):
    logger.info(f"get_shift_photo (from_user={message.from_user.id})")

    attachments = await get_files(album if album else [message])
    if not attachments:
        await message.answer(text=messages.NOT_PHOTO)
        return

    paths = []
    for file_id in attachments:
        file = await message.bot.get_file(file_id)
        paths.append(file.file_path)

    await state.update_data(shift_photo=paths)
    # Костыль, чтобы сбросить текущий state
    await state.set_state(ShiftReport.master_id)
    await message.answer(text=messages.CONFIRM_PHOTO, reply_markup=kb.confirm_shift_photo)


@master.callback_query(F.data == "save_shift_photo")
async def confirm_write_shift(callback: CallbackQuery, state: FSMContext):
    logger.info(f"confirm_write_shift (from_user={callback.from_user.id})")
    await callback.answer()
    await callback.message.edit_reply_markup(None)
    await callback.message.answer(
        text=messages.CONFIRM_WRITE_SHIFT, reply_markup=kb.confirm_write_shift
    )


@master.callback_query(F.data == "confirm_write_shift")
async def write_shift_to_db(callback: CallbackQuery, state: FSMContext):
    logger.info(f"write_shift_to_db (from_user={callback.from_user.id})")
    await callback.answer(messages.SHIFT_SAVING, show_alert=True)

    data = await state.get_data()
    await state.clear()
    logger.debug(data)

    workers_activities_list = data.get("workers_activities_list", [])
    master_id = int(data.get("master_id"))
    factory_id = int(data.get("factory_id"))
    photo_paths = data.get("shift_photo")
    shift_date = data.get("date")

    # Преобразование списка
    formatted_list = [
        {User.id: int(worker_id), Activity.id: int(activity_id)}
        for worker_id, activity_id in workers_activities_list
    ]

    # Добавление мастера в список (перемещено)
    logger.debug(formatted_list)
    await callback.message.edit_reply_markup(None)
    await callback.message.edit_text(text=messages.SHIFT_SAVING)

    if shift_date:
        day, month, year = map(int, shift_date.split("."))
        formated_date = datetime.combine(
            date(year=year, month=month, day=day), datetime.now().time()
        )
    else:
        formated_date = None

    await requests.add_shift(
        user_id=master_id,
        factory_id=factory_id,
        photo_paths=photo_paths,
        positions=formatted_list,
        shift_datetime=formated_date,
    )

    await callback.message.edit_text(text=messages.SHIFT_SAVED)


@master.callback_query(F.data == "view_shift")
async def view_shift(callback: CallbackQuery, state: FSMContext):
    logger.info(f"view_shift (from_user={callback.from_user.id})")
    await callback.answer()
    data = await state.get_data()

    master_id = int(data.get("master_id"))
    factory_id = int(data.get("factory_id"))

    prev_shifts = await requests.get_shift_by_date(master_id, factory_id)
    time_sheet = prev_shifts[0]

    text = ""
    positions = await requests.get_positions_by_shift_id(time_sheet.id)
    for worker_position, code in positions:
        user = await requests.get_user(worker_position.user_id, use_tg=False)
        text += messages.WORKER_ACTIVITY_PAIR.format(user.fullname, code)

    await callback.message.edit_reply_markup(None)
    await callback.message.answer(text=text, reply_markup=kb.confirm_prev_shift)


@master.callback_query(F.data == "confirm_prev_shift")
async def confirm_prev_shift(callback: CallbackQuery, state: FSMContext):
    logger.info(f"confirm_prev_shift (from_user={callback.from_user.id})")
    await callback.answer()
    data = await state.get_data()

    master_id = int(data.get("master_id"))
    factory_id = int(data.get("factory_id"))

    prev_shifts = await requests.get_shift_by_date(master_id, factory_id)
    time_sheet = prev_shifts[0]

    positions = await requests.get_positions_by_shift_id(time_sheet.id)
    formatted_list = [
        [str(worker_position.user_id), str(worker_position.activity_id)]
        for worker_position, _ in positions
    ]
    await state.update_data(workers_activities_list=formatted_list)

    await callback.message.edit_reply_markup(reply_markup=None)
    reply_markup = await kb.get_activity_list(cur_page=1, key="master_shift_")

    if not reply_markup:
        await state.clear()
        await callback.answer(messages.EMPTY_MASTER_ACTIVITY, show_alert=True)
        return

    await callback.message.answer(text=messages.CHOOSE_MASTER_ACTIVITY, reply_markup=reply_markup)
