from datetime import date, datetime
from typing import Sequence, Tuple

from sqlalchemy import (
    Date,
    and_,
    case,
    cast,
    desc,
    false,
    func,
    or_,
    select,
    true,
    union,
)
from sqlalchemy.engine.row import Row, RowMapping
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import aliased

from app.config.roles import Role
from app.db.exceptions import AlreadyExistsError, BadFormatError, BadKeyError, DBError
from app.db.models import (
    Activity,
    Correction,
    Factory,
    MasterFactory,
    Timesheet,
    User,
    WorkerPosition,
    WorkerPositionActual,
    WorkerProfile,
    async_session,
)
from app.utils import setup_logger
from app.utils.month import Month
from app.utils.uploader import get_disk_link, upload_photos

logger = setup_logger(__name__)


# Работа с User


async def get_users_by_role(role: Role) -> Sequence[User]:
    """Получение User по Role

    Args:
        role (Role): Роль пользователя. Если нужно выбрать несколько ролей, то используем `|`,
                    например, role = Role.WORKER | Role.MASTER | Role.USER

    Returns:
        Sequence[User]: Массив всех найдённых User.
    """
    logger.debug(f"Получение user'ов ро роли (role={role})")
    async with async_session() as session:
        users = await session.scalars(
            select(User).where(User.role.op("&")(role) != 0).order_by(User.fullname)
        )
        return users.all()


async def get_user(id: int, use_tg: bool = True) -> User:
    logger.debug(f"Получение user (id={id}, use_tg={use_tg})")
    async with async_session() as session:
        condition = User.tg_id if use_tg else User.id
        user: User = await session.scalar(select(User).where(condition == id))

        if not user:
            raise BadKeyError()
        return user


async def set_user(tg_id: int = None) -> User:
    """Добавляет пользователя в таблицу, если тот не сущесвует.

    Args:
        tg_user_id (_type_, optional): Defaults to None.

    Returns:
        int: user_id внутри системы.
    """
    logger.debug(f"Установка user (tg_id={tg_id})")
    async with async_session() as session:
        user: User = await session.scalar(select(User).where(User.tg_id == tg_id))

        if not user:
            logger.info(f"User (tg_id={tg_id}) не существует. Добавляем...")
            user = User(tg_id=tg_id)
            session.add(user)
            await session.commit()
        return user


async def update_user(id: int, values: dict, use_tg: bool = True) -> None:
    """Обновление сущности пользователя.

    Args:
        tg_id (int): tg_user_id
        values (dict): Данные для обновления в формате {User.field1: new_value1,
                                                        User.field2: new_value2}

    Raises:
        DBKeyError: Ошибка неверного ключа.
        DBBadDataError: Ошибка неверного формата данных.
    """
    logger.debug(f"Обновление user (id={id}, use_tg={use_tg}) с values={values.values()}")
    async with async_session() as session:
        condition = User.tg_id if use_tg else User.id
        user: User = await session.scalar(select(User).where(condition == id))

        if not user:
            raise BadKeyError()

        try:
            if User.tg_id in values:
                check_user = await session.scalar(
                    select(User).where(User.tg_id == values.get(User.tg_id))
                )
                if check_user.role == Role.USER:
                    check_user.tg_id = None
                    await session.flush()

            user.tg_id = values.get(User.tg_id, user.tg_id)
            user.fullname = values.get(User.fullname, user.fullname)
            user.role = values.get(User.role, user.role)
            await session.commit()
        except Exception as ex:
            raise BadFormatError(ex)


async def get_report_users(factory_id: int, year: int, month: int):
    logger.debug(f"Получение Workers для Factory (factory_id={factory_id}) за ({year}-{month})")
    async with async_session() as session:
        users = await session.execute(
            select(
                User,
                case((User.id == Timesheet.user_id, true()), else_=false()).label("is_master"),
            )
            .join(WorkerPositionActual, WorkerPositionActual.user_id == User.id)
            .join(Timesheet, Timesheet.id == WorkerPositionActual.timesheet_id)
            .where(
                Timesheet.factory_id == factory_id,
                func.extract("year", Timesheet.datetime) == year,
                func.extract("month", Timesheet.datetime) == month,
            )
            .order_by(User.fullname)
            .distinct()
        )

        return users.all()


