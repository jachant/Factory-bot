from datetime import date
from math import ceil

from aiogram import Bot
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import labels
from app.config.keyboards import KEYBOARD_PAGE_SIZE
from app.config.roles import Role
from app.db import requests
from app.utils import setup_logger
from app.utils.month import MONTHS, Month

logger = setup_logger(__name__)

ownerKb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=labels.SAVE_REPORT)],
        [KeyboardButton(text=labels.EDITING), KeyboardButton(text=labels.INSTRUCTION_BUTTON)],
    ]
)

editingKb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=labels.EMPLOYEE_MANAGE), KeyboardButton(text=labels.MASTERS_MANAGE)],
        [
            KeyboardButton(text=labels.EDIT_SHIFT),
            KeyboardButton(text=labels.CREATE_SHIFT),
            KeyboardButton(text=labels.EDIT_CODES),
        ],
        [
            KeyboardButton(text=labels.ADMIN_MANAGE),
            KeyboardButton(text=labels.MAIN_MENU),
            KeyboardButton(text=labels.FACTORIES_MANAGE),
        ],
    ]
)

masterKb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=labels.SHIFT_REPORET)],
        [KeyboardButton(text=labels.MASTER_INSTRUCION_BUTTON)],
    ]
)

adminManageKb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=labels.ADD_ADMIN, callback_data="add_admin")],
        [InlineKeyboardButton(text=labels.ADMIN_LIST, callback_data="list_admins")],
        [InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb")],
    ]
)

confirmAdminAdd = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text=labels.YES, callback_data="add_admin_confirm"),
            InlineKeyboardButton(text=labels.NO, callback_data="add_admin_denied"),
        ],
        [InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb")],
    ]
)

masterManageKb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=labels.ADD_MASTER, callback_data="add_master")],
        [InlineKeyboardButton(text=labels.MASTER_LIST, callback_data="list_master")],
        [InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb")],
    ]
)

confirmMasterAdd = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text=labels.YES, callback_data="add_master_confirm"),
            InlineKeyboardButton(text=labels.NO, callback_data="add_master_denied"),
        ],
        [InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb")],
    ]
)

adminKb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=labels.SAVE_REPORT)],
        [KeyboardButton(text=labels.ADMIN_EDITING), KeyboardButton(text=labels.ADMIN_INSTRUCTION)],
    ]
)

admin_editing_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=labels.EMPLOYEE_MANAGE), KeyboardButton(text=labels.MASTERS_MANAGE)],
        [
            KeyboardButton(text=labels.EDIT_SHIFT),
            KeyboardButton(text=labels.CREATE_SHIFT),
            KeyboardButton(text=labels.EDIT_CODES),
        ],
        [
            KeyboardButton(text=labels.FACTORIES_MANAGE),
            KeyboardButton(text=labels.ADMIN_MAIN_MENU),
        ],
    ]
)

factories_manage = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=labels.ADD_FACTORY, callback_data="add_factory")],
        [InlineKeyboardButton(text=labels.FACTORY_LIST, callback_data="factory_list")],
        [InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb")],
    ]
)

confirm_factory_add = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text=labels.YES, callback_data="add_factory_confirm"),
            InlineKeyboardButton(text=labels.NO, callback_data="add_denied"),
        ],
        [InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb")],
    ]
)

activity_code_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=labels.ADD_CODE_BUTTON, callback_data="add_activity_code")],
        [InlineKeyboardButton(text=labels.LIST_CODE_BUTTON, callback_data="list_activity_code")],
        [InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb")],
    ]
)

confirm_add_activity_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text=labels.YES, callback_data="add_activity_confirm"),
            InlineKeyboardButton(text=labels.NO, callback_data="add_denied"),
        ],
        [InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb")],
    ]
)

workers_manage_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=labels.ADD_WORKER, callback_data="add_worker")],
        [InlineKeyboardButton(text=labels.WORKERS_LIST, callback_data="list_workers")],
        [InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb")],
    ]
)


confirm_add_worker_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text=labels.YES, callback_data="add_worker_confirm"),
            InlineKeyboardButton(text=labels.NO, callback_data="add_denied"),
        ],
        [InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb")],
    ]
)

