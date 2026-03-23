from logging import Formatter, Logger, StreamHandler, getLogger

import logfire

from .config import settings


def logger_setup(name: str):
    logger = getLogger(name)
    logger.setLevel("INFO")
    log_formatter = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler = (
        StreamHandler()
        if settings.LOGFIRE_TOKEN is None
        else logfire.LogfireLoggingHandler()
    )
    handler.setFormatter(log_formatter)
    logger.addHandler(handler)
    return logger


class LoggerWrapper:
    logger: Logger
    prefix: str

    def __init__(self, logger: Logger, prefix: str = ""):
        self.logger = logger
        self.prefix = prefix

    def _wrap(self, message: str) -> str:
        return f"{self.prefix}{message}"

    def error(self, message: str):
        self.logger.error(self._wrap(message))

    def warning(self, message: str):
        self.logger.warning(self._wrap(message))

    def info(self, message: str):
        self.logger.info(self._wrap(message))

    def debug(self, message: str):
        self.logger.debug(self._wrap(message))
