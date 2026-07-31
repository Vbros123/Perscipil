from core import email


class SuccessfulResponse:
    def raise_for_status(self) -> None:
        return None


def test_resend_delivery_uses_https_api(monkeypatch):
    captured = {}

    def fake_post(url, *, json, headers, timeout):
        captured.update(url=url, json=json, headers=headers, timeout=timeout)
        return SuccessfulResponse()

    monkeypatch.setattr(email.settings, "EMAIL_DELIVERY_MODE", "resend")
    monkeypatch.setattr(email.settings, "RESEND_API_URL", "https://api.resend.test/emails")
    monkeypatch.setattr(email.settings, "RESEND_API_KEY", "re_test")
    monkeypatch.setattr(email.settings, "SMTP_FROM_NAME", "PrivateLens Security")
    monkeypatch.setattr(email.settings, "SMTP_FROM_EMAIL", "security@example.com")
    monkeypatch.setattr(email.httpx, "post", fake_post)

    email._send_email("user@example.com", "Verify", "Plain text", "<p>HTML</p>")

    assert captured["url"] == "https://api.resend.test/emails"
    assert captured["headers"] == {"Authorization": "Bearer re_test"}
    assert captured["json"]["to"] == ["user@example.com"]
    assert captured["json"]["from"] == "PrivateLens Security <security@example.com>"
