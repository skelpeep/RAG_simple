# atguigu/tool/logger.py

import logging
import colorlog

logger = logging.getLogger()
logger.setLevel(logging.INFO)

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bold_red',
    }
))

# logger.handlers.clear()
logger.addHandler(handler)


if __name__ == '__main__':
    logger.info("Hello from logger!")
    logger.error("Hello from logger!")
    logger.debug("Hello from logger!")
    logger.warning("Hello from logger!")
    logger.critical("Hello from logger!")