shifh_set_up = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text=labels.VIEW_SHIFT, callback_data="view_shift"),
        ],
        [InlineKeyboardButton(text=labels.CREATE_NEW_SHIFT, callback_data="shift_not_set_up")],
        [InlineKeyboardButton(text=labels.DENIE_SHIFT, callback_data="denie_shift")],
    ]
)

confirm_prev_shift = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text=labels.CONFIRM_SET_UP_SHIFT, callback_data="confirm_prev_shift"
            )
        ],
        [InlineKeyboardButton(text=labels.CREATE_NEW_SHIFT, callback_data="shift_not_set_up")],
        [InlineKeyboardButton(text=labels.DENIE_SHIFT, callback_data="denie_shift")],
    ]
)

confirm_master_shift_activity = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text=labels.YES, callback_data="confirm_master_shift_activity_1"),
            InlineKeyboardButton(text=labels.NO, callback_data="shift_not_set_up"),
        ],
        [InlineKeyboardButton(text=labels.DENIE_SHIFT, callback_data="denie_shift")],
    ]
)

confirm_shift_photo = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=labels.SAVE_SHIFT_PHOTO, callback_data="save_shift_photo")],
        [InlineKeyboardButton(text=labels.GET_NEW_SHIFT_PHOTO, callback_data="write_shift")],
        [InlineKeyboardButton(text=labels.DENIE_SHIFT, callback_data="denie_shift")],
    ]
)

confirm_write_shift = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text=labels.YES, callback_data="confirm_write_shift"),
            InlineKeyboardButton(text=labels.NO, callback_data="denie_shift"),
        ],
    ]
)

confirm_edit_shift = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text=labels.YES, callback_data="confirm_edit_shift_report"),
            InlineKeyboardButton(text=labels.NO, callback_data="not_confirm_edit_shift_report"),
        ],
    ]
)

denie_shift = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text=labels.DENIE_SHIFT, callback_data="denie_shift"),
        ]
    ]
)


async def get_list_by_role(role: Role, cur_page: int, bot: Bot, key: str = "", end: str = ""):
    """Универсальная клавиатура.

    Code:
        "admin" - admin list
        "master" - master list
        "worker" - worker list for admin
        "mworkers" - workerlist for master

    Returns:
        InlineKeyboardMarkup: Inline кнопки.
    """
    people_list = await requests.get_users_by_role(role)

    if not people_list:
        return None

    pages_num = ceil(len(people_list) / KEYBOARD_PAGE_SIZE)
    from_i = KEYBOARD_PAGE_SIZE * (cur_page - 1)
    to_i = min(len(people_list), KEYBOARD_PAGE_SIZE * cur_page)
    keyboard = InlineKeyboardBuilder()

    for i in range(from_i, to_i):
        logger.debug(f"{key}{role}_{people_list[i].id}_{cur_page}")
        keyboard.row(
            InlineKeyboardButton(
                text=people_list[i].fullname,
                callback_data=f"{key}{role}_{people_list[i].id}_{cur_page}{end}",
            ),
        )

    keyboard.row(
        InlineKeyboardButton(
            text=labels.BACK,
            callback_data=(f"{key}page_{role}_{cur_page - 1}{end}" if cur_page - 1 > 0 else "_"),
        ),
        InlineKeyboardButton(text=f"{cur_page}/{pages_num}", callback_data="_"),
        InlineKeyboardButton(
            text=labels.FORWARD,
            callback_data=(
                f"{key}page_{role}_{cur_page + 1}{end}" if cur_page < pages_num else "_"
            ),
        ),
    )

    if key == "shift_choose_worker_":
        keyboard.row(
            InlineKeyboardButton(text=labels.SAVE_CHOISE, callback_data=f"save_shift_choise{end}")
        )

    logger.debug(f"{key}return_manage_{role}")
    if key == "shift_by_admin_":
        keyboard.row(
            InlineKeyboardButton(text=labels.RETURN, callback_data="enter_shift_date"),
            InlineKeyboardButton(text=labels.CANCEL_EDITING, callback_data="denie_shift"),
        )
    elif key != "shift_choose_worker_":
        keyboard.row(
            InlineKeyboardButton(
                text=labels.RETURN, callback_data=f"{key}return_manage_{role}{end}"
            ),
            InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb"),
        )
    else:
        keyboard.row(
            InlineKeyboardButton(text=labels.DENIE_SHIFT, callback_data="denie_shift"),
        )

    return keyboard.as_markup()


