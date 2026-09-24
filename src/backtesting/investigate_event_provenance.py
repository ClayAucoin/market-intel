"""Read-only provenance capture and offline replay of unchanged event calculations.

Never calls builder.main/clear_backtest_events, never connects during replay, and
routes the original save function into an in-memory SQL-parameter recorder only.
"""
from bisect import bisect_left
from collections import Counter, defaultdict
from contextlib import ExitStack
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import re
import time
from unittest.mock import patch

from psycopg.rows import dict_row
from src.database import get_connection
from src.backtesting import build_backtest_events as builder, backtester
from src.analysis import event_timing, market_context
from src.analysis.experimental_signal import qualifies_experimental_signal
from src.backtesting.apply_acceptance_repair import configure, fingerprints, PIN
from src.backtesting.timestamp_rebuild_preflight import filing_drift
from src.backtesting.audit_sector_readiness import MEMBERSHIP

ROOT=Path('logs/research/timestamp_rebuild_2026-09-23')
CUTOFF=datetime(2026,9,23,13,57,52,311140,tzinfo=timezone.utc)


class PriceIndex:
    def __init__(self, rows):
        self.rows=defaultdict(list)
        self.prior_rows=defaultdict(list)
        for symbol,day,opened,closed in rows:
            self.rows[symbol].append((day,opened,closed))
            if closed is not None: self.prior_rows[symbol.upper()].append((day,closed))
        self.days={s:[r[0] for r in rs] for s,rs in self.rows.items()}
        self.prior_days={s:[r[0] for r in rs] for s,rs in self.prior_rows.items()}
        if any(len(set(days))!=len(days) for days in self.days.values()):
            raise ValueError('Duplicate price dates')
        if any(days!=sorted(days) or len(days)!=len(set(days)) for days in self.prior_days.values()):
            raise ValueError('Ambiguous case-insensitive price ordering')

    def on(self,symbol,day):
        symbol=symbol.upper(); days=self.days.get(symbol,[]); i=bisect_left(days,day)
        if i==len(days) or days[i]!=day:return None
        row=self.rows[symbol][i]
        return dict(trade_date=day,adjusted_open=row[1],adjusted_close=row[2])

    def after(self,symbol,day):
        symbol=symbol.upper();days=self.days.get(symbol,[]);i=bisect_left(days,day)
        if i==len(days):return None
        row=self.rows[symbol][i]
        # Original get_price_on_or_after converts even a NULL close to Decimal,
        # so keep that failure rather than silently skipping a row.
        return dict(trade_date=row[0],price=Decimal(row[2]))

    def entry(self,symbol,day):
        row=self.on(symbol,day)
        return dict(trade_date=day,open=row['adjusted_open'],close=row['adjusted_close']) if row else None

    def next_date(self,symbol,day):
        days=self.days.get(symbol.upper(),[]);i=bisect_left(days,day)
        return days[i] if i<len(days) and days[i]<=day+timedelta(days=event_timing.MAX_ENTRY_DELAY_DAYS) else None

    def prior(self,symbol,day,limit=61):
        symbol=symbol.upper();days=self.prior_days.get(symbol,[]);i=bisect_left(days,day)
        return [dict(trade_date=d,close=c) for d,c in self.prior_rows[symbol][max(0,i-limit):i]]


class Capture:
    """Accept ONLY the original event INSERT's parameters; no DB connection."""
    def __init__(self):self.events={}
    def cursor(self):return self
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self,statement,parameters):
        match=re.match(r'\s*INSERT INTO backtest_events\s*\((.*?)\)\s*VALUES',statement,re.S)
        if not match:raise ValueError('Unexpected operation in memory capture')
        columns=[c.strip() for c in match.group(1).split(',')]
        if len(columns)!=len(parameters):raise ValueError('Event parameter shape differs')
        row=dict(zip(columns,parameters));key=(row['security_id'],row['period_end'])
        if key in self.events:raise ValueError('Duplicate expected event key')
        self.events[key]=row


