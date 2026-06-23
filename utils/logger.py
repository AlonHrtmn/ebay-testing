import logging
import os

# Tracker to overwrite execution.log on the first call, and append on subsequent calls
_first_init = True

def setup_logger(name="ebay_test"):
    global _first_init
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
        
        # Open in write mode for the first logger to clear the file, then append
        mode = "w" if _first_init else "a"
        _first_init = False
        
        fh = logging.FileHandler(log_file_path, mode=mode, encoding="utf-8")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
    return logger