async def manage_people(role: Role, user_tg_id: int, back_page: int):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(text=labels.DISMISS, callback_data=f"dismiss_{role}_{user_tg_id}")
    )

    # через if добавить кнопки для мастеров и работников

    keyboard.row(
        InlineKeyboardButton(text=labels.RETURN, callback_data=f"page_{role}_{back_page}"),
        InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb"),
    )
    return keyboard.as_markup()


async def person_delete(role: Role, user_tg_id: int):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(text=labels.YES, callback_data=f"confirm_dismiss_{role}_{user_tg_id}")
    )

    keyboard.row(
        InlineKeyboardButton(text=labels.NO, callback_data=f"denied_dismiss_{role}_{user_tg_id}")
    )
    return keyboard.as_markup()


async def get_factory_list(key: str = ""):
    keyboard = InlineKeyboardBuilder()

    factories = await requests.get_factories()
    if not factories:
        return None

    for f in factories:
        keyboard.row(
            InlineKeyboardButton(
                text=f"{f.company_name} | {f.factory_name}", callback_data=f"{key}factory_{f.id}"
            )
        )
    if key == "report":
        keyboard.row(
            InlineKeyboardButton(text=labels.ALL_FACTORIES, callback_data=f"{key}factory_")
        )
    if key == "edit_shift_":
        keyboard.row(
            InlineKeyboardButton(
                text=labels.CANCEL_EDITING, callback_data="not_confirm_edit_shift_report"
            ),
        )
    elif key == "shift_by_admin_":
        keyboard.row(
            InlineKeyboardButton(text=labels.RETURN, callback_data="create_shift_by_admin"),
            InlineKeyboardButton(text=labels.CANCEL_EDITING, callback_data="denie_shift"),
        )
    else:
        keyboard.row(
            InlineKeyboardButton(text=labels.RETURN, callback_data=f"{key}return_factories"),
            InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb"),
        )

    return keyboard.as_markup()


async def manage_factory(fact_id: int):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(text=labels.DELETE, callback_data=f"delete_factory_{fact_id}"),
        InlineKeyboardButton(
            text=labels.MASTER_LIST, callback_data=f"master_list_factory_{fact_id}"
        ),
    )

    keyboard.row(
        InlineKeyboardButton(text=labels.RETURN, callback_data="factory_list"),
        InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb"),
    )

    return keyboard.as_markup()


async def confirm_delete_fact(fact_id: int):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(text=labels.YES, callback_data=f"confirm_delete_factory_{fact_id}"),
        InlineKeyboardButton(text=labels.NO, callback_data="denied_dismiss_factory"),
    )

    return keyboard.as_markup()


async def get_activity_list(cur_page: int, key: str = "", end: str = ""):

    activity_list = await requests.get_activities()

    pages_num = ceil(len(activity_list) / KEYBOARD_PAGE_SIZE)
    from_i = KEYBOARD_PAGE_SIZE * (cur_page - 1)
    to_i = min(len(activity_list), KEYBOARD_PAGE_SIZE * cur_page)

    keyboard = InlineKeyboardBuilder()

    if not activity_list:
        return None

    for i in range(from_i, to_i):
        keyboard.row(
            InlineKeyboardButton(
                text=activity_list[i].code,
                callback_data=f"{key}activity_{activity_list[i].id}_{cur_page}{end}",
            )
        )

    keyboard.row(
        InlineKeyboardButton(
            text=labels.BACK,
            callback_data=(f"{key}page_actlist_{cur_page - 1}{end}" if cur_page - 1 > 0 else "_"),
        ),
        InlineKeyboardButton(text=f"{cur_page}/{pages_num}", callback_data="_"),
        InlineKeyboardButton(
            text=labels.FORWARD,
            callback_data=(
                f"{key}page_actlist_{cur_page + 1}{end}" if cur_page < pages_num else "_"
            ),
        ),
    )
    if key == "master_shift_":
        keyboard.row(
            InlineKeyboardButton(text=labels.DENIE_SHIFT, callback_data="denie_shift"),
        )
    elif key == "edit_shift_":
        keyboard.row(
            InlineKeyboardButton(
                text=labels.CANCEL_EDITING, callback_data="not_confirm_edit_shift_report"
            ),
        )
    elif key != "shift_choose_activity_":
        keyboard.row(
            InlineKeyboardButton(
                text=labels.RETURN, callback_data=f"{key}return_manage_actlist{end}"
            ),
            InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb"),
        )
    else:
        keyboard.row(
            InlineKeyboardButton(text=labels.NOT_ADD, callback_data=f"not_add{end}"),
        )
        keyboard.row(
            InlineKeyboardButton(text=labels.DENIE_SHIFT, callback_data="denie_shift"),
        )

    return keyboard.as_markup()


