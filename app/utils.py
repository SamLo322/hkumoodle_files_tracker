import datetime
import json
import os
import sys
import zipfile
from datetime import datetime
from typing import Optional
from urllib.parse import unquote

from templates import default_mod_types


def validate_filename(name: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    file, ext = os.path.splitext(name.strip())
    for char in invalid_chars:
        file = file.replace(char, '_')
    if len(file) == 0:
        file = 'untitled'
    return file + ext

# TODO: Refract path to class with getters (Only join once)
def root_path(name: str = None) -> str | None:
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "program_data")

    match name:
        case "master":
            return os.path.join(base_path, "master.json")
        case "storage":
            return config.get_master()["storage"]
        case "logs":
            return os.path.join(base_path, "storage_logs")
        case 'mod_types':
            return os.path.join(base_path, "mod_types.json")
        case _:
            return base_path


def init_master() -> Optional[json]:
    if file_exists(root_path("master")):
        return json.load(open(root_path("master"), "r"))
    return None


def init_modtype():
    if not file_exists(root_path("mod_types")):
        default_types = default_mod_types()
        write(root_path("mod_types"), default_types, replace=True)
        return default_types
    return json.load(open(root_path("mod_types"), "r"))


def init_db(opt: str = None):
    path = root_path(opt)
    if not file_exists(path):
        return {}
    return json.load(open(path, "r"))


def folder_exists(path: str, create: bool = True) -> bool:
    if os.path.exists(path):
        return True
    if not create:
        return False
    os.makedirs(path)
    return True


def file_exists(path: str) -> bool:
    return os.path.exists(path)


def url_decode(url: str) -> str:
    return unquote(url)


def form_date(date: str, format: str) -> datetime:
    return datetime.strptime(date, format)


def cr(msg: str, color: str = None) -> str:
    if color:
        return f"[{color}]{msg}[/{color}]"
    return msg


def latest_filename(path: str) -> str:
    i = 1
    orig, file = os.path.split(path)
    file, extension = os.path.splitext(file)
    while os.path.exists(path):
        i += 1
        path = os.path.join(orig, f"{file}_{i}{extension}")
    return path


def download_file(path: str, content: bytes | str):
    mode = "wb" if isinstance(content, bytes) else "w"
    with open(path, mode) as f:
        f.write(content)


def extract_zip(path: str):
    with zipfile.ZipFile(path, "r") as zip_ref:
        zip_ref.extractall(os.path.splitext(path)[0])
    os.remove(path)


def write(path: str, data: dict, replace: bool = False):
    if not replace:
        path = latest_filename(path)
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


def sym(name: str):
    if name == "tick":
        return ":heavy_check_mark:"
    return "|no symbol|"


class config_init:
    master: Optional[dict]
    mod_types: dict
    db: dict
    db_prev: dict
    skipped_key: tuple
    replaced_key: tuple
    color_ignore_keys: tuple

    def __init__(self):
        folder_exists(root_path())
        folder_exists(root_path("logs"))
        self.master = init_master()
        self.mod_types = init_modtype()
        self.skipped_key = ("sections", "cmlist")
        self.replaced_key = ("title", "name")
        self.color_ignore_keys = ("cmid", "plugin", "modname", "module")

    def check_mod_type(self, modname: str, module: str, plugin: str) -> str | None:
        for key, value in self.mod_types.items():
            if (
                value.get("modname") == modname
                and value.get("module") == module
                and value.get("plugin") == plugin
            ):
                return key
        return None

    def new_mod_type(self, modname: str, module: str, plugin: str):
        self.mod_types["not set"] = {
            "modname": modname,
            "module": module,
            "plugin": plugin
        }
        write(root_path("mod_types"), self.mod_types, True)

    def get_master(self) -> dict:
        if not self.master:
            self.master = init_master()
        return self.master | {}

    def get_skipped_keys(self) -> tuple:
        return self.skipped_key

    def get_replaced_keys(self) -> tuple:
        return self.replaced_key

    def get_color_ignore_keys(self) -> tuple:
        return self.color_ignore_keys


config = config_init()
