from bs4 import BeautifulSoup

from src.filing_document import download_filing


def html_to_text(html):
    soup = BeautifulSoup(html, "html.parser")

    # Remove content that isn't useful for textual analysis.
    for element in soup(["script", "style"]):
        element.decompose()

    text = soup.get_text(separator="\n")

    # Clean excessive whitespace.
    lines = []

    for line in text.splitlines():
        line = " ".join(line.split())

        if line:
            lines.append(line)

    return "\n".join(lines)


def get_filing_text(ticker, form):
    filing = download_filing(ticker, form)

    filing["text"] = html_to_text(filing["html"])

    return filing


if __name__ == "__main__":
    filing = get_filing_text("DELL", "8-K")

    print("Company:", filing["company_name"])
    print("Filing date:", filing["filing_date"])
    print("Characters:", len(filing["text"]))
    print()
    print("=" * 70)
    print()
    print(filing["text"][:5000])