async def manage_activity(id: str, back_page: int):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(InlineKeyboardButton(text=labels.DELETE, callback_data=f"delete_activity_{id}"))

    keyboard.row(
        InlineKeyboardButton(text=labels.RETURN, callback_data=f"page_actlist_{back_page}"),
        InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb"),
    )

    return keyboard.as_markup()


async def activity_delete(id: str):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(text=labels.YES, callback_data=f"confirm_delete_activity_{id}")
    )

    keyboard.row(InlineKeyboardButton(text=labels.NO, callback_data="denied_dismiss_"))
    return keyboard.as_markup()


async def manage_worker(role: Role, id: str, back_page: int):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(
            text=labels.DELETE, callback_data=f"delete_{(Role.WORKER | Role.MASTER)}_{id}"
        )
    )

    keyboard.row(
        InlineKeyboardButton(text=labels.EDIT_RATE, callback_data=f"edit_rate_{id}"),
    )

    keyboard.row(
        InlineKeyboardButton(text=labels.EDIT_JOB, callback_data=f"edit_job_{id}"),
    )

    keyboard.row(
        InlineKeyboardButton(text=labels.RETURN, callback_data=f"page_{role}_{back_page}"),
        InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb"),
    )

    return keyboard.as_markup()


async def confirm_worker_delete(id: str):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(text=labels.YES, callback_data=f"confirm_delete_worker_{id}"),
        InlineKeyboardButton(text=labels.NO, callback_data="denied_dismiss_worker"),
    )

    return keyboard.as_markup()


async def confirm_rate_change(id: str, new_rate: str):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(text=labels.YES, callback_data=f"confirm_change_rate_{id}_{new_rate}")
    )

    keyboard.row(InlineKeyboardButton(text=labels.NO, callback_data="denied_change_"))
    return keyboard.as_markup()


async def confirm_job_change(id: str, job: str):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(text=labels.YES, callback_data=f"confirm_change_job_{id}_{job}")
    )

    keyboard.row(InlineKeyboardButton(text=labels.NO, callback_data="denied_change_"))
    return keyboard.as_markup()


async def confirm_add_master(id: str, factory_id: str, tg_id: str):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(
            text=labels.YES, callback_data=f"confirm_add_master_{id}_{factory_id}_{tg_id}"
        )
    )

    keyboard.row(InlineKeyboardButton(text=labels.NO, callback_data="add_denied"))
    return keyboard.as_markup()


async def master_info_kb(role: Role, id: str, back_page: int, factory_id: str = ""):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(text=labels.EDIT_FACTORY, callback_data=f"edit_master_factory_{id}"),
    )

    keyboard.row(
        InlineKeyboardButton(text=labels.MASTER_REMOVE, callback_data=f"remove_master_{id}"),
    )

    if not factory_id:
        keyboard.row(
            InlineKeyboardButton(text=labels.RETURN, callback_data=f"page_{role}_{back_page}"),
            InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb"),
        )
    else:
        keyboard.row(
            InlineKeyboardButton(
                text=labels.RETURN, callback_data=f"master_list_factory_{factory_id}"
            ),
            InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb"),
        )

    return keyboard.as_markup()


async def confirm_edit_factory(id: str, factory_id: str):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(
            text=labels.YES, callback_data=f"confirm_edit_master_factory_{id}_{factory_id}"
        )
    )

    keyboard.row(InlineKeyboardButton(text=labels.NO, callback_data="denied_change_"))
    return keyboard.as_markup()


async def confirm_master_delete(id: str):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(text=labels.YES, callback_data=f"confirm_delete_master_{id}"),
        InlineKeyboardButton(text=labels.NO, callback_data="denied_dismiss_master"),
    )

    return keyboard.as_markup()


