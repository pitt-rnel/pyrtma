class DataLoggerError(Exception):
    pass


class BasePathNotFound(DataLoggerError):
    pass


class MissingMetadata(DataLoggerError):
    pass


class DataCollectionNotConfigured(DataLoggerError):
    pass


class DataCollectionNotFound(DataLoggerError):
    pass


class DataCollectionInProgress(DataLoggerError):
    pass


class InvalidFormatter(DataLoggerError):
    pass


class DataSetExistsError(DataLoggerError):
    pass


class DataCollectionThreadError(DataLoggerError):
    pass


class DataFormatterKeyError(DataLoggerError):
    pass


class DataCollectionFullError(DataLoggerError):
    pass


class InvalidMetadata(DataLoggerError):
    pass
