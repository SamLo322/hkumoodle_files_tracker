from playwright.sync_api import sync_playwright, BrowserContext

from utils import root_path


def create_browser(playwright: sync_playwright) -> BrowserContext:
    # Launch a browser
    # context = playwright.chromium.launch(
    #     # headless=False,
    #     channel="chrome",
    #     # user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0",
    #     args=["--headless=new"]
    # )
    context = playwright.chromium.launch_persistent_context(
        "",
        # root_path("userdir"),
        # headless=False,
        channel="chrome",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0",
        args=["--headless=new"]
    )
    return context