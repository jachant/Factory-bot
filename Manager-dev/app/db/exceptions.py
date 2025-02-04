class DBError(Exception):
    """Ошибка в модуле БД.

    Args:
        Exception (_type_): Exception
    """


class BadKeyError(DBError):
    """Ошибка невалидного ключа в БД.
    Args:
        Exception (_type_): DBError
    """

    pass


class BadFormatError(DBError):
    """Ошибка неправильных данных, переданных в БД.
    Args:
        Exception (_type_): DBError
    """

    pass


class AlreadyExistsError(DBError):
    """Ошибка неправильных данных, переданных в БД.
    Args:
        Exception (_type_): DBError
    """

    pass
