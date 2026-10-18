"""Selenium Grid tests for the Guest Web Player (NaSCon '26 Day 2).

Connects to a Selenium Hub on port 4444.  The app must be running and
reachable at BASE_URL (default http://localhost:8000).

Run with:
    pytest tests/selenium/test_guest_player.py \
        --base-url http://localhost:8000 \
        --hub-url http://localhost:4444/wd/hub

Or set env vars BASE_URL / HUB_URL before pytest.
"""
from __future__ import annotations

import os
import time
import threading
from typing import Generator

import pytest
import uvicorn
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
HUB_URL = os.environ.get("HUB_URL", "http://localhost:4444/wd/hub")
MATCH_ID = "match-sel-001"
SESSION_ID = "costream-sel-001"
TIMEOUT = 15  # seconds


# ---------------------------------------------------------------------------
# App server fixture – starts a real uvicorn server in-process
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def app_server():
    """Start the FastAPI app in a background thread for the test session.

    Skipped when BASE_URL points to a remote server (i.e. the caller already
    has the app running).
    """
    if BASE_URL != "http://localhost:8000":
        yield
        return

    from app.main import app  # noqa: PLC0415

    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="error")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait until the server is ready
    import socket

    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", 8000), timeout=1):
                break
        except OSError:
            time.sleep(0.2)

    yield

    server.should_exit = True
    thread.join(timeout=5)


# ---------------------------------------------------------------------------
# WebDriver fixture – remote grid on port 4444
# ---------------------------------------------------------------------------
@pytest.fixture
def driver() -> Generator[WebDriver, None, None]:
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:4444/status", timeout=1)
    except Exception:
        pytest.skip("Selenium Grid hub not reachable at port 4444")

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,900")

    d = webdriver.Remote(command_executor=HUB_URL, options=options)
    d.implicitly_wait(5)
    yield d
    d.quit()


def wait(driver: WebDriver, testid: str, timeout: int = TIMEOUT):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, f"[data-testid='{testid}']"))
    )


def visible(driver: WebDriver, testid: str, timeout: int = TIMEOUT):
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, f"[data-testid='{testid}']"))
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def live_url(match_id: str = MATCH_ID) -> str:
    return f"{BASE_URL}/web/matches/{match_id}/live"


def costream_url(session_id: str = SESSION_ID) -> str:
    return f"{BASE_URL}/web/costream/{session_id}"


# ===========================================================================
# 1. Page load & all 9 data-testid elements are present
# ===========================================================================
class TestPresence:
    TESTIDS = [
        "guest-video-player",
        "live-score-banner",
        "guest-cart-count",
        "pinned-merch-card",
        "add-to-guest-cart-btn",
        "chat-message-list",
        "chat-input-field",
        "chat-send-btn",
        "progressive-auth-modal",
    ]

    def test_all_testids_present_on_live(self, driver: WebDriver):
        driver.get(live_url())
        for tid in self.TESTIDS:
            el = wait(driver, tid)
            assert el is not None, f"Missing data-testid={tid}"

    def test_all_testids_present_on_costream(self, driver: WebDriver):
        driver.get(costream_url())
        for tid in self.TESTIDS:
            el = wait(driver, tid)
            assert el is not None, f"Missing data-testid={tid} on costream route"

    def test_page_title(self, driver: WebDriver):
        driver.get(live_url())
        assert "NaSCon" in driver.title


# ===========================================================================
# 2. Video player
# ===========================================================================
class TestVideoPlayer:
    def test_video_element_inside_player(self, driver: WebDriver):
        driver.get(live_url())
        container = wait(driver, "guest-video-player")
        # Either the container itself is a <video> or it contains one
        tag = container.tag_name
        if tag != "video":
            videos = container.find_elements(By.TAG_NAME, "video")
            assert len(videos) >= 1, "guest-video-player must contain a <video> element"

    def test_video_has_controls(self, driver: WebDriver):
        driver.get(live_url())
        container = wait(driver, "guest-video-player")
        tag = container.tag_name
        if tag == "video":
            video = container
        else:
            video = container.find_element(By.TAG_NAME, "video")
        assert video.get_attribute("controls") is not None

    def test_video_has_aria_label(self, driver: WebDriver):
        driver.get(live_url())
        container = wait(driver, "guest-video-player")
        # Either the container or the video has aria-label
        label = container.get_attribute("aria-label") or ""
        if not label:
            tag = container.tag_name
            if tag != "video":
                try:
                    video = container.find_element(By.TAG_NAME, "video")
                    label = video.get_attribute("aria-label") or ""
                except Exception:
                    pass
        assert label, "Video player must have aria-label for WCAG 2.1 AA"


