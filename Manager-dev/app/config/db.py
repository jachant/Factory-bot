import os

DB_URL = f"postgresql+asyncpg://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}\
@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"


class UserLen:
    fullname = 40


class FactoryLen:
    company_name = 30
    factory_name = 30


class WorkerProfileLen:
    job = 20


class ActivityLen:
    code = 5
    description = 60


class TimesheetLen:
    link = 100


class CorrectionLen:
    reason = 100
