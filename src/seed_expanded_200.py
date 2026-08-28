from io import StringIO

import pandas as pd
import requests

from src.analysis_universe import (
    add_security_to_universe,
    create_universe,
    get_security_id,
    get_universe_id,
)

from src.database import get_connection


UNIVERSE_NAME = "expanded_200"

TARGET_COMPANIES = 200

SLICKCHARTS_URL = (
    "https://www.slickcharts.com/sp500"
)

WIKIPEDIA_URL = (
    "https://en.wikipedia.org/wiki/"
    "List_of_S%26P_500_companies"
)


SECTOR_MAP = {
    "Information Technology":
        "Technology",

    "Communication Services":
        "Communication Services",

    "Financials":
        "Financials",

    "Health Care":
        "Healthcare",

    "Consumer Discretionary":
        "Consumer Discretionary",

    "Consumer Staples":
        "Consumer Staples",

    "Industrials":
        "Industrials",

    "Energy":
        "Energy",

    "Materials":
        "Materials",

    "Utilities":
        "Utilities",

    "Real Estate":
        "Real Estate",
}


def download_html(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; MarketIntel/1.0)"
        ),
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()

    return response.text


def normalize_source_symbol(
    symbol,
):
    symbol = str(
        symbol
    ).strip().upper()

    return symbol.replace(
        "-",
        ".",
    )


def get_database_symbol(
    symbol,
):
    symbol = normalize_source_symbol(
        symbol
    )

    return symbol.replace(
        ".",
        "-",
    )


def load_market_cap_ranking():
    print(
        "Downloading S&P 500 "
        "market-cap ranking..."
    )

    html = download_html(
        SLICKCHARTS_URL
    )

    tables = pd.read_html(
        StringIO(html)
    )

    ranking = None

    for table in tables:
        columns = {
            str(column).strip()
            for column in table.columns
        }

        if (
            "Symbol" in columns
            and "Company" in columns
            and "Weight" in columns
        ):
            ranking = table.copy()
            break

    if ranking is None:
        raise ValueError(
            "Could not find the "
            "Slickcharts S&P 500 table."
        )

    ranking["source_symbol"] = (
        ranking["Symbol"].apply(
            normalize_source_symbol
        )
    )

    ranking["market_cap_rank"] = (
        range(
            1,
            len(ranking) + 1,
        )
    )

    return ranking


def load_sp500_metadata():
    print(
        "Downloading S&P 500 "
        "sector metadata..."
    )

    html = download_html(
        WIKIPEDIA_URL
    )

    tables = pd.read_html(
        StringIO(html)
    )

    metadata = None

    for table in tables:
        columns = {
            str(column).strip()
            for column in table.columns
        }

        required = {
            "Symbol",
            "Security",
            "GICS Sector",
            "GICS Sub-Industry",
            "CIK",
        }

        if required.issubset(
            columns
        ):
            metadata = table.copy()
            break

    if metadata is None:
        raise ValueError(
            "Could not find the "
            "Wikipedia S&P 500 "
            "constituent table."
        )

    metadata["source_symbol"] = (
        metadata["Symbol"].apply(
            normalize_source_symbol
        )
    )

    metadata["CIK"] = (
        metadata["CIK"]
        .astype(str)
        .str.replace(
            ".0",
            "",
            regex=False,
        )
        .str.zfill(10)
    )

    return metadata


