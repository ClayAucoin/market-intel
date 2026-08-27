import subprocess
import sys

from src.import_universe_prices import (
    import_universe_prices,
)

from src.run_paper_trading import (
    main as run_paper_trading,
)


UNIVERSE = "expanded_50"


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
        "src.import_universe_financials",
        UNIVERSE,
    )


def refresh_filings():
    print_header(
        "STEP 2: REFRESH SEC FILINGS"
    )

    run_module(
        "src.import_universe_filings",
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
        "src.build_backtest_events",
        UNIVERSE,
    )


def run_paper_system():
    print_header(
        "STEP 5: RUN PAPER TRADING"
    )

    run_paper_trading()


def main():
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


if __name__ == "__main__":
    main()