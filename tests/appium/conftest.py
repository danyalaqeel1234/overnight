"""
Appium 2 Pytest Configuration for NaSCon '26 Day 2 Mobile Testing.
Tests against Appium 2 Server (default: http://localhost:4723) with uiautomator2.
Skips cleanly if Appium server or physical/emulator device is not connected.
"""
from __future__ import annotations

import os
import json
import urllib.request
import pytest
from appium import webdriver
from appium.options.android import UiAutomator2Options

APPIUM_SERVER_URL = os.environ.get("APPIUM_SERVER_URL", "http://localhost:4723")


@pytest.fixture(scope="session")
def appium_available():
    """Verify Appium server is reachable and reports ready: true."""
    try:
        req = urllib.request.Request(f"{APPIUM_SERVER_URL}/status")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                # Appium 2 returns {"value": {"ready": true, ...}}
                return data.get("value", {}).get("ready", False)
    except Exception:
        pass
    return False


@pytest.fixture(scope="function")
def android_driver(appium_available):
    if not appium_available:
        pytest.skip(f"Appium 2 server at {APPIUM_SERVER_URL} is not ready or no mobile device connected.")

    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.automation_name = "UiAutomator2"
    options.device_name = os.environ.get("ANDROID_DEVICE_NAME", "Android Device")
    options.app_package = "com.mutators.mobile"
    options.app_activity = ".MainActivity"
    options.no_reset = True
    options.new_command_timeout = 60

    try:
        driver = webdriver.Remote(command_executor=APPIUM_SERVER_URL, options=options)
    except Exception as e:
        pytest.skip(f"Could not connect to Android session: {e}")

    yield driver
    driver.quit()
