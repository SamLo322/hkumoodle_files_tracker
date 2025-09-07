import base64
import re
import sys

from playwright.sync_api import sync_playwright, BrowserContext

from logger import logger
from utils import config, cr


class playwright_manager:
    playwright: sync_playwright
    context: BrowserContext
    sesskey: str
    login_status: bool

    def __init__(self):
        self.playwright = sync_playwright().start()
        self.context = self.playwright.chromium.launch_persistent_context(
            "",
            channel="chrome",
            user_agent={
                # Window - Edge
                "win32": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/140.0.3485.54",

                # Mac - Safari
                "darwin": "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_6_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
                # Safari
                # Mac - Edge
                # "darwin": "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_6_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/140.0.3485.54" #Edge
            }[sys.platform],
            args=["--headless=new"]
        )
        self.login_status = False
        self.sesskey = ""

    def login(self):
        if self.login_status:
            return
        login_info = config.get_master()['login']

        logger.spinner(cr("Logging in", "green"))

        page = self.context.new_page()
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
        self.login_status = True

    def get_sesskey(self):
        if self.sesskey:
            return self.sesskey
        res = self.context.request.get("https://moodle.hku.hk/my/courses.php")
        self.sesskey = re.search(r'"sesskey":".+?"', res.text()).group(0).split(":")[1].strip('"')
        return self.sesskey

    def get_context(self) -> BrowserContext:
        return self.context

    def close(self):
        self.context.close()
        self.playwright.stop()


playwright = playwright_manager()
