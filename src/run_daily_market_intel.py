import subprocess
import sys

from src.daily_logger import (
    start_daily_log,
    stop_daily_log,
)

from src.prices.import_universe_prices import (
    import_universe_prices,
)

from src.notifications.notifier import (
    send_notification,
)

from src.paper_trading.run_paper_trading import (
    main as run_paper_trading,
)


UNIVERSE = "expanded_500"


def print_header(title):
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)


def run_module(
    module_name,
    *arguments,
):
    command = [
        sys.executable,
        "-m",
        module_name,
        *arguments,
    ]

    print()
    print(
        "Running:",
        " ".join(command),
    )
    print()

    result = subprocess.run(
        command,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"{module_name} failed "
            f"with exit code "
            f"{result.returncode}"
        )


def refresh_financials():
    print_header(
        "STEP 1: REFRESH FINANCIAL DATA"
    )

    run_module(
        "src.financials.import_universe_financials",
        UNIVERSE,
    )


def refresh_filings():
    print_header(
        "STEP 2: REFRESH SEC FILINGS"
    )

    run_module(
        "src.sec.import_universe_filings",
        UNIVERSE,
    )


def refresh_prices():
    print_header(
        "STEP 3: REFRESH MARKET PRICES"
    )

    import_universe_prices(
        universe_name=UNIVERSE,
        refresh=True,
    )


def rebuild_events():
    print_header(
        "STEP 4: REBUILD MARKET EVENTS"
    )

    run_module(
        "src.backtesting.build_backtest_events",
        UNIVERSE,
    )


def run_paper_system():
    print_header(
        "STEP 5: RUN PAPER TRADING"
    )

    run_paper_trading()


def send_success_notification(
    log_path,
):
    subject = (
        "Market Intel Daily Update Complete"
    )

    message = (
        "The Market Intel daily update "
        "completed successfully.\n\n"
        f"Universe: {UNIVERSE}\n"
        f"Log file: {log_path}\n\n"
        "Any new qualifying paper BUY or "
        "position-close events are sent "
        "as separate alerts."
    )

    send_notification(
        subject=subject,
        message=message,
    )


def send_failure_notification(
    error,
    log_path,
):
    subject = (
        "MARKET INTEL DAILY UPDATE FAILED"
    )

    message = (
        "The Market Intel daily update "
        "did not complete successfully.\n\n"
        f"Universe: {UNIVERSE}\n"
        f"Error: {error}\n"
        f"Log file: {log_path}\n\n"
        "Check the server log for the "
        "full error details."
    )

    send_notification(
        subject=subject,
        message=message,
    )


def run_daily_update():
    print()
    print("#" * 100)
    print("MARKET INTEL DAILY UPDATE")
    print("#" * 100)

    print(
        f"Universe: {UNIVERSE}"
    )

    refresh_financials()
    refresh_filings()
    refresh_prices()
    rebuild_events()
    run_paper_system()

    print()
    print("#" * 100)
    print(
        "MARKET INTEL DAILY UPDATE COMPLETE"
    )
    print("#" * 100)


def main():
    log = start_daily_log()

    log_path = log["path"]

    try:
        print(
            f"Log file: {log_path}"
        )

        run_daily_update()

        stop_daily_log(log)

        print()
        print(
            f"Full log saved to: {log_path}"
        )

        send_success_notification(
            log_path
        )

    except Exception as error:
        print()
        print("#" * 100)
        print(
            "MARKET INTEL DAILY UPDATE FAILED"
        )
        print("#" * 100)

        try:
            stop_daily_log(log)
        except Exception:
            pass

        try:
            send_failure_notification(
                error,
                log_path,
            )
        except Exception as notification_error:
            print()
            print(
                "Could not send failure "
                "notification:"
            )
            print(
                notification_error
            )

        raise


if __name__ == "__main__":
    main()