import base64
import json
import os
import re
from typing import Optional

from playwright.sync_api import BrowserContext, sync_playwright

import utils
from browser import create_browser
from utils import cr, config

from logger import logger


def moodle_main() -> dict:
    with sync_playwright() as p:
        logger.spinner(cr("Starting app", "green"))
        context = create_browser(p)
        logger.stop_spinner()

        login(context)

        uni_lib = {}
        links, sesskey = identify_courses(context)

        logger.add_task("scrape_courses", cr(f'Obtaining {len(links)} courses information', 'green'), len(links))
        for i in links:
            uni_lib[i['name']] = scrape_courses(context, i, sesskey)
            logger.update_task("scrape_courses", 1)

        download(uni_lib, context)
        context.close()
    return uni_lib


def login(context: BrowserContext):
    login_info = config.get_master()['login']

    logger.spinner(cr("Logging in", "green"))

    page = context.new_page()
    page.goto("https://moodle.hku.hk/login/index.php")

    page.locator(".btn.login-identityprovider-btn.btn-success").click()
    page.get_by_placeholder("Email").fill(login_info['email'])

    with page.expect_response("https://login.microsoftonline.com/organizations/oauth2/v2.0/authorize*") as result:
        page.locator("#login_btn").click()
    res = result.value

    if res.status != 302:
        page.locator("#passwordInput").fill(base64.b64decode(login_info['password']).decode())
        page.locator("#submitButton").click()
        page.locator("#idSIButton9").click()
        page.locator("#idSIButton9").click()
        page.wait_for_event("load")

    logger.stop_spinner()
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
        action_type = config.check_mod_type(i.get('modname'), i.get('module'), i.get('plugin'))
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
            logger.print(
                f"{cr('Unidentified module', 'red')} ({cr(course['name'].split(' ')[0], 'turquoise2')}): {i['id']} {i.get('name')}")
    return structure


def identify_courses(context: BrowserContext) -> tuple[list[dict], str]:
    logger.spinner(cr("Identifying moodle pages", "green"))
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
        for j in config.get_master()['courses']:
            if i['fullname'].startswith(j):
                links.append({
                    'name': i['fullname'],
                    'id': i['id'],
                    'url': i['viewurl']
                })
                logger.print(f"{cr('Identified moodle page', 'green')}: {cr(i['fullname'], 'turquoise2')}")
                break
    logger.stop_spinner()
    return links, sesskey


def download(lib: dict, context: BrowserContext):
    top_level = list(lib.keys())

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

    def download_page_pdf(url: str, path: str) -> None:
        page = context.new_page()
        page.goto(url + "&redirect=1")
        page.emulate_media(media="screen")
        page.pdf(path=path)
        page.close()

    def download_recursive(data: dict, path: Optional[list] = None):
        path = path or []

        if "type" in data and data['type'] in ["file", "folder", "assignment", ]:
            if data['type'] == 'file':
                links = get_redirect_link(data['url'], data['cmid'])
                # HTML type file
                if links is None:
                    partial_path = os.path.join(*path[:-1], f'[HTML] {data["name"]}.pdf')
                    full_path = os.path.join(utils.root_path("storage"), partial_path)
                    if not utils.file_exists(full_path):
                        logger.print(f'{cr("Downloading", "yellow4")} {cr(partial_path, "white")}')
                        download_page_pdf(data['url'], full_path)
                    return
            else:
                links = get_page_links(data['url'])

                # No links found in page
                if links is None:
                    return

            for link in links:
                filename = utils.url_decode(link.split("/")[-1].split("?")[0])
                partial_path = os.path.join(*path[:-1], filename)
                full_path = os.path.join(utils.root_path("storage"), partial_path)

                if os.path.splitext(filename)[1] == ".zip":
                    exist = utils.file_exists(os.path.splitext(full_path)[0])
                else:
                    exist = utils.file_exists(full_path)


                if exist:
                    # logger.print(f'{cr("File exists", "yellow")}: {cr(partial_path, "cyan")}')
                    pass
                else:
                    utils.folder_exists(os.path.dirname(full_path)) # Create parent folder if not exist (recursive)
                    logger.print(f'{cr("Downloading", "yellow4")} {cr(partial_path, "white")}')
                    utils.download_file(full_path, context.request.get(link).body())

                    if os.path.splitext(filename)[1] == ".zip":
                        logger.spinner(f"{cr('Extracting', 'yellow4')} {cr(partial_path, 'white')}")
                        utils.extract_zip(full_path)
                        logger.stop_spinner()

        else:
            for key, value in data.items():
                if isinstance(value, dict):
                    # logger.print(f'New path: {path + rename(value, key)}')
                    download_recursive(value, path + rename(value, key))

                if key in top_level:
                    logger.print(f'{cr("Completed", "bright_green")} {cr(key, "turquoise2")} {utils.sym("tick")}')
                    logger.update_task("filesearch", 1)

    logger.add_task("filesearch", cr(f'Searching for files in {len(lib)} pages', 'green'), len(lib))
    download_recursive(lib)
