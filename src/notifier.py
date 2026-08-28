from src.gmail_notifier import send_email
from src.slack_notifier import send_slack_message


DEFAULT_EMAIL = "clay.marketintel@gmail.com"
DEFAULT_SLACK_CHANNEL = "#market-intel-alerts"


def send_notification(
    subject: str,
    message: str,
    send_gmail: bool = True,
    send_slack: bool = True,
) -> dict:
    results = {
        "gmail": None,
        "slack": None,
    }

    if send_gmail:
        results["gmail"] = send_email(
            to_address=DEFAULT_EMAIL,
            subject=subject,
            body=message,
        )

    if send_slack:
        results["slack"] = send_slack_message(
            channel=DEFAULT_SLACK_CHANNEL,
            # message=f"*{subject}*\n\n{message}",
            message=f"<@U0BMEND132M>\n\n*{subject}*\n\n{message}",
        )

    return results


if __name__ == "__main__":
    results = send_notification(
        subject="Market Intel Notification Test",
        message=(
            "This is a combined notification test.\n\n"
            "If everything is working, this message should arrive "
            "through both Gmail and Slack."
        ),
    )

    print("Notification test complete.")
    print(f"Gmail: {results['gmail']}")
    print(f"Slack: {results['slack']}")