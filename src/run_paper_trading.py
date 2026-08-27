from src.paper_position_manager import (
    main as manage_positions,
)
from src.paper_trading_engine import (
    main as process_signals,
)
from src.paper_trading_report import (
    main as show_report,
)


def main():
    print()
    print("=" * 100)
    print("DAILY PAPER TRADING RUN")
    print("=" * 100)

    manage_positions()

    print()
    print("=" * 100)

    process_signals()

    print()
    print("=" * 100)

    show_report()

    print()
    print("=" * 100)
    print("DAILY PAPER TRADING RUN COMPLETE")
    print("=" * 100)


if __name__ == "__main__":
    main()