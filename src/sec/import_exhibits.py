from src.sec.exhibit_parser import get_filing_documents
from src.sec.exhibit_repository import save_exhibits


def import_exhibits(ticker, form):
    filing, documents = get_filing_documents(
        ticker,
        form,
    )

    save_exhibits(
        filing["id"],
        documents,
    )

    return documents


if __name__ == "__main__":
    import_exhibits("DELL", "8-K")