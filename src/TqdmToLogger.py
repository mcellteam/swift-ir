import logging
import io

__all__ = ['TqdmToLogger']

# class TqdmToLogger(io.StringIO):
#     """
#         Output stream for TQDM which will output to logger module instead of
#         the StdOut.
#     """
#     logger = None
#     level = None
#     buf = ''
#     def __init__(self,logger,level=None):
#         super(TqdmToLogger, self).__init__()
#         # self.logger = logger
#         self.logger = logging.getLogger(__name__)
#         self.level = level or logging.INFO
#     def write(self,buf):
#         self.buf = buf.strip('\r\n\t ')
#     def flush(self):
#         # self.logger.log(self.level, self.buf)
#         self.logger.log(self.level, self.buf)

import logging as log

from tqdm import tqdm
from io import StringIO

class TqdmLogFormatter(object):
    def __init__(self, logger):
        self._logger = logger

    def __enter__(self):
        self.__original_formatters = list()

        for handler in self._logger.handlers:
            self.__original_formatters.append(handler.formatter)

            handler.terminator = ''
            formatter = log.Formatter( '%(message)s')
            handler.setFormatter(formatter)

        return self._logger

    def __exit__(self, exc_type, exc_value, exc_traceback):
        for handler, formatter in zip(self._logger.handlers, self.__original_formatters):
            handler.terminator = '\n'
            handler.setFormatter(formatter)

class TqdmLogger(StringIO):
    def __init__(self, logger):
        super().__init__()

        self._logger = logger

    def write(self, buffer):
        with TqdmLogFormatter(self._logger) as logger:
            logger.info(buffer)

    def flush(self):
        pass