# Работа с Factory


async def set_factory(company_name: str, factory_name: str) -> Factory:
    """Устанавливет или обновляет завод.

    Args:
        company_name (str): Имя компании завода.
        factory_name (str): Имя завода.

    Returns:
        Factory: Сущность завода.
    """
    logger.debug(f"Установка factory (company={company_name}, factory={factory_name})")
    async with async_session() as session:
        factory = Factory(company_name=company_name, factory_name=factory_name)
        session.add(factory)
        try:
            await session.commit()
        except IntegrityError:
            raise AlreadyExistsError()
        except Exception as ex:
            raise DBError(ex)
        return factory


async def get_factory(id: int) -> Factory:
    logger.debug(f"Получение factory (id={id})")
    async with async_session() as session:
        factory: Factory = await session.scalar(select(Factory).where(Factory.id == id))

        if not factory:
            raise BadKeyError()
        return factory


async def delete_factory(id: int) -> None:
    logger.debug(f"Удаление factory (id={id})")
    async with async_session() as session:
        factory: Factory = await session.scalar(select(Factory).where(Factory.id == id))

        if not factory:
            raise BadKeyError()
        factory.is_deleted = True
        await session.commit()


async def get_factories(deleted: bool = False) -> Sequence[Factory]:
    logger.debug(f"Получение factories (deleted={deleted})")
    async with async_session() as session:
        factories = await session.scalars(select(Factory).where(Factory.is_deleted.is_(deleted)))
        return factories.all()


# Работа с Master


async def set_factory_to_master(user_id: int, factory_id: int) -> MasterFactory:
    logger.debug(f"Назначение user'у завода (user_id={user_id}, factory_id={factory_id})")
    async with async_session() as session:
        master_factory = await session.scalar(
            select(MasterFactory).where(MasterFactory.user_id == user_id)
        )
        if not master_factory:
            master_factory = MasterFactory(user_id=user_id, factory_id=factory_id)
            session.add(master_factory)
        else:
            master_factory.factory_id = factory_id
        try:
            await session.commit()
        except IntegrityError:
            raise AlreadyExistsError()
        except BadKeyError:
            raise
        except Exception as ex:
            raise DBError(ex)
        return master_factory


async def get_factory_by_user(id: int, use_tg: bool = False) -> Factory:
    """Получение сущности завода по id юзера (по умолчанию используется внутренний).

    Args:
        id (int): id юзера
        use_tg (bool, optional): Использовать tg_id. Defaults to False.

    Returns:
        Factory: Сущность завода.
    """
    logger.debug(f"Получение factory для User (user_id={id}, use_tg={use_tg})")
    async with async_session() as session:
        user_id = id
        if use_tg:
            user = await get_user(id)
            user_id = user.id
        factory = await session.scalar(
            select(Factory)
            .join(MasterFactory, Factory.id == MasterFactory.factory_id)
            .where(MasterFactory.user_id == user_id)
        )
        return factory


async def get_masters_by_factory(factory_id: int) -> Sequence[User]:
    logger.debug(f"Получение masters по Factory (factory_id={factory_id})")
    async with async_session() as session:
        users = await session.scalars(
            select(User)
            .join(MasterFactory, User.id == MasterFactory.user_id)
            .where(MasterFactory.factory_id == factory_id)
            .order_by(User.fullname)
        )
        return users.all()


# Работа с Activity


