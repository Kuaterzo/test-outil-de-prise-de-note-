"""Envoi de la synthèse par e-mail (SMTP), fonctionnalité optionnelle.

S'appuie uniquement sur la bibliothèque standard (`smtplib`, `email`). La
construction du message est *pure* (donc testable sans réseau) ; l'envoi est
isolé dans :func:`send_email`.

Le serveur SMTP se configure dans la configuration (`smtp_host`, `smtp_port`,
`smtp_user`, …). Le mot de passe peut être fourni via la configuration ou, de
préférence, via la variable d'environnement ``PMO_SMTP_PASSWORD``.
"""

from __future__ import annotations

import mimetypes
import os
from email.message import EmailMessage
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Optional, Sequence

if TYPE_CHECKING:
    from .config import Config


class EmailError(RuntimeError):
    """Erreur d'envoi d'e-mail (configuration, connexion, authentification)."""


def parse_recipients(value: str | Sequence[str]) -> list[str]:
    """Normalise une liste de destinataires (chaîne « a, b » ou séquence)."""
    if isinstance(value, str):
        items = value.split(",")
    else:
        items = list(value)
    return [item.strip() for item in items if item and item.strip()]


def build_email_message(
    subject: str,
    body: str,
    sender: str,
    recipients: Sequence[str],
    attachments: Optional[Iterable[Path]] = None,
) -> EmailMessage:
    """Construit un e-mail texte avec pièces jointes (synthèse, documents…)."""
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    for path in attachments or []:
        path = Path(path)
        if not path.exists():
            continue
        ctype, _ = mimetypes.guess_type(path.name)
        maintype, _, subtype = (ctype or "application/octet-stream").partition("/")
        message.add_attachment(
            path.read_bytes(),
            maintype=maintype,
            subtype=subtype or "octet-stream",
            filename=path.name,
        )
    return message


def send_email(
    message: EmailMessage,
    *,
    host: str,
    port: int = 587,
    username: Optional[str] = None,
    password: Optional[str] = None,
    use_tls: bool = True,
    timeout: float = 30.0,
) -> None:
    """Envoie un e-mail via SMTP (STARTTLS par défaut, SSL implicite si port 465)."""
    import smtplib

    if not host:
        raise EmailError("Aucun serveur SMTP n'est configuré (smtp_host).")

    try:
        if port == 465:  # SSL implicite
            server = smtplib.SMTP_SSL(host, port, timeout=timeout)
        else:
            server = smtplib.SMTP(host, port, timeout=timeout)
        with server:
            if use_tls and port != 465:
                server.starttls()
            if username:
                server.login(username, password or "")
            server.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        raise EmailError(
            "Authentification SMTP refusée. Vérifie l'identifiant et le mot de "
            "passe (variable PMO_SMTP_PASSWORD)."
        ) from exc
    except smtplib.SMTPException as exc:
        raise EmailError(f"Échec de l'envoi de l'e-mail : {exc}") from exc
    except OSError as exc:
        raise EmailError(
            f"Connexion au serveur SMTP {host}:{port} impossible : {exc}"
        ) from exc


def send_synthesis_email(
    config: "Config",
    subject: str,
    body: str,
    attachments: Optional[Iterable[Path]] = None,
) -> list[str]:
    """Envoie la synthèse aux destinataires définis dans la configuration.

    Renvoie la liste des destinataires. Lève :class:`EmailError` en cas de
    configuration incomplète ou d'échec d'envoi.
    """
    recipients = parse_recipients(config.email_to)
    if not recipients:
        raise EmailError("Aucun destinataire n'est défini (email_to).")

    sender = config.email_from or config.smtp_user
    if not sender:
        raise EmailError("Aucune adresse d'expéditeur (email_from).")

    password = config.smtp_password or os.environ.get("PMO_SMTP_PASSWORD")
    message = build_email_message(subject, body, sender, recipients, attachments)
    send_email(
        message,
        host=config.smtp_host,
        port=config.smtp_port,
        username=config.smtp_user or None,
        password=password,
        use_tls=config.smtp_use_tls,
    )
    return recipients


__all__ = [
    "EmailError",
    "parse_recipients",
    "build_email_message",
    "send_email",
    "send_synthesis_email",
]
