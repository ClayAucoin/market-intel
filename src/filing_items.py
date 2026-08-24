import re

from src.filing_parser import get_filing_text


ITEM_PATTERN = re.compile(
    r"\bITEM\s+(\d+\.\d+)\b",
    re.IGNORECASE,
)


def find_items(text):
    items = []

    for match in ITEM_PATTERN.finditer(text):
        item_number = match.group(1)

        items.append(
            {
                "item": item_number,
                "position": match.start(),
            }
        )

    return items


if __name__ == "__main__":
    filing = get_filing_text("DELL", "8-K")

    items = find_items(filing["text"])

    print(
        f"{filing['ticker']} "
        f"{filing['filing_date']} "
        f"8-K"
    )

    print()

    for item in items:
        print(f"Item {item['item']}")