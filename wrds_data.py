"""Data loading for the Topic 4 project (market-neutral long-short strategy).

CRSP monthly returns come from monthly_returns.csv (a crsp.msf_v2 export from the
WRDS website) when it is present, otherwise they are pulled with the WRDS API.
Compustat fundamentals, GICS sector history and the CRSP/Compustat link are always
pulled with the WRDS API. Everything is cached in ./data as parquet files.

Usage:
    import wrds_data
    data = wrds_data.load(username="your_wrds_username")
"""
from pathlib import Path

import pandas as pd
import wrds

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
CSV_PATH = HERE / "monthly_returns.csv"
START, END = "1989-12-01", "2025-12-31"

# CRSP v2 equivalent of the classic "share code 10/11 on NYSE/AMEX/NASDAQ" filter
COMMON_STOCK_SQL = """securitytype = 'EQTY' and securitysubtype = 'COM' and sharetype = 'NS'
          and primaryexch in ('N', 'A', 'Q')"""
LINK_SQL = "linktype in ('LU', 'LC') and linkprim in ('P', 'C')"


def crsp_from_csv(path=CSV_PATH):
    """Website export -> common stocks, one row per (permno, month).

    The raw export also holds ETFs, closed-end funds and ADRs, and repeats a
    (permno, month) row when ticker/SIC/exchange changes within the month.
    In a stock's last (delisting) month the export has no security type and
    placeholder codes (exchange X, SIC 0, ...), so the previous month's
    descriptors are carried forward; otherwise the filter would drop every
    delisting return.
    """
    df = pd.read_csv(path, parse_dates=["MthCalDt"], low_memory=False)
    df = df.sort_values(["PERMNO", "MthCalDt"])
    desc = ["PrimaryExch", "USIncFlg", "SecurityType", "SecuritySubType", "ShareType", "Ticker", "SICCD"]
    df[desc] = df[desc].astype(object).where(df.SecurityType.notna())
    df[desc] = df.groupby("PERMNO")[desc].ffill()
    df = df[(df.SecurityType == "EQTY") & (df.SecuritySubType == "COM")
            & (df.ShareType == "NS") & df.PrimaryExch.isin(["N", "A", "Q"])]
    df = df.drop_duplicates(["PERMNO", "MthCalDt"], keep="last")
    df.columns = df.columns.str.lower()
    df["siccd"] = df.siccd.astype("int64")
    return df[["permno", "mthcaldt", "mthret", "mthprc", "mthcap", "siccd", "ticker", "usincflg"]]


def crsp_from_wrds(db):
    """Same content as crsp_from_csv, pulled with the API (~2.4M rows, 1-2 minutes)."""
    df = db.raw_sql(f"""
        select permno, mthcaldt, mthret, mthprc, mthcap, siccd, ticker, usincflg
        from crsp.msf_v2
        where mthcaldt between '{START}' and '{END}'
          and {COMMON_STOCK_SQL}
    """, date_cols=["mthcaldt"])
    df = df.drop_duplicates(["permno", "mthcaldt"], keep="last")
    num = ["mthret", "mthprc", "mthcap"]
    df[num] = df[num].astype(float)                       # same dtypes as the CSV path
    df[["permno", "siccd"]] = df[["permno", "siccd"]].astype("int64")
    return df


def ccm_links(db):
    return db.raw_sql(f"""
        select gvkey, lpermno as permno, linkdt, linkenddt
        from crsp.ccmxpf_lnkhist
        where {LINK_SQL} and lpermno is not null
    """, date_cols=["linkdt", "linkenddt"])


def gics_history(db):
    # comp.co_hgic starts in 1999-06; comp.company holds the current sector as a fallback
    hist = db.raw_sql("select gvkey, indfrom, indthru, gsector from comp.co_hgic",
                      date_cols=["indfrom", "indthru"])
    current = db.raw_sql("select gvkey, gsector from comp.company where gsector is not null")
    return hist, current


def compustat_annual(db):
    return db.raw_sql(f"""
        select gvkey, datadate, at, lt, seq, ceq, pstk, pstkrv, pstkl, txditc, revt, cogs, ib
        from comp.funda
        where indfmt = 'INDL' and datafmt = 'STD' and popsrc = 'D' and consol = 'C'
          and datadate >= '1985-01-01'
          and gvkey in (select distinct gvkey from crsp.ccmxpf_lnkhist where {LINK_SQL})
    """, date_cols=["datadate"])


def crsp_daily(db, permnos, start=START, end=END):
    """Daily returns of the given PERMNOs (pulled year by year to keep memory low)."""
    inlist = ",".join(str(int(p)) for p in permnos)
    chunks = []
    for year in range(pd.Timestamp(start).year, pd.Timestamp(end).year + 1):
        chunks.append(db.raw_sql(f"""
            select permno, dlycaldt as date, dlyret as ret
            from crsp.dsf_v2
            where permno in ({inlist})
              and dlycaldt between '{max(start, f"{year}-01-01")}' and '{min(end, f"{year}-12-31")}'
        """, date_cols=["date"]))
        print(year, end=" ", flush=True)
    print()
    return pd.concat(chunks, ignore_index=True)


def ff_daily(db, start=START, end=END):
    return db.raw_sql(f"""
        select date, mktrf, rf from ff.factors_daily
        where date between '{start}' and '{end}'
    """, date_cols=["date"])


def load_daily(permnos, username=None):
    """Daily stock returns for `permnos` and daily Fama-French market / rf, cached in ./data."""
    DATA_DIR.mkdir(exist_ok=True)
    p_ret, p_mkt = DATA_DIR / "crsp_daily.parquet", DATA_DIR / "ff_daily.parquet"
    cached = pd.read_parquet(p_ret, columns=["permno"]).permno.unique() if p_ret.exists() else []
    if not set(permnos) <= set(cached) or not p_mkt.exists():
        db = wrds.Connection(wrds_username=username)
        crsp_daily(db, permnos).to_parquet(p_ret, index=False)
        ff_daily(db).to_parquet(p_mkt, index=False)
        db.close()
    return pd.read_parquet(p_ret), pd.read_parquet(p_mkt)


def load(username=None, csv_path=CSV_PATH, refresh=False):
    """Return a dict of DataFrames; WRDS is queried only for files missing from ./data."""
    DATA_DIR.mkdir(exist_ok=True)
    names = ["crsp", "ccm_links", "gics_hist", "gics_current", "funda"]
    paths = {n: DATA_DIR / f"{n}.parquet" for n in names}
    if refresh or not all(p.exists() for p in paths.values()):
        db = wrds.Connection(wrds_username=username)
        crsp = crsp_from_csv(csv_path) if Path(csv_path).exists() else crsp_from_wrds(db)
        gics_hist, gics_current = gics_history(db)
        pulled = {"crsp": crsp, "ccm_links": ccm_links(db), "gics_hist": gics_hist,
                  "gics_current": gics_current, "funda": compustat_annual(db)}
        db.close()
        for n, df in pulled.items():
            df.to_parquet(paths[n], index=False)
            print(f"{n}: {len(df):,} rows")
    return {n: pd.read_parquet(p) for n, p in paths.items()}


if __name__ == "__main__":
    import sys
    load(username=sys.argv[1] if len(sys.argv) > 1 else None, refresh=True)
