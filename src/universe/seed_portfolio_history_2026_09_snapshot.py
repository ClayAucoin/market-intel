from decimal import Decimal

from src.database import get_connection
from src.universe.analysis_universe import (
    get_security_id,
)


PORTFOLIO_NAME = "Historical Portfolio"
SNAPSHOT_MONTH = "2026-09-01"
SOURCE_FILENAME = "2026-09.PDF"

CASH = Decimal("4025.49")
TOTAL_PORTFOLIO_VALUE = Decimal("285785.12")
TOTAL_COST_BASIS = Decimal("103681.47")


HOLDINGS = [
    ("ABBV", "ABBVIE INC", "258.64", "12.34655", "3193.31", "1357.20", "1852.78"),
    ("ADBE", "ADOBE INC", "282.82", "10.00", "2828.20", "451.37", "2409.43"),
    ("AMD", "ADVANCED MICRO DEVICES INC", "457.86", "17.00", "7783.62", "2884.60", "4928.77"),
    ("GOOGL", "ALPHABET INC CL A", "337.01", "60.31321", "20326.15", "3605.24", "16600.89"),
    ("AMZN", "AMAZON.COM INC", "255.07", "16.00", "4081.12", "2009.97", "2068.75"),
    ("ADI", "ANALOG DEVICES INC", "357.64", "10.00", "3576.40", "2186.00", "1359.20"),
    ("AAPL", "APPLE INC", "325.57", "206.12061", "67106.68", "4283.43", "62732.56"),
    ("AXSM", "AXSOME THERAPEUTICS INC.", "204.68", "20.00", "4093.60", "1247.60", "2809.00"),
    ("BAC", "BANK OF AMERICA CORP", "63.06", "45.8614", "2892.01", "1249.08", "1593.87"),
    ("BA", "BOEING CO", "209.89", "10.00", "2098.90", "2085.90", "-29.30"),
    ("AVGO", "BROADCOM INC", "369.82", "40.52492", "14986.92", "7619.66", "7361.59"),
    ("CDNS", "CADENCE DESIGN SYSTEMS INC", "307.32", "12.00", "3687.84", "502.44", "3254.04"),
    ("CHKP", "CHECK POINT SOFTWARE TECH LTD", "133.83", "20.00", "2676.60", "2487.00", "202.40"),
    ("CHDN", "CHURCHILL DOWNS INC", "87.80", "10.18938", "894.62", "476.86", "406.05"),
    ("KO", "COCA-COLA CO", "88.83", "22.14217", "1966.88", "1348.62", "599.89"),
    ("COIN", "COINBASE GLOBAL INC", "176.99", "10.00", "1769.90", "1676.80", "91.40"),
    ("CRSP", "CRISPR THERAPEUTICS AG", "55.89", "16.00", "894.24", "1015.40", "-106.28"),
    ("DK", "DELEK US HOLDINGS INC NEW", "72.44", "7.08018", "512.88", "170.53", "348.73"),
    ("DAL", "DELTA AIR LINES INC DEL", "78.56", "51.82777", "4071.58", "1696.41", "2262.20"),
    ("DLR", "DIGITAL REALTY TRUST INC", "181.80", "21.71267", "3947.36", "3142.80", "836.48"),
    ("ETN", "EATON CORPORATION PLC", "392.24", "5.01358", "1966.52", "2122.75", "-163.89"),
    ("LLY", "ELI LILLY & CO", "1173.98", "10.26623", "12052.34", "3769.75", "8139.08"),
    ("ENB", "ENBRIDGE INC", "50.33", "100.00", "5033.00", "3836.26", "1235.74"),
    ("ECG", "EVERUS CONSTR GROUP INC", "111.69", "21.00", "2345.49", "855.29", "1532.41"),

    ("GD", "GENERAL DYNAMICS CORP", "363.64", "5.38478", "1958.12", "1242.56", "746.63"),
    ("GLOB", "GLOBANTS A", "39.34", "17.00", "668.78", "1043.72", "-369.16"),
    ("HD", "HOME DEPOT INC", "320.30", "11.118", "3561.09", "3355.60", "199.60"),
    ("IBM", "IBM", "230.62", "34.4541", "7945.80", "4748.49", "3224.19"),
    ("NTLA", "INTELLIA THERAPEUTICS INC", "12.32", "33.00", "406.56", "983.35", "-564.74"),
    ("JNJ", "JOHNSON &JOHNSON", "274.63", "11.19762", "3075.20", "1835.99", "1200.69"),
    ("KEYS", "KEYSIGHT TECHNOLOGIES INC", "319.96", "10.00", "3199.60", "998.18", "2194.52"),
    ("KTB", "KONTOOR BRANDS INC", "73.43", "58.00106", "4259.01", "2473.11", "1856.09"),
    ("MRVL", "MARVELL TECHNOLOGY INC", "205.37", "40.77672", "8374.31", "1023.46", "7555.55"),
    ("MDU", "MDU RESOURCES GROUP INC", "19.78", "91.93175", "1818.41", "1130.11", "703.93"),
    ("MSFT", "MICROSOFT CORP", "497.88", "6.13891", "3056.44", "2030.37", "1045.35"),
    ("MDB", "MONGODB INC CLASS A COMMON", "395.28", "3.00", "1185.84", "1129.92", "172.71"),
    ("NVDA", "NVIDIA CORP", "226.48", "150.42909", "34069.18", "2403.81", "30305.49"),
    ("ORCL", "ORACLE CORP", "145.35", "15.14682", "2201.59", "3644.69", "-1504.14"),
    ("PM", "PHILIP MORRIS INTL INC", "188.17", "16.97455", "3194.10", "1648.71", "1528.08"),
    ("QCOM", "QUALCOMM INC", "169.31", "11.27819", "1909.51", "745.47", "1133.59"),
    ("O", "REALTY INCOME CORP", "61.34", "120.92145", "7417.32", "5274.48", "2145.26"),
    ("RTX", "RTXCORP", "202.23", "16.20614", "3277.36", "1412.35", "1912.50"),
    ("CRM", "SALESFORCE INC", "255.40", "12.0788", "3084.92", "2868.54", "249.12"),
    ("SNPS", "SYNOPSYS INC", "415.27", "8.00", "3322.16", "3167.60", "150.96"),
    ("TXT", "TEXTRON INC", "80.06", "27.00587", "2162.08", "2475.51", "-322.87"),
    ("TSCO", "TRACTOR SUPPLY CO", "35.06", "27.49007", "963.80", "600.20", "353.98"),
    ("TRMB", "TRIMBLE NAVIGATION LTD", "58.92", "15.00", "883.80", "1014.66", "-130.56"),
    ("TFC", "TRUIST FINL CORP", "50.86", "30.00", "1525.80", "1309.62", "173.58"),
    ("VG", "VENTURE GLOBAL INC", "14.64", "70.11449", "1026.47", "1040.01", "19.42"),
    ("VMRK", "VIVMARK RESIDENTIAL", "65.28", "37.16643", "2426.22", "2000.00", "426.22"),
]


