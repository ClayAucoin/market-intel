"""Offline fixtures only; never contact SEC or the database."""
import unittest
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

with patch('dotenv.load_dotenv'):
    from src.backtesting.sec_sic_pilot import parse_header, lookup, retrieve

HEADER='''<html><pre>&lt;ACCEPTANCE-DATETIME&gt;20200806160000
ACCESSION NUMBER: 0000000001-20-000001
FILER:
 COMPANY DATA:
 CENTRAL INDEX KEY: 0000000001
 STANDARD INDUSTRIAL CLASSIFICATION: SOFTWARE [7372]
FILER:
 CENTRAL INDEX KEY: 0000000002
 STANDARD INDUSTRIAL CLASSIFICATION: ELECTRIC SERVICES [4911]
</pre></html>'''


class PilotTests(unittest.TestCase):
    def test_header_issuer_specific(self):
        result=parse_header(HEADER,'0000000001','0000000001-20-000001')
        self.assertEqual(result['sic'],'7372')
        self.assertEqual(result['accepted_at'],'2020-08-06T16:00:00-04:00')

    def test_wrong_issuer_fails(self):
        with self.assertRaises(ValueError): parse_header(HEADER,'3','0000000001-20-000001')

    def test_wrong_accession_fails(self):
        with self.assertRaises(ValueError): parse_header(HEADER,'1','wrong')

    def test_missing_timestamp_fails(self):
        with self.assertRaises(ValueError): parse_header(HEADER.replace('20200806160000',''),'1','0000000001-20-000001')

    def test_conflicting_same_issuer_fails(self):
        with self.assertRaises(ValueError): parse_header(HEADER.replace('0000000002','0000000001'),'1','0000000001-20-000001')

    def obs(self,date,code='7372',cik='1'):
        return dict(cik=cik,sic=code,description='fixture',accession=date,accepted_at=date)

    def test_no_backdating(self):
        result=lookup([self.obs('2020-08-07T14:00:00+00:00')],'1',datetime(2020,8,7,13,30,tzinfo=timezone.utc))
        self.assertEqual(result['status'],'UNKNOWN')

    def test_latest_supported_only(self):
        obs=[self.obs('2020-08-05T10:00:00+00:00'),self.obs('2020-08-06T10:00:00+00:00','4911'),self.obs('2020-08-08T10:00:00+00:00','9999')]
        self.assertEqual(lookup(obs,'1',datetime(2020,8,7,tzinfo=timezone.utc))['sic'],'4911')

    def test_exact_decision_time_excluded(self):
        self.assertEqual(lookup([self.obs('2020-08-07T00:00:00+00:00')],'1',datetime(2020,8,7,tzinfo=timezone.utc))['status'],'UNKNOWN')

    def test_conflicting_latest_ambiguous(self):
        obs=[self.obs('2020-08-06T10:00:00+00:00'),self.obs('2020-08-06T10:00:00+00:00','4911')]
        self.assertEqual(lookup(obs,'1',datetime(2020,8,7,tzinfo=timezone.utc))['status'],'AMBIGUOUS')

    def test_other_issuer_never_used(self):
        self.assertEqual(lookup([self.obs('2020-08-06T10:00:00+00:00',cik='2')],'1',datetime(2020,8,7,tzinfo=timezone.utc))['status'],'UNKNOWN')

    def test_default_and_exhausted_budget_do_not_fetch(self):
        with tempfile.TemporaryDirectory() as tmp, patch('src.backtesting.sec_sic_pilot.ROOT',Path(tmp)), patch('src.backtesting.sec_sic_pilot.requests.get') as get:
            self.assertEqual(retrieve('1','fixture',False,[40]),(None,False))
            self.assertEqual(retrieve('1','fixture',True,[0]),(None,False))
            get.assert_not_called()

    def test_saved_evidence_replays_offline(self):
        root=Path(__file__).resolve().parents[1]/'logs/research/sec_sic_pilot'
        data=json.loads((root/'pilot_2026-09-23_052233.json').read_text())
        with patch('src.backtesting.sec_sic_pilot.ROOT',root), patch('src.backtesting.sec_sic_pilot.requests.get') as get:
            for obs in data['observations']:
                cached,used=retrieve(obs['cik'],obs['accession'],True,[40])
                self.assertFalse(used)
                self.assertEqual(hashlib.sha256(cached['raw_header'].encode()).hexdigest(),obs['sha256'])
                parsed=parse_header(cached['raw_header'],obs['cik'],obs['accession'])
                for key,value in parsed.items(): self.assertEqual(value,obs[key])
            for target in data['targets']:
                self.assertEqual(lookup(data['observations'],target['cik'],datetime.fromisoformat(target['decision_at'])),target['lookup'])
            get.assert_not_called()


if __name__=='__main__': unittest.main()
