import pandas as pd

from src.database import get_connection


CSV_PATH = "data/sp500_components_history.csv"
INDEX_NAME = "S&P 500"
SOURCE = "thuningxu/sp500nq100"
START_DATE = pd.Timestamp("2018-01-01")


def normalize_ticker(ticker):
    return ticker.strip().upper()


def ticker_candidates(ticker):
    ticker = normalize_ticker(ticker)

    return {
        ticker,
        ticker.replace(".", "-"),
        ticker.replace("-", "."),
    }


def load_security_maps(cursor):
    cursor.execute(
        """
        SELECT ticker, id
        FROM securities;
        """
    )

    direct = {
        ticker.upper(): security_id
        for ticker, security_id in cursor.fetchall()
    }

    cursor.execute(
        """
        SELECT ticker, security_id
        FROM security_ticker_history;
        """
    )

    history = {
        ticker.upper(): security_id
        for ticker, security_id in cursor.fetchall()
    }

    return direct, history


def resolve_security_id(ticker, direct, history):
    for candidate in ticker_candidates(ticker):
        if candidate in direct:
            return direct[candidate]

    for candidate in ticker_candidates(ticker):
        if candidate in history:
            return history[candidate]

    return None


def load_snapshots():
    df = pd.read_csv(CSV_PATH)

    df["date"] = pd.to_datetime(df["date"])

    df = df[
        df["date"] >= START_DATE
    ].copy()

    df = df.sort_values("date")

    snapshots = []

    for _, row in df.iterrows():
        tickers = {
            normalize_ticker(ticker)
            for ticker in str(row["tickers"]).split(",")
            if ticker.strip()
        }

        snapshots.append(
            (
                row["date"].date(),
                tickers,
            )
        )

    return snapshots


def build_membership_runs(
    snapshots,
    direct,
    history,
):
    active = {}
    completed = []

    for snapshot_date, tickers in snapshots:
        current = {}

        for ticker in tickers:
            security_id = resolve_security_id(
                ticker,
                direct,
                history,
            )

            if security_id is None:
                raise RuntimeError(
                    f"Could not resolve ticker: {ticker}"
                )

            current[security_id] = ticker

        current_ids = set(current)
        active_ids = set(active)

        entering = current_ids - active_ids
        leaving = active_ids - current_ids

        for security_id in entering:
            active[security_id] = {
                "ticker": current[security_id],
                "effective_from": snapshot_date,
            }

        for security_id in leaving:
            run = active.pop(security_id)

            completed.append(
                {
                    "security_id": security_id,
                    "ticker": run["ticker"],
                    "effective_from": run["effective_from"],
                    "effective_to": (
                        snapshot_date
                        - pd.Timedelta(days=1)
                    ),
                }
            )

    for security_id, run in active.items():
        completed.append(
            {
                "security_id": security_id,
                "ticker": run["ticker"],
                "effective_from": run["effective_from"],
                "effective_to": None,
            }
        )

    return completed


def main():
    snapshots = load_snapshots()

    if not snapshots:
        raise RuntimeError(
            "No S&P 500 snapshots found."
        )

    with get_connection() as conn:
        with conn.cursor() as cursor:
            direct, history = load_security_maps(
                cursor
            )

            runs = build_membership_runs(
                snapshots,
                direct,
                history,
            )

            cursor.execute(
                """
                DELETE FROM index_membership_history
                WHERE index_name = %s;
                """,
                (INDEX_NAME,),
            )

            for run in runs:
                cursor.execute(
                    """
                    INSERT INTO index_membership_history (
                        index_name,
                        security_id,
                        effective_from,
                        effective_to,
                        source,
                        notes
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    );
                    """,
                    (
                        INDEX_NAME,
                        run["security_id"],
                        run["effective_from"],
                        run["effective_to"],
                        SOURCE,
                        (
                            "Derived from historical "
                            "S&P 500 membership snapshots."
                        ),
                    ),
                )

    print(
        "Snapshots:",
        len(snapshots),
    )

    print(
        "Membership runs inserted:",
        len(runs),
    )

    print(
        "First snapshot:",
        snapshots[0][0],
    )

    print(
        "Latest snapshot:",
        snapshots[-1][0],
    )


if __name__ == "__main__":
    main()