import os
import json
import urllib.request
import urllib.error

from dotenv import load_dotenv


load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")


def send_slack_message(channel: str, message: str) -> dict:
    if not SLACK_BOT_TOKEN:
        raise ValueError("SLACK_BOT_TOKEN is not set in the .env file.")

    url = "https://slack.com/api/chat.postMessage"

    payload = {
        "channel": channel,
        "text": message,
    }

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            result = json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"Slack HTTP error: {error.code} {error.reason}"
        ) from error

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Could not connect to Slack: {error.reason}"
        ) from error

    if not result.get("ok"):
        raise RuntimeError(
            f"Slack API error: {result.get('error', 'unknown_error')}"
        )

    return result


if __name__ == "__main__":
    result = send_slack_message(
        channel="#market-intel-alerts",
        message=(
            "Market Intel Slack test\n\n"
            "Slack notifications are working."
        ),
    )

    print("Slack message sent successfully.")
    print(f"Channel: {result.get('channel')}")
    print(f"Timestamp: {result.get('ts')}")