import httpx
from playwright.sync_api import sync_playwright


def fetch_page(url: str, needs_js: bool = False) -> str:
    """Fetch a page, using Playwright for JS-heavy sites."""
    if needs_js:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")
            content = page.content()
            browser.close()
            return content
    else:
        response = httpx.get(url, follow_redirects=True, timeout=30.0)
        response.raise_for_status()
        return response.text
