from src.services.notifications import NotificationConfig, build_notification_text


def _make_config(**overrides):
    defaults = dict(
        waha_base_url="http://waha:3000",
        waha_api_key=None,
        waha_session="default",
        agent_name="Demetrio",
        calendly_url="https://calendly.com/test",
        red_info_url="https://example.com/info",
    )
    defaults.update(overrides)
    return NotificationConfig(**defaults)


def test_build_notification_text_gold_requires_calendly():
    config = _make_config(calendly_url=None)
    text, reason = build_notification_text("GOLD", config)
    assert text is None
    assert reason == "missing_calendly_url"


def test_build_notification_text_gold_includes_emoji_and_link():
    config = _make_config()
    text, reason = build_notification_text("GOLD", config)
    assert reason is None
    assert "🏆" in text
    assert "calendly.com/test" in text
    assert "Demetrio" in text


def test_build_notification_text_silver_uses_agent():
    config = _make_config()
    text, reason = build_notification_text("SILVER", config)
    assert reason is None
    assert "Demetrio" in text
    assert "✅" in text


def test_build_notification_text_red_requires_link():
    config = _make_config(red_info_url=None)
    text, reason = build_notification_text("RED", config)
    assert text is None
    assert reason == "missing_red_info_url"


def test_build_notification_text_red_includes_link_and_emoji():
    config = _make_config()
    text, reason = build_notification_text("RED", config)
    assert reason is None
    assert "🔗" in text
    assert "example.com/info" in text


def test_build_notification_text_unknown_label():
    config = _make_config()
    text, reason = build_notification_text("UNKNOWN", config)
    assert text is None
    assert reason == "unknown_label"
