"""data_logger exceptions"""


class DataLoggerError(Exception):
    def __init__(self, dataset: str = "", msg: str = ""):
        self.dataset = dataset
        self.msg = msg

        super().__init__(msg)


class DatasetNotConfigured(DataLoggerError):
    pass


class DatasetError(DataLoggerError):
    pass


class DatasetNotFound(DatasetError):
    pass


class DatasetInProgress(DatasetError):
    pass


class InvalidFormatter(DatasetError):
    pass


class DatasetExistsError(DatasetError):
    pass


class DatasetThreadError(DatasetError):
    pass


class DataFormatterKeyError(DataLoggerError):
    pass


class DataLoggerFullError(DatasetError):
    pass


class NoClientError(DataLoggerError):
    """Client must first be registered to Dataset"""

    def __init__(self):
        super().__init__(msg=self.__doc__ or "")
