from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow


CLIENT_FILE = Path(
    "credentials/gmail_oauth_client.json"
)

TOKEN_FILE = Path(
    "credentials/gmail_token.json"
)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
]


def main():
    if not CLIENT_FILE.exists():
        raise FileNotFoundError(
            f"Missing OAuth client file: {CLIENT_FILE}"
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_FILE,
        SCOPES,
    )

    credentials = flow.run_local_server(
        port=0,
        open_browser=False,
    )

    TOKEN_FILE.write_text(
        credentials.to_json(),
        encoding="utf-8",
    )

    TOKEN_FILE.chmod(
        0o600
    )

    print()
    print("Gmail OAuth authorization complete.")
    print(
        f"Token saved to: {TOKEN_FILE}"
    )


if __name__ == "__main__":
    main()