# ===========================================================================
# 3. Live score banner
# ===========================================================================
class TestScoreBanner:
    def test_banner_visible(self, driver: WebDriver):
        driver.get(live_url())
        banner = visible(driver, "live-score-banner")
        assert banner.is_displayed()

    def test_banner_has_initial_text(self, driver: WebDriver):
        driver.get(live_url())
        banner = wait(driver, "live-score-banner")
        text = banner.text.strip()
        assert text, "live-score-banner must have non-empty initial text"

    def test_banner_aria_live(self, driver: WebDriver):
        driver.get(live_url())
        banner = wait(driver, "live-score-banner")
        assert banner.get_attribute("aria-live") in ("polite", "assertive"), (
            "live-score-banner must have aria-live for screen readers"
        )

    def test_banner_role_status(self, driver: WebDriver):
        driver.get(live_url())
        banner = wait(driver, "live-score-banner")
        role = banner.get_attribute("role") or ""
        assert role in ("status", "region", "alert"), (
            "live-score-banner should have an appropriate ARIA role"
        )


# ===========================================================================
# 4. Merch card & cart
# ===========================================================================
class TestMerchCart:
    def test_merch_card_visible(self, driver: WebDriver):
        driver.get(live_url())
        card = visible(driver, "pinned-merch-card")
        assert card.is_displayed()

    def test_add_to_cart_increments_count(self, driver: WebDriver):
        driver.get(live_url())
        count_el = wait(driver, "guest-cart-count")
        assert count_el.text.strip() == "0"

        btn = wait(driver, "add-to-guest-cart-btn")
        btn.click()

        WebDriverWait(driver, TIMEOUT).until(
            lambda d: d.find_element(
                By.CSS_SELECTOR, "[data-testid='guest-cart-count']"
            ).text.strip() == "1"
        )

    def test_add_to_cart_multiple_clicks(self, driver: WebDriver):
        driver.get(live_url())
        btn = wait(driver, "add-to-guest-cart-btn")
        for _ in range(3):
            btn.click()
            time.sleep(0.1)

        count_el = wait(driver, "guest-cart-count")
        WebDriverWait(driver, TIMEOUT).until(
            lambda d: int(
                d.find_element(
                    By.CSS_SELECTOR, "[data-testid='guest-cart-count']"
                ).text.strip()
            ) >= 3
        )

    def test_cart_button_touch_target(self, driver: WebDriver):
        driver.get(live_url())
        btn = wait(driver, "add-to-guest-cart-btn")
        assert btn.size["height"] >= 48, "Touch target height must be >= 48px"
        assert btn.size["width"] >= 48, "Touch target width must be >= 48px"

    def test_cart_button_keyboard_activatable(self, driver: WebDriver):
        driver.get(live_url())
        count_el = wait(driver, "guest-cart-count")
        before = count_el.text.strip()

        btn = wait(driver, "add-to-guest-cart-btn")
        btn.send_keys(Keys.RETURN)

        WebDriverWait(driver, TIMEOUT).until(
            lambda d: d.find_element(
                By.CSS_SELECTOR, "[data-testid='guest-cart-count']"
            ).text.strip() != before
        )

    def test_cart_button_aria_label(self, driver: WebDriver):
        driver.get(live_url())
        btn = wait(driver, "add-to-guest-cart-btn")
        label = btn.get_attribute("aria-label") or ""
        assert label, "add-to-guest-cart-btn must have aria-label"


# ===========================================================================
# 5. Chat
# ===========================================================================
class TestChat:
    def test_chat_input_focusable(self, driver: WebDriver):
        driver.get(live_url())
        inp = wait(driver, "chat-input-field")
        inp.click()
        assert driver.switch_to.active_element == inp

    def test_chat_send_button_touch_target(self, driver: WebDriver):
        driver.get(live_url())
        btn = wait(driver, "chat-send-btn")
        assert btn.size["height"] >= 48
        assert btn.size["width"] >= 48

    def test_chat_input_aria_label(self, driver: WebDriver):
        driver.get(live_url())
        inp = wait(driver, "chat-input-field")
        label = inp.get_attribute("aria-label") or ""
        assert label, "chat-input-field must have aria-label"

    def test_chat_send_aria_label(self, driver: WebDriver):
        driver.get(live_url())
        btn = wait(driver, "chat-send-btn")
        label = btn.get_attribute("aria-label") or ""
        assert label, "chat-send-btn must have aria-label"

    def test_chat_message_list_role_log(self, driver: WebDriver):
        driver.get(live_url())
        log = wait(driver, "chat-message-list")
        role = log.get_attribute("role") or ""
        assert role == "log", "chat-message-list must have role='log'"

    def test_chat_message_list_aria_live(self, driver: WebDriver):
        driver.get(live_url())
        log = wait(driver, "chat-message-list")
        assert log.get_attribute("aria-live") in ("polite", "assertive")

    def test_chat_send_via_enter_key(self, driver: WebDriver):
        """Pressing Enter in the input triggers send (via JS keydown handler)."""
        driver.get(live_url())
        inp = wait(driver, "chat-input-field")
        inp.send_keys("hello selenium")
        inp.send_keys(Keys.RETURN)
        # After enter the input is cleared (modal may appear for 403 guest – that's ok)
        WebDriverWait(driver, TIMEOUT).until(
            lambda d: d.find_element(
                By.CSS_SELECTOR, "[data-testid='chat-input-field']"
            ).get_attribute("value") == ""
        )


