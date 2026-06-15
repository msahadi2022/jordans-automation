import logging
import os
import sys

import azure.functions as func

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main(mytimer: func.TimerRequest) -> None:
    """Azure Function entry point — triggers the Jordan automation pipeline."""
    if mytimer.past_due:
        logging.warning("Timer is past due — running now.")

    logging.info("Jordan automation triggered by timer.")

    from main import run
    run()
