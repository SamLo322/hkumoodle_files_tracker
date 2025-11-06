import json
import os
import plistlib
import re
import sys
import time
from typing import Optional

import utils
from browser import playwright
from logger import logger
from utils import cr, config


def get_course_options():
    playwright.login()
    res = moodle_mainpage()
    return [i['fullname'] for i in res.json()[0]['data']['courses']]


def create_course_link(uni_lib: dict):
    for course in uni_lib:
        path = os.path.join(utils.root_path("storage"), course)
        utils.folder_exists(path) # Create course folder if not exist

        if sys.platform == 'win32':
            link_path = os.path.join(path, f"{course}.url")
            if not utils.file_exists(link_path):
                utils.download_file(link_path, f"[InternetShortcut]\nURL={uni_lib[course]['url']}\n")
                logger.print(f'{cr("Created shortcut file", "green")} for {cr(course, "turquoise2")}')
        elif sys.platform == 'darwin':
            try:
                link_path = os.path.join(path, f"{course}.webloc")
                if not utils.file_exists(link_path):
                    with open(link_path, "w") as f:
                        plistlib.dump({'URL': uni_lib[course]['url']}, f)
                    logger.print(f'{cr("Created shortcut file", "green")} for {cr(course, "turquoise2")}')
            except Exception as e:
                logger.print(f"{cr('Failed to create .webloc file', 'red')}: {cr(e, 'yellow')}")

def moodle_main() -> dict:
    logger.spinner(cr("Starting app", "green"))
    logger.stop_spinner()

    playwright.login()

    uni_lib = {}
    links = identify_courses()

    logger.add_task("scrape_courses", cr(f'Obtaining {len(links)} courses information', 'green'), len(links))
    for i in links:
        uni_lib[i['name']] = scrape_courses(i)
        logger.update_task("scrape_courses", 1)

    create_course_link(uni_lib)
    download(uni_lib)
    return uni_lib


def scrape_courses(course: dict) -> dict:
    sesskey = playwright.get_sesskey()
    res = playwright.get_context().request.post(
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
            'title': i.get('title').replace("&amp;", "&"),
            # 'sectionurl': i.get('sectionurl'),
        }
        if i['cmlist']:
            structure['sections'][i['id']]['cmlist'] = {j: {} for j in i['cmlist']}

    for i in res['cm']:
        modname, module, plugin = i.get('modname'), i.get('module'), i.get('plugin')
        action_type = config.check_mod_type(modname, module, plugin)
        if not action_type:
            config.new_mod_type(modname, module, plugin)
            logger.print(
                f"{cr('Unidentified module', 'red')}-{module} ({cr(course['name'].split(' ')[0], 'turquoise2')}): {i['id']} {i.get('name')}")
            action_type = "not set"

        structure['sections'][i['sectionid']]['cmlist'][i['id']] = {
            'name': i.get('name').replace("&amp;", "&"),
            'cmid': i.get('id'),
            'modname': modname,
            'module': module,
            'plugin': plugin,
            'url': i.get('url'),
            'restriction': i.get('hascmrestrictions'),
            'type': action_type
        }
    return structure


