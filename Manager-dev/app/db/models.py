from datetime import datetime

from sqlalchemy import (
    DDL,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    delete,
    event,
    select,
    update,
)
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.config.db import (
    DB_URL,
    ActivityLen,
    CorrectionLen,
    FactoryLen,
    TimesheetLen,
    UserLen,
    WorkerProfileLen,
)
from app.config.roles import Role
from app.db.exceptions import BadKeyError

engine = create_async_engine(
    url=DB_URL,
    echo=False,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=True)
    fullname: Mapped[str] = mapped_column(String(UserLen.fullname), nullable=True)
    reg_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    role: Mapped[int] = mapped_column(SmallInteger, default=Role.USER, nullable=False)


@event.listens_for(User, "after_update")
def delete_master_factory_entry(mapper, connection, target: User):
    """Удаление привязки мастера к заводу, если мастера сняли с должности.

    Args:
        mapper (_type_): _description_
        connection (_type_): _description_
        target (User): _description_
    """
    session = Session(bind=connection)
    if target.role == Role.MASTER:
        return
    session.execute(delete(MasterFactory).where(MasterFactory.user_id == target.id))


class Factory(Base):

    __tablename__ = "factory"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    company_name: Mapped[str] = mapped_column(String(FactoryLen.company_name), nullable=False)
    factory_name: Mapped[str] = mapped_column(String(FactoryLen.factory_name), nullable=False)

    __table_args__ = (UniqueConstraint("company_name", "factory_name", name="uq_factory_company"),)


@event.listens_for(Factory, "after_update")
def delete_master_factory_entries(mapper, connection, target: Factory):
    """Удаление всех мастеров с завода, если завод удалён.

    Args:
        mapper (_type_): _description_
        connection (_type_): _description_
        target (Factory): _description_
    """
    session = Session(bind=connection)
    if target.is_deleted is True:
        subquery = (
            select(User.id)
            .join(MasterFactory, MasterFactory.user_id == User.id)
            .where(MasterFactory.factory_id == target.id)
            .scalar_subquery()
        )
        session.execute(update(User).where(User.id.in_(subquery)).values(role=Role.WORKER))
        session.execute(delete(MasterFactory).where(MasterFactory.factory_id == target.id))


class MasterFactory(Base):

    __tablename__ = "master_factory"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), primary_key=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("factory.id"), primary_key=True)


@event.listens_for(MasterFactory, "before_insert")
def check_user_role_before_insert(mapper, connection, target: MasterFactory):
    """Проверка, чтобы к заводу привязывали только мастера.

    Args:
        mapper (_type_): _description_
        connection (_type_): _description_
        target (MasterFactory): _description_

    Raises:
        BadKeyError: _description_
    """
    session = Session(bind=connection)
    user: User = session.scalar(select(User).where(User.id == target.user_id))
    # Only masters can have factory
    if user is None or user.role != Role.MASTER:
        raise BadKeyError("User не является мастером")


class WorkerProfile(Base):

    __tablename__ = "worker_profile"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), primary_key=True)
    month: Mapped[int] = mapped_column(
        SmallInteger, default=lambda: datetime.now().month, primary_key=True
    )
    year: Mapped[int] = mapped_column(
        SmallInteger, default=lambda: datetime.now().year, primary_key=True
    )
    job: Mapped[str] = mapped_column(String(WorkerProfileLen.job), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(5, 2), default=1, nullable=False)

    __table_args__ = (
        CheckConstraint("month >= 1 AND month <= 12", name="valid_month"),
        CheckConstraint("year >= 1900 AND year <= 2100", name="valid_year"),
        CheckConstraint("rate >= 0", name="valid_rate"),
    )


class Activity(Base):

    __tablename__ = "activity"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(ActivityLen.code), index=True, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duration: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    description: Mapped[str] = mapped_column(String(ActivityLen.description), nullable=False)
    color: Mapped[str] = mapped_column(String(6), nullable=False)

    __table_args__ = (
        CheckConstraint("color ~ '^[0-9a-f]{6}$'", name="valid_hex_color"),
        CheckConstraint("duration >= 0", name="check_duration_non_negative"),
    )


class Timesheet(Base):

    __tablename__ = "timesheet"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))  # Master id
    factory_id: Mapped[int] = mapped_column(ForeignKey("factory.id"))
    datetime: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    link: Mapped[str] = mapped_column(String(TimesheetLen.link), nullable=True)


class WorkerPosition(Base):

    __tablename__ = "worker_position"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timesheet_id: Mapped[int] = mapped_column(ForeignKey("timesheet.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))  # Worker id
    activity_id: Mapped[int] = mapped_column(ForeignKey("activity.id"))


class Correction(Base):

    __tablename__ = "correction"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    worker_position_id: Mapped[int] = mapped_column(ForeignKey("worker_position.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))  # Admin id
    new_activity_id: Mapped[int] = mapped_column(ForeignKey("activity.id"))
    reason: Mapped[str] = mapped_column(String(CorrectionLen.reason), nullable=False)
    datetime: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class WorkerPositionActual(Base):
    __tablename__ = "worker_position_view"

    id: Mapped[int] = mapped_column(primary_key=True)
    timesheet_id: Mapped[int] = mapped_column()
    user_id: Mapped[int] = mapped_column()  # Worker id
    activity_id: Mapped[int] = mapped_column()


async def db_init():
    """Асинхронная инициализация БД, генерация таблиц."""
    from app.utils import setup_logger

    logger = setup_logger(__name__)

    async with engine.connect() as conn:
        logger.info("Инициализация БД")
        await conn.run_sync(Base.metadata.create_all)
        await conn.commit()
        try:
            # Удаление созданной таблицы WorkerPositionActual для избегания конфликтов
            await conn.run_sync(Base.metadata.tables[WorkerPositionActual.__tablename__].drop)
            await conn.commit()
        except ProgrammingError:
            await conn.rollback()
        await conn.execute(VIEW_WORKERS_DDL)
        await conn.commit()


# Представление, которое возвращает WorkerPosition с актуальным изменением
VIEW_WORKERS_DDL = DDL(
    """
CREATE OR REPLACE VIEW worker_position_view AS
SELECT
    wp.id,
    wp.timesheet_id,
    wp.user_id,
    COALESCE(c.new_activity_id, wp.activity_id) AS activity_id
FROM worker_position wp
LEFT JOIN LATERAL (
    SELECT new_activity_id
    FROM correction
    WHERE worker_position_id = wp.id
    ORDER BY datetime DESC
    LIMIT 1
) c ON true;
"""
)
