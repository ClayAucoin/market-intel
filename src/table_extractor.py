import pandas as pd

from src.document_service import get_exhibit_by_id
from src.sec_client import SEC_HEADERS

import requests


def extract_tables(exhibit_id):
    document = get_exhibit_by_id(exhibit_id)

    response = requests.get(
        document["document_url"],
        headers=SEC_HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    tables = pd.read_html(
        response.text,
    )

    return document, tables


if __name__ == "__main__":
    EXHIBIT_ID = 28

    document, tables = extract_tables(EXHIBIT_ID)

    print(
        f"{document['ticker']} "
        f"{document['exhibit_type']}"
    )

    print(f"HTML tables found: {len(tables)}")

    search_terms = [
        "net revenue",
        "gross margin",
        "operating income",
        "net income",
        "earnings per share",
        "free cash flow",
    ]

    for table_index, table in enumerate(tables, start=1):
        for row_index, row in table.iterrows():
            row_text = " ".join(
                str(value)
                for value in row.values
            ).lower()

            if any(
                term in row_text
                for term in search_terms
            ):
                print()
                print("=" * 80)
                print(
                    f"TABLE {table_index}, "
                    f"ROW {row_index}"
                )
                print("=" * 80)

                start = max(0, row_index - 2)
                end = min(
                    len(table),
                    row_index + 3,
                )

                print(
                    table.iloc[start:end].to_string(
                        index=True,
                    )
                )