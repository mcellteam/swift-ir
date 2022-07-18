import logging
import time
from tqdm import tqdm
import io
import config as cfg


__all__ = ['TqdmToLogger']

class TqdmToLogger(io.StringIO):
    """
        Output stream for TQDM which will output to logger module instead of
        the StdOut.
    """
    logger = None
    level = None
    buf = ''
    def __init__(self,logger,level=None):
        super(TqdmToLogger, self).__init__()
        # self.logger = logger
        self.logger = logging.getLogger('package.ui.heads_up_display')
        self.level = level or logging.INFO
    def write(self,buf):
        self.buf = buf.strip('\r\n\t ')
    def flush(self):
        # self.logger.log(self.level, self.buf)
        self.logger.log(self.level, self.buf)