async def set_activity(
    code: str, duration: float, description: str, color: str = "ffffff"
) -> Activity:
    logger.debug(
        f"Установка activity (code={code}, duration={duration}, desc={description}, color={color})"
    )
    async with async_session() as session:
        # Проверка кода с таким же code и is_deleted == False
        current_activity = await session.scalar(
            select(Activity).where(Activity.code == code, Activity.is_deleted.is_(False))
        )
        if current_activity:
            raise AlreadyExistsError()
        logger.debug("Активного кода не существует, создаём...")

        activity = Activity(
            code=code, duration=duration, description=description, color=color.lower()
        )
        session.add(activity)
        try:
            await session.commit()
        except (IntegrityError, DBAPIError) as ex:
            logger.error(ex)
            if not hasattr(ex.orig, "pgcode"):
                raise DBError(ex)
            raise BadFormatError(ex)
        except Exception as ex:
            raise DBError(ex)
        return activity


async def delete_activity(id: int) -> None:
    logger.debug(f"Удаление activity (id={id})")
    async with async_session() as session:
        activity: Activity = await session.scalar(select(Activity).where(Activity.id == id))

        if not activity:
            raise BadKeyError()
        activity.is_deleted = True
        await session.commit()


async def get_activities(deleted: bool = False) -> Sequence[Activity]:
    """Получение списка активностей.

    Args:
        deleted (bool, optional): Вернуть только удалённые. Defaults to False.

    Returns:
        _type_: _description_
    """
    logger.debug(f"Получение activities (deleted={deleted})")
    async with async_session() as session:
        activities = await session.scalars(
            select(Activity).where(Activity.is_deleted.is_(deleted))
        )
        return activities.all()


async def get_report_activities(factory_id: int, year: int, month: int) -> Sequence[Activity]:
    logger.debug(f"Получение Activities для Factory (factory_id={factory_id}) за ({year}-{month})")
    async with async_session() as session:
        activity_subquery = union(
            select(
                WorkerPosition.activity_id.label("activity_id"),
                WorkerPosition.id.label("worker_position_id"),
            ),
            select(
                Correction.new_activity_id.label("activity_id"),
                Correction.worker_position_id,
            ),
        ).subquery()

        activities = await session.scalars(
            select(Activity)
            .join(activity_subquery, activity_subquery.c.activity_id == Activity.id)
            .join(WorkerPosition, WorkerPosition.id == activity_subquery.c.worker_position_id)
            .join(Timesheet, Timesheet.id == WorkerPosition.timesheet_id)
            .where(
                Timesheet.factory_id == factory_id,
                func.extract("year", Timesheet.datetime) == year,
                func.extract("month", Timesheet.datetime) == month,
            )
            .order_by(Activity.is_deleted)
            .distinct()
        )

        return activities.all()


async def get_report_user_activities(factory_id: int, user_id: int, year: int, month: int):
    logger.debug(
        f"Получение User Activities для Factory\
(factory_id={factory_id}, user_id={user_id}) за ({year}-{month})"
    )
    async with async_session() as session:
        activities = await session.execute(
            select(Activity, Timesheet.datetime, Timesheet.link)
            .join(
                WorkerPositionActual,
                WorkerPositionActual.activity_id == Activity.id,
            )
            .join(Timesheet, Timesheet.id == WorkerPositionActual.timesheet_id)
            .where(
                Timesheet.factory_id == factory_id,
                WorkerPositionActual.user_id == user_id,
                func.extract("year", Timesheet.datetime) == year,
                func.extract("month", Timesheet.datetime) == month,
            )
            .order_by(Timesheet.datetime)
        )

        return activities.fetchall()


async def get_activity(id: int) -> Activity:
    logger.debug(f"Получение activity (id={id})")
    async with async_session() as session:
        activity: Activity = await session.scalar(select(Activity).where(Activity.id == id))

        if not activity:
            raise BadKeyError()
        return activity


# Работа с Worker


async def set_profile(fullname: str, job: str, rate: float) -> WorkerProfile:
    logger.debug(f"Установка profile для user (fullname={fullname}, job={job}, rate={rate})")
    async with async_session() as session:
        user = User(fullname=fullname, role=Role.WORKER)
        session.add(user)
        await session.flush()

        profile = WorkerProfile(user_id=user.id, job=job, rate=rate)
        session.add(profile)
        await session.commit()


