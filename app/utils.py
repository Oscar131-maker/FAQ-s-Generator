import logging
import os
from datetime import datetime

# Setup logging
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file = os.path.join(log_dir, "app_debug.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("FAQGenerator")

def log_interaction(step, input_data, output_data, error=None):
    """
    Logs interactions for debugging.
    """
    log_entry = f"\n{'='*50}\nSTEP: {step}\nTIME: {datetime.now()}\n"
    log_entry += f"INPUT:\n{input_data}\n"
    if output_data:
        log_entry += f"OUTPUT:\n{output_data}\n"
    if error:
        log_entry += f"ERROR:\n{error}\n"
    log_entry += f"{'='*50}\n"
    
    logger.info(log_entry)
