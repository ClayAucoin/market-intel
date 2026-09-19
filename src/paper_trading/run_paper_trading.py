from src.paper_trading.paper_position_manager import (
    main as manage_positions,
)
from src.paper_trading.paper_trading_engine import (
    fill_pending_purchases,
    main as process_signals,
)
from src.paper_trading.paper_trading_report import (
    main as show_report,
)


def main(universe_name):
    print()
    print("=" * 100)
    print("DAILY PAPER TRADING RUN")
    print("=" * 100)

    fill_pending_purchases()
    manage_positions()

    print()
    print("=" * 100)

    process_signals(
        universe_name
    )

    print()
    print("=" * 100)

    show_report()

    print()
    print("=" * 100)
    print("DAILY PAPER TRADING RUN COMPLETE")
    print("=" * 100)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python -m "
            "src.paper_trading.run_paper_trading "
            "<universe_name>"
        )

    main(
        sys.argv[1]
    )
