import datetime
import json
import os
import sys
import zipfile
from datetime import datetime
from urllib.parse import unquote

from rich import print as tree_print
from rich.console import Console
from rich.progress import Progress
from rich.prompt import Prompt, IntPrompt
from rich.status import Status
from rich.tree import Tree

from mod_types import default_mod_types

_master: json = None
_mod_types: json = None
_db: json = None
_db2: json = None

_skipped_key = ('sections', 'cmlist')
_replaced_key = ('title', 'name')

_color_ignore_keys = ('cmid', 'plugin', 'modname', 'module')


def root_path(name: str = None) -> str:
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "program_data")
    # base_path = "C:\\Users\\SamLo\\Downloads\\tmp"
    if name == "master":
        return os.path.join(base_path, "master.json")
    if name == 'mod_types':
        return os.path.join(base_path, "mod_types.json")
    if name == 'dbinfo':
        return os.path.join(base_path, "dbinfo.json")
    if name == 'dbinfo2':
        return os.path.join(base_path, "dbinfo_ytd.json")
    if name == 'usrdir':
        return os.path.join(base_path, "userdir")
    if name == "db":
        # return os.path.join(base_path, "debug2")
        return get_master()["db_path"]
    return base_path


def print(msg: any, color: str = None):
    if color:
        _process.console.print(f"[{color}]{msg}[/{color}]")
    else:
        _process.console.print(msg)


def check_path(path: str, folder: bool = True, create: bool = True) -> bool:
    if os.path.exists(path):
        return True
    if not create:
        return False
    if folder:
        os.makedirs(path)
        print(f"{cr('Directory created', 'green')}: {cr(path, 'dark_green')}")
        return True
    if not check_path(os.path.dirname(path), create=False):
        os.makedirs(os.path.dirname(path))
        print(f"{cr('Directory created', 'green')}: {cr(os.path.dirname(path), 'dark_green')}")
    return False


def get_master() -> json:
    global _master
    if not _master:
        with open(f"{root_path('master')}", "r") as f:
            _master = json.load(f)
    return _master


def get_mod_types() -> json:
    global _mod_types

    if _mod_types:
        return _mod_types

    if not check_path(root_path('mod_types'), folder=False, create=False):
        default_types = default_mod_types()
        write(root_path('mod_types'), default_types, replace=True)
        _mod_types = default_types
        return default_types

    with open(f"{root_path('mod_types')}", "r") as f:
        _mod_types = json.load(f)
    return _mod_types


def check_mod_type(modname: str, module: str, plugin: str) -> str | None:
    for key, value in get_mod_types().items():
        if value["modname"] == modname and value["module"] == module and value["plugin"] == plugin:
            return key


def get_db(opt: str = None) -> json:
    if opt == 'dbinfo2':
        path = root_path('dbinfo2')
    else:
        path = root_path('dbinfo')

    if not check_path(path, folder=False, create=False):
        return {}

    if opt == 'dbinfo2':
        global _db2
        if not _db2:
            with open(f"{path}", "r") as f:
                _db2 = json.load(f)
        return _db2

    global _db
    if not _db:
        with open(f"{path}", "r") as f:
            _db = json.load(f)
    return _db


def url_decode(url: str) -> str:
    return unquote(url)


def form_date(date: str, format: str) -> datetime:
    return datetime.strptime(date, format)


def cr(msg: str, color: str = None) -> str:
    if color:
        return f"[{color}]{msg}[/{color}]"
    return msg


def print_tree(data: dict):
    if not data:
        print("No update in Moodle", "bright_yellow")
        return

    # Recursively print tree
    def print_tree_recursive(data: dict, tree: Tree):
        for key, value in data.items():
            if isinstance(value, dict):
                subtree = tree.add(key)
                print_tree_recursive(value, subtree)
            else:
                tree.add(f'{key}: {value}')

    tree = Tree("Root")
    print_tree_recursive(data, tree)
    tree_print(tree)


def get_skipped_keys() -> tuple:
    return _skipped_key


def get_replaced_keys() -> tuple:
    return _replaced_key


def get_color_ignore_keys() -> tuple:
    return _color_ignore_keys


def latest_filename(path: str) -> str:
    i = 1
    orig, file = os.path.split(path)
    file, extension = file.split(".")
    while os.path.exists(path):
        i += 1
        path = f"{orig}\\{file}_{i}.{extension}"
    return path


def download_file(path: str, content: bytes):
    with open(path, "wb") as f:
        f.write(content)


def extract_zip(path: str):
    with zipfile.ZipFile(path, 'r') as zip_ref:
        zip_ref.extractall(os.path.splitext(path)[0])
    os.remove(path)


def write(path: str, data: dict, replace: bool = False):
    if not replace:
        path = latest_filename(path)
    with open(path, "w") as f:
        json.dump(data, f, indent=4)
    print(f"{cr('File updated', "green")}: {cr(path, "cyan")}")


def init_rich():
    global _process
    _process = Rich()


def sym(name: str):
    if name == "tick":
        return ":heavy_check_mark:"
    return "|no symbol|"

def start_process():
    for task in _process.process.tasks:
        if not task.finished:
            task.visible = True
    if not _process.process.live.is_started:
        _process.process.start()


def pause_process():
    for task in _process.process.tasks:
        task.visible = False
    if _process.process.live.is_started:
        _process.process.stop()


def add_task(name: str, description: str, total: int):
    if name in _process.tasks:
        _process.console.print(f"Replacing task: {name}", "red")
        _process.process.tasks[_process.tasks[name]].visible = False
    _process.tasks[name] = _process.process.add_task(description, total=total)


def update_task(name: str, advance: int):
    _process.process.update(_process.tasks[name], advance=advance)
    if _process.process.tasks[_process.tasks[name]].finished:
        _process.process.tasks[_process.tasks[name]].visible = False
        msg = _process.process.tasks[_process.tasks[name]].description
        _process.console.print(f"{msg} {sym('tick')}")


def start_spinner():
    if _process.process.live.is_started:
        pause_process()
    if not _process.status._live.is_started:
        _process.status.start()


def stop_spinner():
    if _process.status._live.is_started:
        _process.status.stop()
        msg = _process.status.status
        print(f"{msg} {sym('tick')}")
    if not _process.process.live.is_started:
        start_process()


def spinner(text: str):
    _process.status.update(text)
    start_spinner()


def prompt(msg: str, tpe: str = None, **kwargs) -> str | int:
    ref = 0
    if _process.process.live.is_started:
        pause_process()
        ref = 1
    elif _process.status._live.is_started:
        stop_spinner()
        ref = 2
    if tpe == "int":
        ans = _process.intprompt.ask(msg, **kwargs)
    else:
        ans = _process.prompt.ask(msg, **kwargs)
    if ref == 1:
        start_process()
    elif ref == 2:
        start_spinner()
    return ans


class Rich:
    process: Progress
    console: Console
    prompt: Prompt
    intprompt: IntPrompt
    status: Status
    tasks: dict
    ongoing: list

    def __init__(self):
        self.console = Console()
        self.status = Status("", console=self.console)
        self.process = Progress(console=self.console)
        self.process.start()
        self.prompt = Prompt(console=self.console)
        self.intprompt = IntPrompt(console=self.console)
        self.tasks = {}
        self.ongoing = []


_process: Rich

if __name__ == "__main__":
    init_rich()

    # from markitdown import MarkItDown
    #
    # md = MarkItDown()
    # result = md.convert(f'{root_path()}\\view.php')
    # print(result.text_content)
