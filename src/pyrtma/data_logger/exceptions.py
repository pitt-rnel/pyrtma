"""data_logger exceptions"""


class DataLoggerError(Exception):
    pass


class DataSetNotConfigured(DataLoggerError):
    pass


class DataSetNotFound(DataLoggerError):
    pass


class DataSetInProgress(DataLoggerError):
    pass


class InvalidFormatter(DataLoggerError):
    pass


class DataSetExistsError(DataLoggerError):
    pass


class DataSetThreadError(DataLoggerError):
    pass


class DataFormatterKeyError(DataLoggerError):
    pass


class DataLoggerFullError(DataLoggerError):
    pass


class NoClientError(DataLoggerError):
    """Client must first be registered to DataSetConfig"""

    def __init__(self, msg=None, *args, **kwargs):
        super().__init__(msg or self.__doc__, *args, **kwargs)
