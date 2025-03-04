import base64
import json
import os.path
import re
from datetime import datetime

from playwright.sync_api import BrowserContext, sync_playwright

import utils
from browser import create_browser
from utils import print, cr


def login(context: BrowserContext):
    login_info = utils.get_master()['login']

    utils.spinner(cr("Logging in", "green"))

    page = context.new_page()
    page.goto("https://moodle.hku.hk/login/index.php")

    page.locator(".btn.login-identityprovider-btn.btn-success").click()
    page.get_by_placeholder("Email").fill(login_info['email'])

    page.locator("#login_btn").click()
    page.wait_for_load_state("load")
    if page.url.startswith("https://login.microsoftonline.com/"):
        page.locator("#passwordInput").fill(base64.b64decode(login_info['password']).decode())
        page.locator("#submitButton").click()
        page.locator("#idSIButton9").click()
        page.locator("#idSIButton9").click()
        page.wait_for_event("load")

    utils.stop_spinner()
    page.close()


def scrape_courses(context: BrowserContext, course: dict, sesskey: str) -> dict:
    res = context.request.post(
        f"https://moodle.hku.hk/lib/ajax/service.php?sesskey={sesskey}&info=core_courseformat_get_state",
        data=[{
            "args": {
                "courseid": course['id']
            },
            "index": 0,
            "methodname": "core_courseformat_get_state"
        }])
    res = json.loads(res.json()[0]['data'])

    structure = {
        'name': course['name'],
        'url': course['url'],
        'id': res['course']['id'],
        'num_sections': str(res['course']['numsections']),
        'sections': {i: {} for i in res['course']['sectionlist']}
    }

    for i in res['section']:
        structure['sections'][i['id']] = {
            'title': i.get('title'),
            # 'sectionurl': i.get('sectionurl'),
        }
        if i['cmlist']:
            structure['sections'][i['id']]['cmlist'] = {j: {} for j in i['cmlist']}

    for i in res['cm']:
        action_type = utils.check_mod_type(i.get('modname'), i.get('module'), i.get('plugin'))
        structure['sections'][i['sectionid']]['cmlist'][i['id']] = {
            'name': i.get('name'),
            'cmid': i.get('id'),
            'modname': i.get('modname'),
            'module': i.get('module'),
            'plugin': i.get('plugin'),
            'url': i.get('url'),
            'type': action_type
        }
        if not action_type:
            print(f"{cr('Unidentified module', 'red')}: {i['id']} {i.get('name')}")
    return structure


def identify_courses(context: BrowserContext) -> tuple[list[dict], str]:
    utils.spinner(cr("Identifying moodle pages", "green"))
    res = context.request.get("https://moodle.hku.hk/my/courses.php")
    sesskey = re.search(r'"sesskey":".+?"', res.text()).group(0).split(":")[1].strip('"')

    res = context.request.post(
        f"https://moodle.hku.hk/lib/ajax/service.php?sesskey={sesskey}&info=core_course_get_enrolled_courses_by_timeline_classification",
        data=[{
            "index": 0,
            "methodname": "core_course_get_enrolled_courses_by_timeline_classification",
            "args": {
                "classification": "all",
                "customfieldname": "",
                "customfieldvalue": "",
                "limit": 0,
                "offset": 0,
                "requiredfields": ["id", "fullname", "shortname", "showcoursecategory", "showshortname", "visible",
                                   "enddate"]
            }
        }])
    links = []
    for i in res.json()[0]['data']['courses']:
        for j in utils.get_master()['courses']:
            if i['fullname'].startswith(j):
                links.append({
                    'name': i['fullname'],
                    'id': i['id'],
                    'url': i['viewurl']
                })
                print(f"{cr('Identified moodle page', "green")}: {cr(i['fullname'], "turquoise2")}")
                break
    utils.stop_spinner()
    return links, sesskey


def playwright_meth() -> dict:
    with sync_playwright() as p:
        context = create_browser(p)
        login(context)

        uni_lib = {}
        links, sesskey = identify_courses(context)

        utils.add_task("scrape_courses", cr(f'Obtaining {len(links)} courses information', 'green'), len(links))
        for i in links:
            uni_lib[i['name']] = scrape_courses(context, i, sesskey)
            utils.update_task("scrape_courses", 1)

        download(uni_lib, context)
        context.close()
    return uni_lib


def db_diff(lib: dict, orig: dict):
    logs = {}

    def recursive_color(dt, color: str = None):
        if isinstance(dt, str):
            return cr(dt, color)
        if not isinstance(dt, dict):
            return dt
        for key in dt.copy().keys():
            if key in utils.get_color_ignore_keys():
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

    def compare(lib, orig, path: list = None):
        path = path or []

        lib_set = set(lib.keys())
        orig_set = set(orig.keys())

        for key in lib_set - orig_set:
            write_log(path, key, lib, "medium_spring_green")

        for key in orig_set - lib_set:
            write_log(path, key, orig, "bright_magenta")

        for key in lib_set & orig_set:
            if lib[key] == orig[key]:
                continue
            if isinstance(lib[key], dict) and isinstance(orig[key], dict):

                if key in utils.get_skipped_keys():
                    compare(lib[key], orig[key], path)
                else:
                    for i in utils.get_replaced_keys():
                        if i in lib[key] and i in orig[key] and lib[key][i] == orig[key][i]:
                            new_name = lib[key][i]
                            lib[new_name] = lib.pop(key)
                            orig[new_name] = orig.pop(key)
                            key = new_name
                            break
                    compare(lib[key], orig[key], path + [key])
            else:
                write_log(path, key, lib, "medium_spring_green")
                write_log(path, key, orig, "bright_magenta")

    compare(lib, orig)
    utils.print_tree(logs)
    return


