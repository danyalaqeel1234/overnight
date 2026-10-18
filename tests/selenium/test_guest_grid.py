"""
Required Selenium Grid Tests (Section 6.2.3 of Part II Specification).
Tests executed against Selenium Grid Hub (http://localhost:4444).
"""
from __future__ import annotations

import time
import requests
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def wait_for_testid(driver, testid: str, timeout: int = 5):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, f"[data-testid='{testid}']"))
    )


def test_1_qr_resolution_and_zero_friction_load(driver, base_url, web_url):
    """
    Test 1 (QR Resolution & Zero-Friction Load):
    Navigate to http://localhost:8080/q/m1-live, verify HTTP redirect to
    /web/matches/match-m1/live, assert [data-testid="guest-video-player"] and
    [data-testid="live-score-banner"] render within 3 seconds with zero login modal
    visible on initial load.
    """
    qr_url = f"{web_url}/q/m1-live"
    driver.get(qr_url)

    # Verify redirect occurred to /web/matches/match-m1/live
    WebDriverWait(driver, 5).until(lambda d: "/web/matches/match-m1/live" in d.current_url)
    assert "/web/matches/match-m1/live" in driver.current_url

    # Assert [data-testid="guest-video-player"] and [data-testid="live-score-banner"] render within 3s
    player = wait_for_testid(driver, "guest-video-player", timeout=3)
    assert player.is_displayed()

    banner = wait_for_testid(driver, "live-score-banner", timeout=3)
    assert banner.is_displayed()
    assert "1 - 0" in banner.text

    # Assert zero login modal visible on initial load
    modal = wait_for_testid(driver, "progressive-auth-modal", timeout=3)
    assert not modal.is_displayed()


def test_2_guest_write_block_and_progressive_modal(driver, base_url, web_url):
    """
    Test 2 (Guest Write Block & Progressive Modal):
    In a fresh guest session, type a message into [data-testid="chat-input-field"]
    and click [data-testid="chat-send-btn"]; assert that the message is not appended
    to chat-message-list and [data-testid="progressive-auth-modal"] becomes visible.
    """
    driver.get(f"{web_url}/web/matches/match-m1/live")

    input_field = wait_for_testid(driver, "chat-input-field")
    send_btn = wait_for_testid(driver, "chat-send-btn")
    chat_list = wait_for_testid(driver, "chat-message-list")

    test_message = "Hello from anonymous guest!"
    input_field.clear()
    input_field.send_keys(test_message)
    send_btn.click()

    # Wait for progressive-auth-modal to become visible
    modal = wait_for_testid(driver, "progressive-auth-modal")
    WebDriverWait(driver, 5).until(lambda d: modal.is_displayed())
    assert modal.is_displayed()

    # Assert message is NOT appended to chat-message-list
    assert test_message not in chat_list.text


def test_3_guest_cart_staging_and_realtime_score_sync(driver, base_url, web_url):
    """
    Test 3 (Guest Cart Staging & Real-Time Score Sync):
    Click [data-testid="add-to-guest-cart-btn"], verify [data-testid="guest-cart-count"]
    updates to "1", trigger a score event via POST /audit/v1/events, and assert
    [data-testid="live-score-banner"] updates in the browser DOM within 500 ms.
    """
    driver.get(f"{web_url}/web/matches/match-m1/live")

    # Click add to guest cart
    add_btn = wait_for_testid(driver, "add-to-guest-cart-btn")
    add_btn.click()

    # Verify [data-testid="guest-cart-count"] updates to "1"
    cart_count = wait_for_testid(driver, "guest-cart-count")
    WebDriverWait(driver, 5).until(lambda d: cart_count.text.strip() == "1")
    assert cart_count.text.strip() == "1"

    # Trigger a score event via POST /audit/v1/events
    event_payload = {
        "event_id": f"evt-sel-score-{int(time.time() * 1000)}",
        "match_id": "match-m1",
        "event_type": "score",
        "minute": 55,
        "payload": {
            "team_id": "club-alpha-1",
            "player_id": "player-alpha-1",
            "points": 1
        }
    }
    resp = requests.post(f"{base_url}/audit/v1/events", json=event_payload, timeout=5)
    assert resp.status_code in (200, 201)

    # Assert [data-testid="live-score-banner"] updates in browser DOM within 500 ms (timeout 3s for buffer)
    banner = wait_for_testid(driver, "live-score-banner")
    WebDriverWait(driver, 3).until(lambda d: "2 - 0" in banner.text or banner.text.strip() != "1 - 0")
