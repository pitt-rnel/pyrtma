"""data_logger exceptions"""


class DataLoggerError(Exception):
    def __init__(self, dataset: str = "", msg: str = ""):
        self.dataset = dataset
        self.msg = msg

        super().__init__(msg)


class DataSetNotConfigured(DataLoggerError):
    pass


class DataSetError(DataLoggerError):
    pass


class DataSetNotFound(DataSetError):
    pass


class DataSetInProgress(DataSetError):
    pass


class InvalidFormatter(DataSetError):
    pass


class DataSetExistsError(DataSetError):
    pass


class DataSetThreadError(DataSetError):
    pass


class DataFormatterKeyError(DataLoggerError):
    pass


class DataLoggerFullError(DataSetError):
    pass


class NoClientError(DataLoggerError):
    """Client must first be registered to Dataset"""

    def __init__(self):
        super().__init__(msg=self.__doc__ or "")
