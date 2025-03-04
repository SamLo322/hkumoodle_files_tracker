from playwright.sync_api import sync_playwright, BrowserContext

import utils
from utils import cr


def create_browser(playwright: sync_playwright) -> BrowserContext:
    utils.spinner(cr("Starting app", "green"))

    # Launch a browser
    context = playwright.chromium.launch_persistent_context(
        utils.root_path("usrdir"),
        # headless=True,
        channel="chrome",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0",
        args=["--headless=new"]
    )
    utils.stop_spinner()
    return context
