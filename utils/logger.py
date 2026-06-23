import logging
import os

def setup_logger(name="ebay_test"):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d]: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console Handler
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # File Handler (Writes to execution.log in the project root)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_file_path = os.path.join(project_root, "execution.log")
        fh = logging.FileHandler(log_file_path, mode="w", encoding="utf-8")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
    return logger