def seed():
    if len(HOLDINGS) != 50:
        raise ValueError(
            f"Expected 50 holdings, found {len(HOLDINGS)}"
        )

    market_value_total = sum(
        Decimal(row[4])
        for row in HOLDINGS
    )

    calculated_total = (
        market_value_total
        + CASH
    )

    cost_basis_total = sum(
        Decimal(row[5])
        for row in HOLDINGS
    )

    gain_loss_total = sum(
        Decimal(row[6])
        for row in HOLDINGS
    )

    print("HISTORICAL PORTFOLIO SEPTEMBER 2026 SNAPSHOT")
    print("=" * 60)

    print(
        f"Holdings market value: "
        f"${market_value_total:,.2f}"
    )

    print(
        f"Cash: "
        f"${CASH:,.2f}"
    )

    print(
        f"Calculated total: "
        f"${calculated_total:,.2f}"
    )

    print(
        f"Source total: "
        f"${TOTAL_PORTFOLIO_VALUE:,.2f}"
    )

    print(
        f"Calculated cost basis: "
        f"${cost_basis_total:,.2f}"
    )

    print(
        f"Source cost basis: "
        f"${TOTAL_COST_BASIS:,.2f}"
    )

    print(
        f"Reported gain/loss total: "
        f"${gain_loss_total:,.2f}"
    )

    if calculated_total != TOTAL_PORTFOLIO_VALUE:
        raise ValueError(
            "Portfolio value total does not "
            "match source document."
        )

    if cost_basis_total != TOTAL_COST_BASIS:
        raise ValueError(
            "Cost basis total does not "
            "match source document."
        )

    security_rows = []

    for row in HOLDINGS:
        ticker = row[0]

        security_id = get_security_id(
            ticker
        )

        if security_id is None:
            raise ValueError(
                f"Security not found: {ticker}"
            )

        security_rows.append(
            (
                security_id,
                *row,
            )
        )

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO portfolio_snapshots (
                    portfolio_name,
                    snapshot_month,
                    cash,
                    total_portfolio_value,
                    total_cost_basis,
                    source_filename
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )

                ON CONFLICT (
                    portfolio_name,
                    snapshot_month
                )
                DO UPDATE SET
                    cash =
                        EXCLUDED.cash,

                    total_portfolio_value =
                        EXCLUDED.total_portfolio_value,

                    total_cost_basis =
                        EXCLUDED.total_cost_basis,

                    source_filename =
                        EXCLUDED.source_filename,

                    updated_at =
                        CURRENT_TIMESTAMP

                RETURNING id;
                """,
                (
                    PORTFOLIO_NAME,
                    SNAPSHOT_MONTH,
                    CASH,
                    TOTAL_PORTFOLIO_VALUE,
                    TOTAL_COST_BASIS,
                    SOURCE_FILENAME,
                ),
            )

            snapshot_id = cursor.fetchone()[0]

            cursor.execute(
                """
                DELETE FROM
                    portfolio_snapshot_holdings

                WHERE snapshot_id = %s;
                """,
                (
                    snapshot_id,
                ),
            )

            for (
                security_id,
                ticker,
                description,
                price,
                shares,
                market_value,
                cost_basis,
                gain_loss,
            ) in security_rows:
                cursor.execute(
                    """
                    INSERT INTO
                        portfolio_snapshot_holdings (
                            snapshot_id,
                            security_id,
                            ticker,
                            description,
                            price,
                            shares,
                            market_value,
                            cost_basis,
                            gain_loss
                        )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    );
                    """,
                    (
                        snapshot_id,
                        security_id,
                        ticker,
                        description,
                        Decimal(price),
                        Decimal(shares),
                        Decimal(market_value),
                        Decimal(cost_basis),
                        Decimal(gain_loss),
                    ),
                )

        conn.commit()

    print()
    print(
        f"Snapshot ID: {snapshot_id}"
    )

    print(
        f"Holdings saved: {len(HOLDINGS)}"
    )

    print(
        "September 2026 Historical Portfolio "
        "snapshot saved successfully."
    )


if __name__ == "__main__":
    seed()