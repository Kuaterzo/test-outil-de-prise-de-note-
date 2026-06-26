import pytest

from pmo_notes import email_sender
from pmo_notes.config import Config
from pmo_notes.email_sender import (
    EmailError,
    build_email_message,
    parse_recipients,
    send_synthesis_email,
)


def test_parse_recipients_from_string():
    assert parse_recipients("a@x.fr, b@y.fr ,") == ["a@x.fr", "b@y.fr"]


def test_parse_recipients_from_list():
    assert parse_recipients(["a@x.fr", " ", "b@y.fr"]) == ["a@x.fr", "b@y.fr"]


def test_build_message_headers_and_body():
    msg = build_email_message(
        "Sujet", "Corps de la synthèse", "from@x.fr", ["to@y.fr", "to2@y.fr"]
    )
    assert msg["Subject"] == "Sujet"
    assert msg["From"] == "from@x.fr"
    assert msg["To"] == "to@y.fr, to2@y.fr"
    assert "Corps de la synthèse" in msg.get_content()


def test_build_message_with_attachment(tmp_path):
    f = tmp_path / "synthese.md"
    f.write_text("## Introduction\nok", encoding="utf-8")
    msg = build_email_message("S", "corps", "from@x.fr", ["to@y.fr"], attachments=[f])
    attachments = list(msg.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "synthese.md"


def test_send_synthesis_email_requires_recipients():
    with pytest.raises(EmailError):
        send_synthesis_email(Config(email_to=""), "S", "corps")


def test_send_synthesis_email_requires_sender():
    with pytest.raises(EmailError):
        send_synthesis_email(Config(email_to="to@y.fr", email_from="", smtp_user=""), "S", "corps")


def test_send_synthesis_email_success(monkeypatch):
    captured = {}

    def fake_send_email(message, **kwargs):
        captured["message"] = message
        captured["kwargs"] = kwargs

    monkeypatch.setattr(email_sender, "send_email", fake_send_email)
    config = Config(
        email_to="to@y.fr, to2@y.fr",
        email_from="from@x.fr",
        smtp_host="smtp.example.com",
        smtp_port=587,
    )
    recipients = send_synthesis_email(config, "Synthèse", "le corps")
    assert recipients == ["to@y.fr", "to2@y.fr"]
    assert captured["kwargs"]["host"] == "smtp.example.com"
    assert captured["message"]["From"] == "from@x.fr"
