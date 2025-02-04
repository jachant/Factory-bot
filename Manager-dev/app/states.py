from aiogram.fsm.state import State, StatesGroup


class PickAdmin(StatesGroup):
    """States для выбора админа.

    Args:
        StatesGroup (_type_): _description_
    """

    id = State()
    name = State()


class PickMaster(StatesGroup):
    """States для выбора админа.

    Args:
        StatesGroup (_type_): _description_
    """

    id = State()
    name = State()


class PickFactory(StatesGroup):
    company_name = State()
    factory_name = State()


class PickActivityCode(StatesGroup):
    code = State()
    duration = State()
    description = State()
    color = State()


class PickWorker(StatesGroup):
    name = State()
    job = State()
    rate = State()


class ChangeRate(StatesGroup):
    new_rate = State()
    id = State()


class ChangeJob(StatesGroup):
    new_job = State()
    id = State()


class AddMaster(StatesGroup):
    id = State()
    tg_id = State()
    factory_id = State()


class ShiftReport(StatesGroup):
    master_id = State()
    factory_id = State()
    master_activity = State()
    workers_list = State()
    activity_list = State()
    temp_worker = State()
    temp_activity = State()
    shift_photo = State()
    date = State()


class SaveReport(StatesGroup):
    year = State()
    month = State()
    factory_id = State()


class EditShift(StatesGroup):
    await_date = State()
    have_date = State()
    explanation = State()
    confirm = State()