async def change_profile(user_id, values: dict) -> None:
    logger.debug(f"Обновление profile у User (user_id={user_id}) с values={values.values()}")
    async with async_session() as session:
        next_month = Month.Next()
        profile: WorkerProfile = await session.scalar(
            select(WorkerProfile).where(
                WorkerProfile.user_id == user_id,
                WorkerProfile.year == next_month.year,
                WorkerProfile.month == next_month.month,
            )
        )

        try:
            if not profile:
                # Duplicate + change current profile
                cur_profile = await get_profile(user_id)
                session.add(
                    WorkerProfile(
                        user_id=user_id,
                        year=next_month.year,
                        month=next_month.month,
                        job=values.get(WorkerProfile.job, cur_profile.job),
                        rate=values.get(WorkerProfile.rate, cur_profile.rate),
                    )
                )
            else:
                profile.job = values.get(WorkerProfile.job, profile.job)
                profile.rate = values.get(WorkerProfile.rate, profile.rate)
            await session.commit()
        except BadKeyError:
            raise
        except Exception as ex:
            raise BadFormatError(ex)


async def get_profile(user_id: int, year: int = None, month: int = None) -> WorkerProfile:
    if not year:
        year = datetime.now().year
    if not month:
        month = datetime.now().month
    logger.debug(f"Получение worker profile (user_id={user_id}, year={year}, month={month})")
    async with async_session() as session:
        worker_profile: WorkerProfile = await session.scalar(
            select(WorkerProfile)
            .where(
                WorkerProfile.user_id == user_id,
                or_(
                    WorkerProfile.year < year,
                    and_(WorkerProfile.year == year, WorkerProfile.month <= month),
                ),
            )
            .order_by(desc(WorkerProfile.year), desc(WorkerProfile.month))
        )

        if not worker_profile:
            raise BadKeyError("Не существует worker profile")
        return worker_profile


# Работа с отчётом о смене


async def add_shift(
    user_id: int,
    factory_id: int,
    photo_paths: list[str],
    positions: list[dict],
    shift_datetime: datetime = None,
) -> None:
    """Добавление смены от мастера.

    Args:
        user_id (int): user_id мастера.
        factory_id (int): id предприятия.
        photo_link (str): Ссылка на фото табеля.
        positions (list[{User.id: id, Activity.id: id},...]): Позиции рабочих.
        shift_datetime: (datetime): Custom shift datetime. Default: None
    """
    logger.debug(f"Регистрация смены от user (user_id={user_id}), photo_paths={photo_paths}")
    if not shift_datetime:
        logger.debug("shift_datetime is null, set current")
        shift_datetime = datetime.now()
    async with async_session() as session:
        user = await get_user(user_id, use_tg=False)
        factory = await get_factory(factory_id)
        timesheet = Timesheet(user_id=user.id, factory_id=factory.id, datetime=shift_datetime)
        session.add(timesheet)
        await session.flush()

        # Попытка загрузить фото табеля
        timesheet.link = await upload_photos(
            photo_paths, factory, user.fullname, timesheet.datetime
        )
        if not timesheet.link:
            logger.critical("Не удалось загрузить фото табеля после попыток. Установка затычки...")
            timesheet.link = await get_disk_link()

        for pos in positions:
            session.add(
                WorkerPosition(
                    timesheet_id=timesheet.id,
                    user_id=pos.get(User.id),
                    activity_id=pos.get(Activity.id),
                )
            )
        await session.commit()


async def get_shift_by_date(user_id: int, factory_id: int, day: date = None):
    """Получает последние n смен для данного мастера и завода.

    Args:
        user_id (int): Внутренний id мастера.

    Returns:
        Sequence[Timesheet]: Сущности смен.
    """
    logger.debug(f"Получение смен за ({day}) от user (user_id={user_id}, factory_id={factory_id})")
    async with async_session() as session:
        conditions = [
            Timesheet.factory_id == factory_id,
            Timesheet.user_id == user_id,
        ]
        if day:
            conditions.append(cast(Timesheet.datetime, Date) == day)
        last_timesheets = await session.scalars(
            select(Timesheet).where(*conditions).order_by(desc(Timesheet.datetime))
        )
        if day:
            return last_timesheets.all()
        else:
            res = last_timesheets.first()
            return [res] if res else None