async def confirm_edit_worker_by_master(number: str, worker_index: str):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(
            text=labels.YES, callback_data=f"confirm_edit_worker_by_master_{worker_index}_{number}"
        ),
        InlineKeyboardButton(
            text=labels.NO, callback_data=f"not_confirm_edit_worker_by_master_{number}"
        ),
    )

    return keyboard.as_markup()


async def confirm_shift_menu(number: str):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(text=labels.EDITING, callback_data=f"edit_not_save_shift_{number}")
    )
    keyboard.row(InlineKeyboardButton(text=labels.WRITE_SHIFT, callback_data="write_shift"))
    keyboard.row(InlineKeyboardButton(text=labels.DENIE_SHIFT, callback_data="denie_shift"))

    return keyboard.as_markup()


async def factory_master_list(factory_id: str, key: str = ""):
    keyboard = InlineKeyboardBuilder()

    master_list = await requests.get_masters_by_factory(int(factory_id))

    if not master_list:
        return None

    for m in master_list:
        keyboard.row(
            InlineKeyboardButton(
                text=m.fullname, callback_data=f"{key}{Role.MASTER}_{m.id}_{1}_{factory_id}"
            )
        )

    if key == "edit_shift_":
        keyboard.row(
            InlineKeyboardButton(
                text=labels.CANCEL_EDITING, callback_data="not_confirm_edit_shift_report"
            ),
            InlineKeyboardButton(text=labels.RETURN, callback_data=f"{key}factory_"),
        )
    else:
        logger.debug(f"{key}factory_{factory_id}")
        keyboard.row(
            InlineKeyboardButton(text=labels.RETURN, callback_data=f"{key}factory_{factory_id}"),
            InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb"),
        )

    return keyboard.as_markup()


async def back_to_edit_shift_factory(factory_id: str):
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(
            text=labels.CANCEL_EDITING, callback_data="not_confirm_edit_shift_report"
        ),
        InlineKeyboardButton(text=labels.RETURN, callback_data=f"edit_shift_factory_{factory_id}"),
    )
    return keyboard.as_markup()


async def report_date_list():
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(
            text=labels.CURRENT_MONTH.format(MONTHS.get(Month.Current().month)),
            callback_data=f"reportdate_{Month.Current().year}_{Month.Current().month}",
        )
    )
    keyboard.row(
        InlineKeyboardButton(
            text=labels.PREV_MONTH.format(MONTHS.get(Month.Prev().month)),
            callback_data=f"reportdate_{Month.Current().year}_{Month.Prev().month}",
        )
    )
    keyboard.row(
        InlineKeyboardButton(text=labels.ANOTHER, callback_data="reportdate_"),
        InlineKeyboardButton(text=labels.CLOSE, callback_data="close_kb"),
    )
    return keyboard.as_markup()


async def get_shift_list(master_id: str, factory_id: str, shift_date: date):
    keyboard = InlineKeyboardBuilder()

    shift_list = await requests.get_shift_by_date(
        user_id=int(master_id), factory_id=int(factory_id), day=shift_date
    )

    if not shift_list:
        return None

    for shift in shift_list:
        keyboard.row(
            InlineKeyboardButton(
                text="Смена от " + str(shift.datetime.strftime("%H:%M")),
                callback_data=f"edit_shift_number_{shift.datetime.strftime("%H:%M")}_{shift.id}",
            )
        )

    keyboard.row(
        InlineKeyboardButton(
            text=labels.CANCEL_EDITING, callback_data="not_confirm_edit_shift_report"
        ),
        InlineKeyboardButton(text=labels.RETURN, callback_data=f"edit_shift_factory_{factory_id}"),
    )

    return keyboard.as_markup()


async def get_workers_by_shift(shift_id: str):
    keyboard = InlineKeyboardBuilder()

    positions = await requests.get_positions_by_shift_id(int(shift_id))

    for pos, _ in positions:
        user = await requests.get_user(pos.user_id, use_tg=False)
        keyboard.row(
            InlineKeyboardButton(
                text=user.fullname,
                callback_data=f"shift_pos_worker_{pos.id}_{pos.activity_id}_{pos.user_id}",
            )
        )

    keyboard.row(
        InlineKeyboardButton(
            text=labels.CANCEL_EDITING, callback_data="not_confirm_edit_shift_report"
        )
    )

    return keyboard.as_markup()
