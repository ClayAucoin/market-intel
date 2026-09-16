from src.notifications.gmail_notifier import send_email
from src.notifications.slack_notifier import send_slack_message


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
        try:
            results["gmail"] = send_email(
                to_address=DEFAULT_EMAIL,
                subject=subject,
                body=message,
            )

        except Exception as error:
            results["gmail"] = {
                "success": False,
                "error": str(error),
            }

            print(
                "WARNING: Gmail notification "
                f"failed: {error}"
            )

    if send_slack:
        try:
            results["slack"] = send_slack_message(
                channel=DEFAULT_SLACK_CHANNEL,
                message=(
                    f"<@U0BMEND132M>\n\n"
                    f"*{subject}*\n\n"
                    f"{message}"
                ),
            )

        except Exception as error:
            results["slack"] = {
                "success": False,
                "error": str(error),
            }

            print(
                "WARNING: Slack notification "
                f"failed: {error}"
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