# ===========================================================================
# 6. Progressive auth modal
# ===========================================================================
class TestAuthModal:
    def test_modal_initially_hidden(self, driver: WebDriver):
        driver.get(live_url())
        modal = wait(driver, "progressive-auth-modal")
        # Must not be visible on load
        assert not modal.is_displayed(), "progressive-auth-modal must be hidden on load"

    def test_modal_has_dialog_role(self, driver: WebDriver):
        driver.get(live_url())
        modal = wait(driver, "progressive-auth-modal")
        assert modal.get_attribute("role") == "dialog"

    def test_modal_aria_modal_false_initially(self, driver: WebDriver):
        driver.get(live_url())
        modal = wait(driver, "progressive-auth-modal")
        # aria-modal should be false or absent when hidden
        val = modal.get_attribute("aria-modal") or "false"
        assert val in ("false", ""), (
            "progressive-auth-modal aria-modal should be false when hidden"
        )

    def test_modal_shows_on_403_chat(self, driver: WebDriver):
        """When /api/v1/chat returns 403 the modal should become visible."""
        driver.get(live_url())

        # Intercept fetch to return 403 via script injection
        driver.execute_script(
            """
            window._origFetch = window.fetch;
            window.fetch = function(url, opts) {
                if (url && url.toString().includes('/api/v1/chat')) {
                    return Promise.resolve(new Response('{"detail":"Forbidden"}', {
                        status: 403,
                        headers: {'Content-Type': 'application/json'}
                    }));
                }
                return window._origFetch(url, opts);
            };
            """
        )

        inp = wait(driver, "chat-input-field")
        inp.send_keys("trigger modal")
        btn = wait(driver, "chat-send-btn")
        btn.click()

        WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, "[data-testid='progressive-auth-modal']")
            )
        )

        modal = driver.find_element(By.CSS_SELECTOR, "[data-testid='progressive-auth-modal']")
        assert modal.is_displayed()
        assert modal.get_attribute("aria-modal") == "true"


# ===========================================================================
# 7. WCAG contrast & dark theme basics (visual regression via JS)
# ===========================================================================
class TestWCAG:
    def test_background_color(self, driver: WebDriver):
        driver.get(live_url())
        bg = driver.execute_script(
            "return window.getComputedStyle(document.body).backgroundColor"
        )
        # Expect #0b0f19 → rgb(11, 15, 25)
        assert "11" in bg or "0b0f19" in bg.lower(), (
            f"Body background should be dark (#0b0f19), got {bg}"
        )

    def test_body_color(self, driver: WebDriver):
        driver.get(live_url())
        color = driver.execute_script(
            "return window.getComputedStyle(document.body).color"
        )
        # #f8fafc → rgb(248, 250, 252)
        assert "248" in color or "f8fafc" in color.lower(), (
            f"Body text color should be #f8fafc, got {color}"
        )

    def test_all_buttons_focusable(self, driver: WebDriver):
        driver.get(live_url())
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            tab_index = btn.get_attribute("tabindex")
            # tabindex -1 means intentionally unfocusable; others are fine
            assert tab_index != "-1", (
                f"Button '{btn.text}' has tabindex=-1, breaking keyboard navigation"
            )

    def test_no_positive_tabindex(self, driver: WebDriver):
        """Positive tabindex values break natural tab order."""
        driver.get(live_url())
        els = driver.find_elements(By.CSS_SELECTOR, "[tabindex]")
        for el in els:
            ti = el.get_attribute("tabindex")
            try:
                assert int(ti) <= 0, (
                    f"Element {el.tag_name} has tabindex={ti}; positive values break tab order"
                )
            except ValueError:
                pass


# ===========================================================================
# 8. Routing – costream route renders the same player UI
# ===========================================================================
class TestCostream:
    def test_costream_route_loads(self, driver: WebDriver):
        driver.get(costream_url())
        wait(driver, "guest-video-player")
        wait(driver, "live-score-banner")

    def test_costream_chat_present(self, driver: WebDriver):
        driver.get(costream_url())
        wait(driver, "chat-input-field")
        wait(driver, "chat-send-btn")


# ===========================================================================
# 9. Mobile viewport (360 × 780)
# ===========================================================================
class TestMobileViewport:
    def test_touch_targets_on_mobile(self, driver: WebDriver):
        driver.set_window_size(360, 780)
        driver.get(live_url())

        for tid in ("add-to-guest-cart-btn", "chat-send-btn"):
            el = wait(driver, tid)
            h = el.size["height"]
            w = el.size["width"]
            assert h >= 48, f"{tid} height {h}px < 48px on mobile"
            assert w >= 48, f"{tid} width {w}px < 48px on mobile"

    def test_video_player_visible_on_mobile(self, driver: WebDriver):
        driver.set_window_size(360, 780)
        driver.get(live_url())
        player = visible(driver, "guest-video-player")
        assert player.is_displayed()
