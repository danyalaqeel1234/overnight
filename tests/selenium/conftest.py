"""
Selenium Grid Pytest Configuration for NaSCon '26 Day 2.
Supports dynamic CLI flags and environment variables for Selenium Hub and Base URL.
Skips cleanly if Selenium Grid is not reachable.
"""
from __future__ import annotations

import os
import urllib.request
import json
import pytest
from selenium import webdriver


def pytest_addoption(parser):
    parser.addoption(
        "--grid-url",
        action="store",
        default=os.environ.get("HUB_URL", os.environ.get("SELENIUM_HUB_URL", "http://localhost:4444")),
        help="Selenium Grid Hub URL (default: http://localhost:4444)",
    )
    parser.addoption(
        "--base-url",
        action="store",
        default=os.environ.get("APP_BASE_URL", os.environ.get("BASE_URL", "http://localhost:8080")),
        help="Target Application Base URL (default: http://localhost:8080)",
    )
    parser.addoption(
        "--browser",
        action="store",
        default="chrome",
        help="Target browser: chrome | firefox",
    )


@pytest.fixture(scope="session")
def grid_url(request):
    raw_url = request.config.getoption("--grid-url")
    # Normalize URL - grid 4 supports both root and /wd/hub
    return raw_url.rstrip("/")


@pytest.fixture(scope="session")
def base_url(request):
    return request.config.getoption("--base-url").rstrip("/")


@pytest.fixture(scope="session")
def web_url(base_url):
    """Base URL as seen from INSIDE the grid browser nodes (compose service name)."""
    return os.environ.get("WEB_BASE_URL", "http://backend:8080").rstrip("/")


@pytest.fixture(scope="session")
def grid_available(grid_url):
    """Check if Selenium Grid is running and ready."""
    status_url = f"{grid_url}/status"
    try:
        with urllib.request.urlopen(status_url, timeout=2) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                if data.get("value", {}).get("ready", False):
                    return True
    except Exception:
        pass
    return False


@pytest.fixture(scope="function")
def driver(request, grid_url, grid_available):
    if not grid_available:
        pytest.skip(f"Selenium Grid at {grid_url} is not ready or not running.")

    browser_name = request.config.getoption("--browser").lower()
    hub_endpoint = f"{grid_url}/wd/hub"

    if browser_name == "firefox":
        options = webdriver.FirefoxOptions()
        options.add_argument("-headless")
    else:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1280,900")

    try:
        d = webdriver.Remote(command_executor=hub_endpoint, options=options)
    except Exception:
        # Fallback to direct grid_url without /wd/hub (Selenium 4 standard)
        d = webdriver.Remote(command_executor=grid_url, options=options)

    d.implicitly_wait(5)
    yield d
    d.quit()
