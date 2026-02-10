from src.services.notifications import NotificationConfig, build_notification_text


def test_build_notification_text_gold_requires_calendly():
    config = NotificationConfig(
        waha_base_url="http://waha:3000",
        waha_api_key=None,
        waha_session="default",
        agent_name="Agente",
        calendly_url=None,
        red_info_url="https://example.com/info",
    )
    text, reason = build_notification_text("GOLD", config)
    assert text is None
    assert reason == "missing_calendly_url"


def test_build_notification_text_silver_uses_agent():
    config = NotificationConfig(
        waha_base_url="http://waha:3000",
        waha_api_key=None,
        waha_session="default",
        agent_name="Demetrio",
        calendly_url="https://calendly.com/test",
        red_info_url="https://example.com/info",
    )
    text, reason = build_notification_text("SILVER", config)
    assert reason is None
    assert "Demetrio" in text


def test_build_notification_text_red_requires_link():
    config = NotificationConfig(
        waha_base_url="http://waha:3000",
        waha_api_key=None,
        waha_session="default",
        agent_name="Agente",
        calendly_url="https://calendly.com/test",
        red_info_url=None,
    )
    text, reason = build_notification_text("RED", config)
    assert text is None
    assert reason == "missing_red_info_url"
