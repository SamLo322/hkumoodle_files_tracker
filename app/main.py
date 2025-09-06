import json
from datetime import datetime

import utils
from browser import playwright
from dbinfos import logs, write_log
from logger import logger
from moodle import moodle_main
from startup import intro, amend_info
from utils import config, cr


def settings(lib: dict) -> None:
    opts = ['u', 'r']
    opt = logger.prompt("Enter to exit. ('u' to enter settings, 'r' to compare change history)").lower()
    while opt in opts:
        if opt == opts[0]:
            amend_info()
        elif opt == opts[1]:
            diff_db = logs.get_compare_logs()
            logger.db_diff(lib, diff_db)
        opt = logger.prompt("Enter to exit. ('u' to enter settings, 'r' to compare change history)").lower()


def update_master_time(update_time: datetime) -> None:
    master = config.get_master()
    master_path = utils.root_path('master')
    master['last_update'] = update_time.strftime("%Y-%m-%d %H:%M:%S")
    utils.write(master_path, master, True)
    logger.print(f"{cr('File updated', 'green')}: {cr(master_path, 'cyan')}")


def main():
    intro()
    lib = moodle_main()
    # lib = logs.get_prev_log() # For testing purpose

    utils.folder_exists(utils.root_path('logs'))
    if logger.db_diff(lib, logs.get_prev_log()):
        update_time = datetime.now()
        write_log(lib, update_time)
        update_master_time(update_time)

    settings(lib)

    # Close
    playwright.close()


if __name__ == '__main__':
    main()
    # import os
    # res = json.load(open(os.path.join(utils.root_path(), 'courses_info.json')))[0]