def build_candidates():
    ranking = (
        load_market_cap_ranking()
    )

    metadata = (
        load_sp500_metadata()
    )

    metadata_by_symbol = {}

    for _, row in metadata.iterrows():
        symbol = row[
            "source_symbol"
        ]

        metadata_by_symbol[
            symbol
        ] = row

    candidates = []

    seen_ciks = set()

    skipped_duplicate = []
    skipped_metadata = []
    skipped_database = []

    for _, row in ranking.iterrows():
        source_symbol = row[
            "source_symbol"
        ]

        metadata_row = (
            metadata_by_symbol.get(
                source_symbol
            )
        )

        if metadata_row is None:
            skipped_metadata.append(
                source_symbol
            )

            continue

        cik = metadata_row[
            "CIK"
        ]

        if cik in seen_ciks:
            skipped_duplicate.append(
                source_symbol
            )

            continue

        database_symbol = (
            get_database_symbol(
                source_symbol
            )
        )

        security_id = (
            get_security_id(
                database_symbol
            )
        )

        if security_id is None:
            skipped_database.append(
                database_symbol
            )

            continue

        raw_sector = metadata_row[
            "GICS Sector"
        ]

        sector = SECTOR_MAP.get(
            raw_sector,
            raw_sector,
        )

        candidates.append(
            {
                "ticker":
                    database_symbol,

                "company_name":
                    metadata_row[
                        "Security"
                    ],

                "cik":
                    cik,

                "sector":
                    sector,

                "industry":
                    metadata_row[
                        "GICS Sub-Industry"
                    ],

                "market_cap_rank":
                    row[
                        "market_cap_rank"
                    ],
            }
        )

        seen_ciks.add(
            cik
        )

        if (
            len(candidates)
            >= TARGET_COMPANIES
        ):
            break

    if (
        len(candidates)
        < TARGET_COMPANIES
    ):
        raise ValueError(
            "Could only resolve "
            f"{len(candidates)} "
            f"companies. "
            f"Need {TARGET_COMPANIES}."
        )

    return {
        "candidates":
            candidates,

        "skipped_duplicate":
            skipped_duplicate,

        "skipped_metadata":
            skipped_metadata,

        "skipped_database":
            skipped_database,
    }


def reset_universe():
    universe_id = get_universe_id(
        UNIVERSE_NAME
    )

    if universe_id is None:
        return

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM
                    analysis_universe_members

                WHERE universe_id = %s;
                """,
                (
                    universe_id,
                ),
            )


def seed():
    print()
    print(
        "BUILDING EXPANDED 200 "
        "MARKET UNIVERSE"
    )

    print("=" * 90)

    result = build_candidates()

    candidates = result[
        "candidates"
    ]

    print()
    print(
        "Resolved candidates:",
        len(candidates),
    )

    create_universe(
        UNIVERSE_NAME,
        (
            "200 large S&P 500 companies "
            "ranked by current market "
            "capitalization with duplicate "
            "issuer share classes removed."
        ),
    )

    reset_universe()

    print()
    print(
        "Seeding database..."
    )

    print("=" * 90)

    added = 0
    failed = []

    for company in candidates:
        ticker = company[
            "ticker"
        ]

        try:
            add_security_to_universe(
                UNIVERSE_NAME,
                ticker,
                sector=company[
                    "sector"
                ],
                industry=company[
                    "industry"
                ],
            )

            print(
                f"{added + 1:>3}. "
                f"{ticker:<7} "
                f"{company['sector']:<25} "
                f"{company['company_name']}"
            )

            added += 1

        except Exception as error:
            print(
                f"ERROR {ticker}: "
                f"{error}"
            )

            failed.append(
                {
                    "ticker":
                        ticker,

                    "error":
                        str(error),
                }
            )

    print()
    print("=" * 90)

    print(
        "expanded_200 seed completed."
    )

    print()
    print(
        "Requested:",
        TARGET_COMPANIES,
    )

    print(
        "Added:",
        added,
    )

    print(
        "Failed:",
        len(failed),
    )

    print(
        "Duplicate share classes skipped:",
        len(
            result[
                "skipped_duplicate"
            ]
        ),
    )

    print(
        "Missing metadata skipped:",
        len(
            result[
                "skipped_metadata"
            ]
        ),
    )

    print(
        "Missing database securities skipped:",
        len(
            result[
                "skipped_database"
            ]
        ),
    )

    if result[
        "skipped_database"
    ]:
        print()
        print(
            "Database securities skipped:"
        )

        for ticker in result[
            "skipped_database"
        ]:
            print(
                f"  {ticker}"
            )

    if failed:
        print()
        print(
            "Failures:"
        )

        for item in failed:
            print(
                f"  {item['ticker']}: "
                f"{item['error']}"
            )


if __name__ == "__main__":
    seed()