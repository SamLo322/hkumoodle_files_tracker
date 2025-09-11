import base64
from datetime import datetime
from tkinter.filedialog import askdirectory
import os
import re

import utils
from logger import logger
from moodle import get_course_options
from utils import config, cr


def intro():
    intro_time = datetime.now()
    if not utils.file_exists(utils.root_path('master')):
        logger.print("Welcome to HKU Moodle Scraper!", "bright_yellow")
        master = {
            "last_update": intro_time.strftime("%Y-%m-%d %H:%M:%S"),
            "storage": obtain_storage_path(),
            "login": obtain_login()
        }
        config.master = master
        master['courses'] = obtain_courses()
        utils.write(utils.root_path('master'), master, True)
        logger.print(f"{cr('File created', 'green')}: {cr(utils.root_path('master'), 'cyan')}")
    diff = intro_time - utils.form_date(config.get_master()["last_update"], "%Y-%m-%d %H:%M:%S")
    logger.print(f"Last updated: {config.get_master()['last_update']} ({diff.total_seconds() / 3600:.2f} hours ago)")
    return


def obtain_login() -> dict:
    return {
        "email": logger.prompt("Email address UID", default="without @connect.hku.hk") + "@connect.hku.hk",
        "password": base64.b64encode(logger.prompt("Password (Hidden)", password=True).encode('utf-8')).decode()
    }


def obtain_storage_path() -> str:
    logger.print("Please select a folder to store your files.", "bright_green")
    path = askdirectory(title="Select folder to store files")
    if not path:
        logger.print("No folder selected. Using default storage path.", "red")
        path = os.path.expanduser("~/Documents")  # Default to Documents folder
    logger.print(f'Selected path: {cr(path, "green")}', "bright_green")
    return path


def obtain_courses() -> list[str]:
    logger.print(f"Current courses:\n{'\n'.join(config.get_master().get('courses', [])) or cr('None', 'red')}",
                 "bright_green")
    courses = []
    opts = ["E", "PICK"]
    while res := logger.prompt("Course code (e.g. math1011): ('pick' to select courses, 'e' to finish)").upper():
        if res == opts[0]:
            logger.print(f"Selected courses:\n{'\n'.join(courses)}", "bright_green") if courses else logger.print(
                "Courses cleared", "red")
            break
        elif res == opts[1]:
            selected = logger.select_multiple(get_course_options() + ["Cancel"])
            if "Cancel" not in selected:
                courses = selected
        else:
            if re.match(r"^[A-Z]{4,}\d{4,}$", res):
                courses.append(res)
            else:
                logger.print("Invalid course code", "red")
    return courses


def amend_info():
    master = config.get_master()
    master_orig = master.copy()
    # Give warning and retry if not in 'choices'
    while opt := logger.prompt("What would you like to amend?", choices=["login", "courses", "path", "exit"]):
        if opt == 'exit':
            break
        if opt == 'login':
            master['login'] = obtain_login()
            config.master = master
        elif opt == 'courses':
            master['courses'] = obtain_courses()
        elif opt == 'path':
            master['storage'] = obtain_storage_path()
    if master != master_orig:
        utils.write(utils.root_path('master'), master, True)
        logger.print(f"{cr('File updated', 'green')}: {cr(utils.root_path('master'), 'cyan')}")
