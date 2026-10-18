"""
Mobile Manifest & Deep Link Configuration Unit Tests.
Verifies Android intent-filter for scheme 'nascon' and screen testIDs in React Native.
"""
from __future__ import annotations

import json
from pathlib import Path


def test_android_intent_filter_manifest():
    app_json_path = Path("mobile/app.json")
    assert app_json_path.exists(), "mobile/app.json must exist"

    data = json.loads(app_json_path.read_text(encoding="utf-8"))
    expo_config = data.get("expo", {})

    # 1. Scheme must be 'nascon'
    assert expo_config.get("scheme") == "nascon", "expo.scheme must be 'nascon'"

    # 2. Android intent-filter must be browsable VIEW for scheme nascon
    android_config = expo_config.get("android", {})
    intent_filters = android_config.get("intentFilters", [])
    assert len(intent_filters) >= 1, "Must configure at least one intentFilter"

    filter_0 = intent_filters[0]
    assert filter_0.get("action") == "VIEW"
    categories = filter_0.get("category", [])
    assert "DEFAULT" in categories
    assert "BROWSABLE" in categories
    data_entry = filter_0.get("data", [])
    assert len(data_entry) >= 1
    assert data_entry[0].get("scheme") == "nascon"


def test_mobile_app_deeplink_routing():
    app_tsx_path = Path("mobile/App.tsx")
    assert app_tsx_path.exists(), "mobile/App.tsx must exist"

    code = app_tsx_path.read_text(encoding="utf-8")
    assert "Linking.getInitialURL()" in code or "Linking.addEventListener" in code
    assert "MatchDetailScreen" in code
    assert "CoStreamScreen" in code

    match_screen_path = Path("mobile/src/screens/MatchDetailScreen.tsx")
    assert match_screen_path.exists()
    assert 'testID="match-live-screen"' in match_screen_path.read_text(encoding="utf-8")

    costream_screen_path = Path("mobile/src/screens/CoStreamScreen.tsx")
    assert costream_screen_path.exists()
    assert 'testID="costream-screen"' in costream_screen_path.read_text(encoding="utf-8")