def replay(data):
    start=time.monotonic()
    prices=PriceIndex(data['prices'])
    histories=defaultdict(list)
    for fact in data['facts']:histories[fact['security_id'],fact['metric']].append(fact)
    if any(len({f['period_end'] for f in rows})!=len(rows) for rows in histories.values()):
        raise ValueError('Ambiguous metric-period ordering')
    filings={f['accession_number']:f for f in data['filings']}
    membership=defaultdict(list)
    for row in data['membership']:membership[row['security_id']].append(row)
    def member(sid,day):
        return any(r['effective_from'] is not None and r['effective_from']<=day and
            (r['effective_to'] is None or day<=r['effective_to']) for r in membership[sid])
    capture=Capture(); results=[]
    with ExitStack() as stack:
        for module in (builder,backtester,event_timing,market_context):
            stack.enter_context(patch.object(module,'get_connection',side_effect=AssertionError('DB connection forbidden in replay')))
        stack.enter_context(patch('psycopg.connect',side_effect=AssertionError('DB forbidden in replay')))
        stack.enter_context(patch('requests.sessions.Session.request',side_effect=AssertionError('Network forbidden')))
        for module,name,function in (
            (builder,'get_metric_history',lambda sid,metric: histories[sid,metric]),
            (builder,'get_filing',lambda acc:filings.get(acc)),
            (builder,'was_index_member_on_date',member),
            (event_timing,'get_next_trading_date',prices.next_date),
            (backtester,'get_price_on_date',prices.on),(backtester,'get_price_on_or_after',prices.after),
            (market_context,'get_prior_prices',prices.prior),(market_context,'get_entry_price_record',prices.entry)):
            stack.enter_context(patch.object(module,name,function))
        for i,security in enumerate(data['securities']):
            if time.monotonic()-start>120:raise ValueError('Offline replay exceeded 120-second bound')
            results.append(builder.build_security_events(capture,security))
        # Isolate FTV timing using the same metrics and unchanged live inputs.
        ftv=next(r for r in data['securities'] if r['ticker']=='FTV')
        fact=next(r for r in histories[ftv['security_id'],'revenue'] if r['period_end']==date(2026,4,3))
        timing={}
        for day in (date(2026,4,30),date(2026,5,1)):
            context=market_context.calculate_market_context('FTV',day)
            current=dict(capture.events[ftv['security_id'],fact['period_end']],**context)
            timing[str(day)]=dict(context=context,qualifies=qualifies_experimental_signal(current),
                prices={symbol:prices.prior(symbol,day,21) for symbol in ('FTV','SPY')})
    actual={(r['security_id'],r['period_end']):r for r in data['events'] if r['membership_qualified']}
    mismatches=[]
    for key,row in capture.events.items():
        existing=actual.get(key)
        if existing is None:continue
        changed={k:dict(expected=v,stored=existing.get(k)) for k,v in row.items() if existing.get(k)!=v}
        if changed:mismatches.append(dict(key=key,fields=changed))
    return dict(expected_events=len(capture.events),actual_events=len(actual),
        expected_only=sorted(set(capture.events)-set(actual)),actual_only=sorted(set(actual)-set(capture.events)),
        mismatched_events=mismatches,security_results=results,
        expected_rows=list(capture.events.values()),ftv_timing=timing,ftv_fact=fact,
        elapsed_seconds=round(time.monotonic()-start,3),compared_fields=list(next(iter(capture.events.values()))))


