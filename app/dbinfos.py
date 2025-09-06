import datetime
import json
import os
from beaupy import select

import utils
from utils import cr
from logger import logger


def write_log(data: dict, updatetime: datetime.datetime) -> None:
    filename = f'moodle_{updatetime.strftime("%Y%m%d_%H%M%S")}.json'
    path = os.path.join(utils.root_path('logs'), filename)
    utils.write(path, data, False)
    logger.print(f"{cr('Log saved', 'bright_green')}: {cr(filename, 'green')}")


class logs_manager:
    filenames: list[str]

    # start_time: datetime.datetime

    def __init__(self):
        self.filenames = sorted(os.listdir(utils.root_path('logs')), reverse=True)
        # self.start_time = datetime.datetime.now()

    def latest_log_path(self, n: int = 1) -> list[str]:
        return self.filenames[:n]

    def get_prev_log(self) -> dict:
        if self.filenames:
            return json.load(open(os.path.join(utils.root_path('logs'), self.filenames[0]), 'r'))
        return {}

    def get_compare_logs(self) -> dict:
        if not self.filenames:
            return {}
        logger.print('Select version to compare', 'bright_green')
        corr_filenames = [
            str(datetime.datetime.strptime('_'.join(os.path.splitext(i)[0].split('_')[1:3]), '%Y%m%d_%H%M%S')) for i in self.filenames
        ]
        opt = logger.select(corr_filenames, return_index=True)
        logger.print(f'Selected version: {corr_filenames[opt]}', 'green')
        return json.load(open(os.path.join(utils.root_path('logs'), self.filenames[opt]), 'r'))


logs = logs_manager()

if __name__ == '__main__':
    print(logs.get_compare_logs())
