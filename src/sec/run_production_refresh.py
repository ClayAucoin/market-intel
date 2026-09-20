"""SEC-only live entry point. Does not run prices, events, paper trading or notifications."""
import argparse

from src.sec.production_report import run_reported
from src.financials.import_universe_financials import import_universe as import_financials
from src.sec.import_universe_filings import import_universe as import_filings


def refresh(universe):
    def imports():
        import_financials(universe, production_refresh=True)
        import_filings(universe, production_refresh=True)
    return run_reported(universe, imports)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("universe", nargs="?", default="expanded_500")
    parser.add_argument("--production-refresh", action="store_true", required=True)
    args = parser.parse_args()
    refresh(args.universe)


if __name__ == "__main__":
    main()
