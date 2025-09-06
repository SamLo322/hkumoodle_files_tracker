import copy

from beaupy import select, select_multiple
from rich.console import Console
from rich.progress import Progress
from rich.prompt import Prompt, IntPrompt
from rich.status import Status
from rich import print as tree_print
from rich.tree import Tree
from utils import sym, cr, config


class Rich:
    process: Progress
    console: Console
    rprompt: Prompt
    intprompt: IntPrompt
    status: Status
    tasks: dict
    ongoing: list

    def __init__(self):
        self.console = Console()
        self.status = Status("", console=self.console)
        self.process = Progress(console=self.console)
        self.process.start()
        self.rprompt = Prompt(console=self.console)
        self.intprompt = IntPrompt(console=self.console)
        self.tasks = {}
        self.ongoing = []

    def print(self, msg: any, color: str = None):
        if color:
            self.console.print(f"[{color}]{msg}[/{color}]")
        else:
            self.console.print(msg)

    def start_spinner(self):
        if self.process.live.is_started:
            self.pause_process()
        if not self.status._live.is_started:
            self.status.start()

    def stop_spinner(self):
        if self.status._live.is_started:
            self.status.stop()
            msg = self.status.status
            self.print(f"{msg} {sym('tick')}")
        if not self.process.live.is_started:
            self.start_process()

    def spinner(self, text: str):
        self.status.update(text)
        self.start_spinner()

    def start_process(self):
        for task in self.process.tasks:
            if not task.finished:
                task.visible = True
        if not self.process.live.is_started:
            self.process.start()

    def pause_process(self):
        for task in self.process.tasks:
            task.visible = False
        if self.process.live.is_started:
            self.process.stop()

    def add_task(self, name: str, description: str, total: int):
        if total < 1:
            return
        if name in self.tasks:
            self.console.print(f"Replacing task: {name}", "red")
            self.process.tasks[self.tasks[name]].visible = False
        self.tasks[name] = self.process.add_task(description, total=total)

    def update_task(self, name: str, advance: int):
        self.process.update(self.tasks[name], advance=advance)
        if self.process.tasks[self.tasks[name]].finished:
            self.process.tasks[self.tasks[name]].visible = False
            msg = self.process.tasks[self.tasks[name]].description
            self.console.print(f"{msg} {sym('tick')}")

    def prompt(self, msg: str, tpe: str = None, **kwargs) -> str | int:
        ref = 0
        if self.process.live.is_started:
            self.pause_process()
            ref = 1
        elif self.status._live.is_started:
            self.stop_spinner()
            ref = 2
        if tpe == "int":
            ans = self.intprompt.ask(msg, **kwargs)
        else:
            ans = self.rprompt.ask(msg, **kwargs)
        if ref == 1:
            self.start_process()
        elif ref == 2:
            self.start_spinner()
        return ans

    def select(self, opts: list[str], **kwargs) -> str:
        self.process.stop()
        opt = select(opts, page_size=10, **kwargs)
        self.process.start()
        return opt

    def select_multiple(self, opts: list[str], **kwargs) -> list[int]:
        self.process.stop()
        user_opts = select_multiple(opts, page_size=10, **kwargs)
        self.process.start()
        return user_opts

    def print_tree(self, data: dict) -> bool:
        if not data:
            self.print("No changes detected", "yellow")
            return False

        # Recursively print tree
        def print_tree_recursive(data: dict, tree: Tree):
            for key, value in data.items():
                if isinstance(value, dict):
                    subtree = tree.add(key)
                    print_tree_recursive(value, subtree)
                else:
                    tree.add(f'{key}: {value}')

        tree = Tree("Moodle")
        print_tree_recursive(data, tree)
        tree_print(tree)
        return True


    def db_diff(self, lib: dict, orig: dict) -> bool:
        lib = copy.deepcopy(lib)
        orig = copy.deepcopy(orig)
        if orig == {}:
            self.print("No previous version", "yellow")
            return True # First run requires saving
        logs = {}

        def recursive_color(dt, color: str = None):
            if isinstance(dt, str):
                return cr(dt, color)
            if not isinstance(dt, dict):
                return dt
            for key in dt.copy().keys():
                if key in config.get_color_ignore_keys():
                    dt.pop(key)
                    continue
                dt[cr(key, color)] = recursive_color(dt.pop(key), color)
            return dt

        def write_log(path: list, key: str, content: dict | str, color: str):
            writer = logs
            for i in path:
                if i not in writer:
                    writer[i] = {}
                writer = writer[i]
            # print(f'Recursive color - {cr(key, color)}: {content[key]}')
            writer[cr(key, color)] = recursive_color(content[key], color)

        def compare(new: dict, orig: dict, path: list = None):
            path = path or []

            lib_set = set(new.keys())
            orig_set = set(orig.keys())

            for key in lib_set - orig_set:
                write_log(path, key, new, "medium_spring_green")

            for key in orig_set - lib_set:
                write_log(path, key, orig, "bright_magenta")

            for key in lib_set & orig_set:
                if new[key] == orig[key]:
                    continue
                if isinstance(new[key], dict) and isinstance(orig[key], dict):

                    if key in config.get_skipped_keys():
                        compare(new[key], orig[key], path)
                    else:
                        for i in config.get_replaced_keys():
                            if i in new[key] and i in orig[key] and new[key][i] == orig[key][i]:
                                new_name = new[key][i]
                                new[new_name] = new.pop(key)
                                orig[new_name] = orig.pop(key)
                                key = new_name
                                break
                        compare(new[key], orig[key], path + [key])
                else:
                    write_log(path, key, new, "medium_spring_green")
                    write_log(path, key, orig, "bright_magenta")

        compare(lib, orig)
        return self.print_tree(logs)

logger = Rich()

if __name__ == '__main__':
    logger.prompt()