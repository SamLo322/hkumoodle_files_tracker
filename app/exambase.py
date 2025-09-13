import os
import re
from datetime import datetime

from playwright.sync_api import Page, Response

import utils
from browser import playwright
from logger import logger
from utils import config, cr

to_yr = datetime.now().year
from_yr = to_yr - 20


def exam_base():
    playwright.login()
    full_course_list = config.get_master().get('courses', [])
    logger.add_task("exam_base", cr(f'Obtaining {len(full_course_list)} courses past papers from Exambase', 'green'),
                    len(full_course_list))
    page = playwright.get_context().new_page()
    for course in full_course_list:
        download_files(course, course_page(course[:8].upper(), page))
        logger.update_task("exam_base", 1)
    page.close()
    return


def filter_packets(res: Response) -> bool:
    match = r"https:\/\/exambase-lib-hku-hk.eproxy.lib.hku.hk\/exhibits\/show\/exam\/home\?the_key=.*"
    return re.match(match, res.url) and res.status == 200
    # logger.print("\n".join([f"https://exambase-lib-hku-hk.eproxy.lib.hku.hk/{i}" for i in files]), "cyan")


def course_page(cde: str, page: Page) -> list[tuple[str, str]]:
    with page.expect_response(filter_packets) as res:
        page.goto(
            f"https://exambase-lib-hku-hk.eproxy.lib.hku.hk/exhibits/show/exam/home?the_key={cde}&the_field=crs&fromYear={from_yr}&toYear={to_yr}&the_sem1=on&the_sem2=on&the_ptype1=on&the_ptype2=on")
    matches = re.findall(r'archive\/files\/\w+.pdf.*?\d{1,2}-\d{1,2}-\d{4}', res.value.text())
    return [(match.split("'")[0], match.split(" ")[-1]) for match in matches]  # relative url, date: d-m-yyyy


def download_files(course: str, matches: list[tuple[str, str]]) -> None:
    context = playwright.get_context()
    partial_path = os.path.join(course, "Past Paper (Exambase)")
    path = os.path.join(utils.root_path("storage"), partial_path)
    if matches:
        utils.folder_exists(path)  # create folder if not exist
    for url, date in matches:
        filename = f"{datetime.strftime(datetime.strptime(date, "%d-%m-%Y"), '%Y%m%d')}.pdf"
        full_path = os.path.join(path, filename)
        if utils.file_exists(full_path):
            continue
        url = f"https://exambase-lib-hku-hk.eproxy.lib.hku.hk/{url}"
        res = context.request.get(url)
        if res.status != 200:
            logger.error(f"Failed to download {course[:8].upper()} paper {date} from Exambase. URL: {url}")
            continue
        logger.print(f'{cr("Downloading", "yellow4")} {cr(os.path.join(partial_path, filename), "white")}')
        utils.download_file(full_path, res.body())
