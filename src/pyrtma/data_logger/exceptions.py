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
