import json
from pathlib import Path

import requests

from src.database import get_connection
from src.sec.sec_client import SEC_HEADERS


SEC_URL = (
    "https://www.sec.gov/files/"
    "company_tickers_exchange.json"
)

CACHE_PATH = Path(
    "data/cache/sec/"
    "company_tickers_exchange.json"
)

SOURCE_NAME = (
    "SEC company_tickers_exchange"
)


def download_sec_mapping():
    print(
        "Downloading SEC ticker mapping..."
    )

    response = requests.get(
        SEC_URL,
        headers=SEC_HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    CACHE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with CACHE_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
        )

    print(
        "Saved SEC ticker mapping "
        "to cache."
    )

    return data


def load_sec_mapping(
    refresh=False,
):
    if (
        CACHE_PATH.exists()
        and not refresh
    ):
        print(
            "Loaded SEC ticker mapping "
            "from cache."
        )

        with CACHE_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    return download_sec_mapping()


def parse_mapping(data):
    fields = data.get(
        "fields",
        []
    )

    rows = data.get(
        "data",
        []
    )

    if not fields or not rows:
        raise ValueError(
            "Unexpected SEC ticker "
            "mapping format."
        )

    parsed = []

    for row in rows:
        record = dict(
            zip(fields, row)
        )

        cik = str(
            record.get("cik", "")
        ).zfill(10)

        ticker = (
            record.get("ticker")
            or ""
        ).strip().upper()

        name = (
            record.get("name")
            or ""
        ).strip()

        exchange = (
            record.get("exchange")
            or ""
        ).strip()

        if (
            not cik
            or not ticker
            or not name
        ):
            continue

        parsed.append(
            {
                "cik": cik,
                "ticker": ticker,
                "company_name": name,
                "exchange": (
                    exchange
                    if exchange
                    else None
                ),
            }
        )

    return parsed


def get_or_create_company(
    cursor,
    record,
):
    cursor.execute(
        """
        SELECT id
        FROM companies
        WHERE cik = %s
        LIMIT 1;
        """,
        (
            record["cik"],
        ),
    )

    row = cursor.fetchone()

    if row is not None:
        company_id = row[0]

        #
        # Keep the SEC issuer name current.
        # Do NOT overwrite the legacy ticker
        # or exchange columns.
        #
        cursor.execute(
            """
            UPDATE companies
            SET
                company_name = %s,
                updated_at =
                    CURRENT_TIMESTAMP
            WHERE id = %s;
            """,
            (
                record["company_name"],
                company_id,
            ),
        )

        return company_id

    #
    # New issuer. Ticker and exchange
    # belong in securities now, not here.
    #
    cursor.execute(
        """
        INSERT INTO companies (
            cik,
            ticker,
            company_name,
            exchange
        )
        VALUES (
            %s,
            NULL,
            %s,
            NULL
        )
        RETURNING id;
        """,
        (
            record["cik"],
            record["company_name"],
        ),
    )

    return cursor.fetchone()[0]


def import_securities(
    refresh=False,
):
    data = load_sec_mapping(
        refresh=refresh
    )

    records = parse_mapping(
        data
    )

    print(
        f"SEC security associations: "
        f"{len(records):,}"
    )

    inserted = 0

    with get_connection() as conn:
        with conn.cursor() as cursor:
            #
            # Remove mappings from our prior
            # SEC import so stale associations
            # disappear when this is refreshed.
            #
            cursor.execute(
                """
                DELETE FROM securities
                WHERE source = %s;
                """,
                (
                    SOURCE_NAME,
                ),
            )

            for record in records:
                company_id = (
                    get_or_create_company(
                        cursor,
                        record,
                    )
                )

                cursor.execute(
                    """
                    INSERT INTO securities (
                        company_id,
                        ticker,
                        exchange,
                        source
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s
                    )

                    ON CONFLICT (
                        company_id,
                        ticker
                    )
                    DO UPDATE SET
                        exchange =
                            EXCLUDED.exchange,

                        source =
                            EXCLUDED.source,

                        updated_at =
                            CURRENT_TIMESTAMP;
                    """,
                    (
                        company_id,
                        record["ticker"],
                        record["exchange"],
                        SOURCE_NAME,
                    ),
                )

                inserted += 1

    print(
        f"Imported {inserted:,} "
        "security associations."
    )


if __name__ == "__main__":
    import_securities(
        refresh=False
    )