async def get_shifts_count(factory_id: int, year: int, month: int):
    logger.debug(
        f"Получение кол-ва смен в дни месяца (factory_id={factory_id}) за ({year}-{month})"
    )
    async with async_session() as session:
        nums = await session.execute(
            select(
                func.date(Timesheet.datetime).label("date"),
                func.count(Timesheet.id).label("count"),
            )
            .where(
                Timesheet.factory_id == factory_id,
                func.extract("year", Timesheet.datetime) == year,
                func.extract("month", Timesheet.datetime) == month,
            )
            .group_by(func.date(Timesheet.datetime))
            .order_by(func.date(Timesheet.datetime))
        )
        res = {row.date.day: row.count for row in nums}

        return res


async def get_positions_by_shift_id(
    timesheet_id: int,
) -> Sequence[Row[Tuple[WorkerPositionActual, str]]]:
    logger.debug(f"Получение состава timesheet (timesheet_id={timesheet_id})")
    async with async_session() as session:
        worker_positions = await session.execute(
            select(WorkerPositionActual, Activity.code)
            .join(User, User.id == WorkerPositionActual.user_id)
            .join(Activity, WorkerPositionActual.activity_id == Activity.id)
            .where(WorkerPositionActual.timesheet_id == timesheet_id)
        )
        return worker_positions.all()


async def correct_worker_position(
    tg_id: int, worker_position_id: int, new_activity_id: int, reason: str
):
    """Устанавливает новое значение для позиции в табеле.

    Args:
        tg_id (int): tg_id админа, который вносит правку.
        worker_position_id (int): Позиция в табеле.
        new_activity_id (int): Новый код.
        reason (str): Причина редактирования.
    """
    logger.debug(
        f"Редактирование WorkerPosition (id={worker_position_id}) админом (tg_id={tg_id})"
    )
    async with async_session() as session:
        user = await get_user(tg_id)
        session.add(
            Correction(
                worker_position_id=worker_position_id,
                user_id=user.id,
                new_activity_id=new_activity_id,
                reason=reason,
            )
        )
        await session.commit()


async def get_report_corrections(factory_id: int, year: int, month: int) -> Sequence[RowMapping]:
    from app.config.genexcel import CorrectionFields

    logger.debug(f"Получение Correction для Factory (factory_id={factory_id}) за ({year}-{month})")
    async with async_session() as session:
        user_master = aliased(User)
        user_worker = aliased(User)
        activity_new = aliased(Activity)
        activity_init = aliased(Activity)
        corrections = await session.execute(
            select(
                Correction.datetime.label(CorrectionFields.NEW_DATE),
                Correction.reason.label(CorrectionFields.REASON),
                activity_new.code.label(CorrectionFields.NEW_CODE),
                activity_new.id.label(CorrectionFields.NEW_CODE_ID),
                Timesheet.datetime.label(CorrectionFields.INIT_DATE),
                activity_init.code.label(CorrectionFields.INIT_CODE),
                activity_init.id.label(CorrectionFields.INIT_CODE_ID),
                user_master.fullname.label(CorrectionFields.MASTER),
                user_worker.fullname.label(CorrectionFields.WORKER),
            )
            .join(WorkerPosition, WorkerPosition.id == Correction.worker_position_id)
            .join(Timesheet, Timesheet.id == WorkerPosition.timesheet_id)
            .join(user_master, user_master.id == Timesheet.user_id)
            .join(user_worker, user_worker.id == WorkerPosition.user_id)
            .join(activity_new, activity_new.id == Correction.new_activity_id)
            .join(activity_init, activity_init.id == WorkerPosition.activity_id)
            .where(
                Timesheet.factory_id == factory_id,
                func.extract("year", Timesheet.datetime) == year,
                func.extract("month", Timesheet.datetime) == month,
            )
            .order_by(user_worker.fullname, desc(Correction.datetime))
        )

        return corrections.mappings().all()