def moodle_mainpage():
    sesskey = playwright.get_sesskey()
    return playwright.get_context().request.post(
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


def identify_courses() -> list[dict]:
    logger.spinner(cr("Identifying moodle pages", "green"))
    res = moodle_mainpage()
    links = []
    for i in res.json()[0]['data']['courses']:
        for j in config.get_master()['courses']:
            if i['fullname'].startswith(j):
                links.append({
                    'name': i['fullname'].split('[')[0].strip(),
                    'id': i['id'],
                    'url': i['viewurl']
                })
                logger.print(f"{cr('Identified moodle page', 'green')}: {cr(i['fullname'], 'turquoise2')}")
                break
    logger.stop_spinner()
    return links


def download(lib: dict):
    top_level = list(lib.keys())
    context = playwright.get_context()

    def rename(dt: dict, key: str) -> list[str] | list:
        if key in config.get_skipped_keys():
            return []
        for name in config.get_replaced_keys():
            if content := dt.get(name):
                key = content
                break
        return [" ".join(key.replace("/", "").replace("\\", "").split())]

    def get_redirect_link(url: str, cmid: str) -> list[str] | None:
        res = context.request.post(url, data={"id": cmid}, max_redirects=0)
        try:
            return [res.headers['location']]
        except KeyError:
            return None

    def get_page_links(url: str) -> list[str] | None:
        res = context.request.get(url)
        regex = re.findall(r'https?://[^"]*forcedownload=1(?=")', res.text())
        return regex

    def download_page_pdf(data: dict, path: list) -> None:
        filename, partial_path, full_path = construct_file_paths(path, f'[HTML] {data["name"]}.pdf')
        if not utils.file_exists(full_path):
            logger.print(f'{cr("Downloading", "yellow4")} {cr(partial_path, "white")}')
            page = context.new_page()
            page.goto(data['url'] + "&redirect=1")
            page.emulate_media(media="screen")
            page.pdf(path=full_path)
            page.close()
        return

    def construct_file_paths(path: list, filename: str) -> tuple[str, str, str]:
        filename = utils.validate_filename(filename)
        partial_path = os.path.join(*path[:-1], filename)
        full_path = os.path.join(utils.root_path("storage"), partial_path)
        return filename, partial_path, full_path

    def download_recursive(data: dict, path: Optional[list] = None):
        path = path or []

        if "type" in data and data['type'] in ["file", "folder", "assignment", ] and not data['restriction']:
            if data['type'] == 'file':
                links = get_redirect_link(data['url'], data['cmid'])

                # HTML type file
                if links is None:
                    download_page_pdf(data, path)
                    return

            elif data['url'] is None:
                link = f'https://moodle.hku.hk/mod/folder/download_folder.php?id={data["cmid"]}'
                filename = f'{data["name"]}.zip'
                filename, partial_path, full_path = construct_file_paths(path, filename)
                if not utils.file_exists(os.path.splitext(full_path)[0]):
                    utils.folder_exists(os.path.dirname(full_path))  # Create parent folder if not exist (recursive)
                    logger.print(f'{cr("Downloading", "yellow4")} {cr(partial_path, "white")}')
                    utils.download_file(full_path, context.request.get(link).body())
                    logger.spinner(f"{cr('Extracting', 'yellow4')} {cr(partial_path, 'white')}")
                    utils.extract_zip(full_path)
                    logger.stop_spinner()
                return

            else:
                links = get_page_links(data['url'])

                # No links found in page
                if links is None:
                    return

                if data['type'] == 'assignment':
                    path.append(data['name'])

            for link in links:
                filename = utils.url_decode(link.split("/")[-1].split("?")[0])
                filename, partial_path, full_path = construct_file_paths(path, filename)

                is_zip = os.path.splitext(filename)[1] == ".zip"

                if is_zip:
                    exist = utils.file_exists(os.path.splitext(full_path)[0])
                else:
                    exist = utils.file_exists(full_path)

                if not exist:
                    utils.folder_exists(os.path.dirname(full_path))  # Create parent folder if not exist (recursive)
                    logger.print(f'{cr("Downloading", "yellow4")} {cr(partial_path, "white")}')
                    utils.download_file(full_path, context.request.get(link).body())

                    if is_zip:
                        logger.spinner(f"{cr('Extracting', 'yellow4')} {cr(partial_path, 'white')}")
                        utils.extract_zip(full_path)
                        logger.stop_spinner()

        else:
            for key, value in data.items():
                if isinstance(value, dict):
                    download_recursive(value, path + rename(value, key))

                if key in top_level:
                    logger.print(f'{cr("Completed", "bright_green")} {cr(key, "turquoise2")} {utils.sym("tick")}')
                    logger.update_task("filesearch", 1)
                    time.sleep(0.2) # Allow time for the task bar to update

    logger.add_task("filesearch", cr(f'Searching for files in {len(lib)} pages', 'green'), len(lib))
    download_recursive(lib)