def download(lib: dict, context: BrowserContext):
    top_level = list(lib.keys())

    def rename(dt: dict, key: str) -> list[str] | list:
        if key in utils.get_skipped_keys():
            return []
        for name in utils.get_replaced_keys():
            if content := dt.get(name):
                key = content
                break
        return [" ".join(key.replace("/", "").replace("\\", "").split())]

    def download_file(url: str, cmid: str) -> list[str]:
        res = context.request.post(url, data={"id": cmid}, max_redirects=0)
        redirect_link = res.headers['location']
        return [redirect_link]

    def download_default(url: str) -> list[str] | None:
        res = context.request.get(url)
        regex = re.findall(r'https?://[^"]*forcedownload=1(?=")', res.text())
        if regex is None:
            return None
        return regex

    def download_recursive(data: dict, path: list = None):
        path = path or []

        if "type" in data and data['type'] in ["file", "folder", "assignment"]:
            if data['type'] == 'file':
                links = download_file(data['url'], data['cmid'])
            else:
                links = download_default(data['url'])
            if links is None:
                return
            for link in links:
                filename = utils.url_decode(link.split("/")[-1].split("?")[0])
                partial_path = os.path.join(*path[:-1], filename)
                full_path = os.path.join(utils.root_path("db"), *path[:-1], filename)

                if os.path.splitext(filename)[1] == ".zip":
                    exist = utils.check_path(os.path.splitext(full_path)[0], create=False)
                    utils.check_path(os.path.dirname(full_path))
                else:
                    exist = utils.check_path(full_path, False)

                if exist:
                    # print(f'{cr("File exists", "yellow")}: {cr(partial_path, "cyan")}')
                    pass
                else:
                    print(f'{cr("Downloading", "yellow4")} {cr(partial_path, "white")}')
                    utils.download_file(full_path, context.request.get(link).body())

                    if os.path.splitext(filename)[1] == ".zip":
                        utils.spinner(f"{cr('Extracting', 'yellow4')} {cr(partial_path, 'white')}")
                        utils.extract_zip(full_path)
                        utils.stop_spinner()

        else:
            for key, value in data.items():
                if isinstance(value, dict):
                    # print(f'New path: {path + rename(value, key)}')
                    download_recursive(value, path + rename(value, key))

                if key in top_level:
                    print(f'{cr('Completed', 'bright_green')} {cr(key, "turquoise2")} {utils.sym('tick')}')
                    utils.update_task("filesearch", 1)

    utils.add_task("filesearch", cr(f'Searching for files in {len(lib)} pages', 'green'), len(lib))
    download_recursive(lib)


def init():
    utils.init_rich()
    if not utils.check_path(utils.root_path('master'), False):
        print("Welcome to HKU Moodle Scraper!", "bright_yellow")
        master = {
            "last_update": "2025-01-01 00:00:00",
            "db_path": utils.prompt("Path to store files", default="drag folder to terminal"),
            "login": {
                "email": utils.prompt("Email address UID", default="without @connect.hku.hk") + "@connect.hku.hk",
                "password": base64.b64encode(utils.prompt("Password", password=True).encode('utf-8')).decode()
            },
            "courses": []
        }
        # if utils.prompt("Save password?", choices=["y", "n"]) == "n":
        #     master['login']['password'] = None
        for i in range(utils.prompt("Number of courses", tpe="int")):
            master['courses'].append(utils.prompt(f"Course code {i + 1}", default="e.g. MATH1011").upper())
        utils.write(utils.root_path('master'), master, True)
    diff = datetime.now() - utils.form_date(utils.get_master()["last_update"], "%Y-%m-%d %H:%M:%S")
    print(f"Last updated: {utils.get_master()['last_update']} ({diff.total_seconds() / 3600:.2f} hours ago)")
    utils.check_path(utils.root_path("db"))
    utils.check_path(utils.root_path("usrdir"))
    return


def amend_info():
    master = utils.get_master()
    while opt := utils.prompt("What would you like to amend?", choices=["login", "courses", "path", "exit"]):
        if opt == 'exit':
            break
        if opt == 'login':
            master['login']['email'] = utils.prompt("Email address UID",
                                                    default="without @connect.hku.hk") + "@connect.hku.hk"
            master['login']['password'] = base64.b64encode(
                utils.prompt("Password", password=True).encode('utf-8')).decode()
        elif opt == 'courses':
            utils.get_master()['courses'] = []
            for i in range(utils.prompt("Number of courses", tpe="int")):
                utils.get_master()['courses'].append(
                    utils.prompt(f"Course code {i + 1}", default="e.g. MATH1011").upper())
        elif opt == 'path':
            master['db_path'] = utils.prompt("Path to store files", default="drag folder to terminal")
    utils.write(utils.root_path('master'), master, True)


def main():
    init()

    # Latest run
    lib = playwright_meth()

    # debug
    # prev_lib = utils.get_db('dbinfo2')
    # lib = utils.get_db('dbinfo')

    # Move dbinfo to dbinfo2
    prev_lib = utils.get_db('dbinfo')
    if lib != prev_lib:
        utils.write(utils.root_path('dbinfo2'), prev_lib, True)
        utils.write(utils.root_path('dbinfo'), lib, True)

    db_diff(lib, prev_lib)

    # Update master
    master = utils.get_master()
    master['last_update'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    utils.write(utils.root_path('master'), master, True)

    if utils.prompt("Enter to exit. ('u' to make amendments)").lower() == "u":
        amend_info()


if __name__ == '__main__':
    main()
