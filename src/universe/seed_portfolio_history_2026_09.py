from src.database import get_connection

from src.universe.analysis_universe import (
    add_security_to_universe,
    create_universe,
)


UNIVERSE_NAME = "portfolio_history_2026_09"


TICKERS = [
    "ABBV",
    "ADBE",
    "AMD",
    "GOOGL",
    "AMZN",
    "ADI",
    "AAPL",
    "AXSM",
    "BAC",
    "BA",
    "AVGO",
    "CDNS",
    "CHKP",
    "CHDN",
    "KO",
    "COIN",
    "CRSP",
    "DK",
    "DAL",
    "DLR",
    "ETN",
    "LLY",
    "ENB",
    "ECG",
    "GD",
    "GLOB",
    "HD",
    "IBM",
    "NTLA",
    "JNJ",
    "KEYS",
    "KTB",
    "MRVL",
    "MDU",
    "MSFT",
    "MDB",
    "NVDA",
    "ORCL",
    "PM",
    "QCOM",
    "O",
    "RTX",
    "CRM",
    "SNPS",
    "TXT",
    "TSCO",
    "TRMB",
    "TFC",
    "VG",
    "VMRK",
]


MANUAL_SECTORS = {
    "AXSM": "Healthcare",
    "CHDN": "Consumer Discretionary",
    "CHKP": "Technology",
    "CRSP": "Healthcare",
    "DK": "Energy",
    "ECG": "Industrials",
    "ENB": "Energy",
    "GLOB": "Technology",
    "KTB": "Consumer Discretionary",
    "MDB": "Technology",
    "MDU": "Utilities",
    "NTLA": "Healthcare",
    "VG": "Energy",
}


def get_existing_sector(ticker):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT aum.sector

                FROM securities s

                JOIN analysis_universe_members aum
                    ON aum.security_id = s.id

                WHERE UPPER(s.ticker) = UPPER(%s)
                  AND aum.sector IS NOT NULL

                ORDER BY aum.id

                LIMIT 1;
                """,
                (ticker,),
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return row[0]


def get_sector(ticker):
    sector = get_existing_sector(ticker)

    if sector is not None:
        return sector

    return MANUAL_SECTORS.get(ticker)


def seed():
    create_universe(
        UNIVERSE_NAME,
        (
            "Historical Portfolio "
            "portfolio snapshot for "
            "September 2026."
        ),
    )

    added = 0
    missing = []
    missing_sector = []

    for ticker in TICKERS:
        sector = get_sector(ticker)

        try:
            add_security_to_universe(
                UNIVERSE_NAME,
                ticker,
                sector=sector,
            )

            added += 1

            if sector is None:
                missing_sector.append(ticker)

            print(
                f"Added {ticker:<6} "
                f"{sector or 'UNKNOWN'}"
            )

        except ValueError as error:
            missing.append(ticker)

            print(
                f"SKIPPED {ticker}: "
                f"{error}"
            )

    print()
    print("=" * 60)
    print("HISTORICAL PORTFOLIO SEPTEMBER 2026 UNIVERSE")
    print("=" * 60)

    print(
        "Expected holdings:",
        len(TICKERS),
    )

    print(
        "Added:",
        added,
    )

    print(
        "Missing securities:",
        len(missing),
    )

    print(
        "Missing sectors:",
        len(missing_sector),
    )

    if missing:
        print(
            "Missing tickers:",
            ", ".join(missing),
        )

    if missing_sector:
        print(
            "Unknown sectors:",
            ", ".join(missing_sector),
        )

    print()
    print(
        "portfolio_history_2026_09 "
        "seed completed."
    )


if __name__ == "__main__":
    seed()