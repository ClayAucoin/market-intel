import base64
from email.message import EmailMessage
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


TOKEN_FILE = Path(
    "credentials/gmail_token.json"
)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
]


def get_credentials():
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(
            f"Missing Gmail token file: {TOKEN_FILE}"
        )

    credentials = Credentials.from_authorized_user_file(
        TOKEN_FILE,
        SCOPES,
    )

    if (
        credentials.expired
        and credentials.refresh_token
    ):
        credentials.refresh(
            Request()
        )

        TOKEN_FILE.write_text(
            credentials.to_json(),
            encoding="utf-8",
        )

        TOKEN_FILE.chmod(
            0o600
        )

    return credentials


def send_email(
    to_address,
    subject,
    body,
):
    credentials = get_credentials()

    service = build(
        "gmail",
        "v1",
        credentials=credentials,
    )

    message = EmailMessage()

    message["To"] = to_address
    message["From"] = (
        "clay.marketintel@gmail.com"
    )
    message["Subject"] = subject

    message.set_content(
        body
    )

    encoded_message = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode()

    result = (
        service.users()
        .messages()
        .send(
            userId="me",
            body={
                "raw": encoded_message,
            },
        )
        .execute()
    )

    return result