def run():
    manifest_path=Path('logs/research/acceptance_repair/manifest.json.gz')
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest()!=PIN:raise ValueError('Manifest hash mismatch')
    manifest=json.loads(gzip.decompress(manifest_path.read_bytes()))
    with get_connection() as conn:
        configure(conn,True)
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT current_timestamp AS snapshot,current_setting('transaction_read_only') AS read_only")
            meta=cur.fetchone()
            cur.execute('SELECT f.*,c.cik,c.ticker,c.company_name FROM filings f JOIN companies c ON c.id=f.company_id ORDER BY f.id')
            filings=cur.fetchall()
            cur.execute(f'SELECT be.*,s.ticker,{MEMBERSHIP} AS membership_qualified,be.xmin::text AS xmin FROM backtest_events be JOIN securities s ON s.id=be.security_id ORDER BY be.security_id,be.period_end')
            events=cur.fetchall()
            cur.execute("SELECT * FROM index_membership_history WHERE index_name='S&P 500' ORDER BY id")
            membership=cur.fetchall()
            cur.execute("SELECT DISTINCT s.id AS security_id,s.ticker FROM securities s JOIN index_membership_history i ON i.security_id=s.id WHERE i.index_name='S&P 500' ORDER BY s.ticker,s.id")
            securities=cur.fetchall()
            cur.execute("SELECT ff.* FROM financial_facts ff WHERE metric IN ('revenue','diluted_eps','gross_profit','operating_income') AND security_id=ANY(%s) ORDER BY security_id,metric,period_end",([s['security_id'] for s in securities],))
            facts=cur.fetchall()
            cur.execute('SELECT ff.*,c.cik,c.ticker,c.company_name,s.ticker AS security_ticker FROM financial_facts ff JOIN companies c ON c.id=ff.company_id LEFT JOIN securities s ON s.id=ff.security_id WHERE ff.created_at>%s ORDER BY ff.id',(CUTOFF,))
            new_facts=cur.fetchall()
            protected=fingerprints(cur)
            cur.execute('SELECT id,cash,prospective_cutover_at FROM paper_accounts ORDER BY id')
            paper=cur.fetchall()
            cur.execute("SELECT last_value,is_called FROM backtest_events_id_seq")
            sequence=cur.fetchone()
            cur.execute("SELECT symbol,trade_date,adjusted_open,adjusted_close,created_at,updated_at FROM daily_prices WHERE symbol IN ('ADBE','SPY') AND trade_date BETWEEN '2026-09-21' AND '2026-09-23' ORDER BY symbol,trade_date")
            adbe_prices=cur.fetchall()
        # A bounded read of cached DB price inputs, no vendor request or refresh.
        prices=[];symbols=sorted({s['ticker'] for s in securities}|{'SPY'})
        with conn.cursor(name='provenance_price_inputs') as cur:
            cur.execute('SELECT symbol,trade_date,adjusted_open,adjusted_close FROM daily_prices WHERE UPPER(symbol)=ANY(%s) ORDER BY symbol,trade_date',([s.upper() for s in symbols],))
            while batch:=cur.fetchmany(10000):
                prices.extend(batch)
                if len(prices)>1600000:raise ValueError('Price input bound exceeded')
    data=dict(metadata=meta,securities=securities,membership=membership,filings=filings,events=events,facts=facts,prices=prices,
        new_facts=new_facts,paper=paper,protected_tables=protected,sequence=sequence,adbe_prices=adbe_prices,
        filing_verification=filing_drift(filings,manifest))
    root=ROOT/'provenance_inputs.json.gz'
    with gzip.open(root,'xt') as output:json.dump(data,output,default=str,separators=(',',':'))
    result=replay(data)
    result.update(metadata=meta,input_path=str(root),input_sha256=hashlib.sha256(root.read_bytes()).hexdigest(),
        code_sha256={str(Path(m.__file__)):hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in (builder,backtester,event_timing,market_context)})
    out=ROOT/'deterministic_replay.json.gz'
    with gzip.open(out,'xt') as output:json.dump(result,output,default=str,separators=(',',':'))
    summary={k:v for k,v in result.items() if k not in ('expected_rows','security_results','ftv_timing')}
    summary.update(new_facts=new_facts,paper=paper,sequence=sequence,adbe_prices=adbe_prices,
        event_transaction_groups=dict(Counter(r['xmin'] for r in events if r['membership_qualified'])),
        event_created_groups=dict(Counter(str(r['created_at']) for r in events if r['membership_qualified'])),
        filing_counts=dict(total=len(filings),changed_manifest=len(data['filing_verification']['changed']),
            missing_manifest=len(data['filing_verification']['missing']),unchanged_categories=data['filing_verification']['unchanged_manifest_categories']))
    (ROOT/'provenance_summary.json').write_text(json.dumps(summary,default=str,indent=2))
    print(json.dumps({k:summary[k] for k in ('expected_events','actual_events','expected_only','actual_only','mismatched_events','elapsed_seconds','new_facts','event_transaction_groups','event_created_groups','filing_counts','paper')},default=str,indent=2))


if __name__=='__main__':
    try:run()
    except Exception as error:
        raise SystemExit(f'Provenance investigation failed ({type(error).__name__}); no database writes performed.') from None
