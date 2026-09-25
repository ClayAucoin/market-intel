"""Offline source-representation investigation; no production mutations."""
from datetime import datetime
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.backtesting import investigate_acceptance_sources as study


class AcceptanceSourceTests(unittest.TestCase):
    def test_explicit_z_is_not_silently_reinterpreted(self):
        result=study.compare('2021-02-23T16:19:41.000Z','20210223161941')
        self.assertEqual(result['submissions_parsed_utc'],'2021-02-23T16:19:41+00:00')
        self.assertEqual(result['header_parsed_utc'],'2021-02-23T21:19:41+00:00')
        self.assertEqual(result['header_minus_submissions_seconds'],18000)
        self.assertEqual(result['classification'],'Z_REPEATS_EASTERN_WALL_CLOCK')
        self.assertFalse(result['is_dst'])

    def test_summer_offset(self):
        result=study.compare('2021-05-04T16:34:25.000Z','20210504163425')
        self.assertTrue(result['is_dst'])
        self.assertTrue(result['exactly_eastern_offset_difference'])
        self.assertEqual(result['header_minus_submissions_seconds'],14400)

    def test_genuine_utc_and_explicit_eastern_agree(self):
        for source in ('2021-05-04T20:34:25.000Z','2021-05-04T16:34:25-04:00'):
            result=study.compare(source,'20210504163425')
            self.assertEqual(result['classification'],'SAME_INSTANT')
            self.assertEqual(result['header_minus_submissions_seconds'],0)

    def test_other_difference_is_not_offset_evidence(self):
        result=study.compare('2021-05-04T15:34:25.000Z','20210504163425')
        self.assertEqual(result['classification'],'OTHER_DISAGREEMENT')
        self.assertFalse(result['same_wall_clock'])

    def test_missing_naive_and_dst_ambiguous_rejected(self):
        for source in (None,'2021-01-01T12:00:00'):
            with self.assertRaises(ValueError):study.compare(source,'20210101120000')
        with self.assertRaises(ValueError):study.compare('2021-11-07T05:30:00Z','20211107013000')

    def test_header_identity_and_exact_value(self):
        raw='<pre>ACCESSION NUMBER: 0000000001-20-000001\n&lt;ACCEPTANCE-DATETIME&gt;20200102120000\nCONFORMED SUBMISSION TYPE: 10-K\nFILED AS OF DATE: 20200102\nFILER:\nCENTRAL INDEX KEY: 0000000001\n</pre>'
        fields=study.header_fields(raw,'0000000001','0000000001-20-000001')
        self.assertEqual(fields['raw_acceptance'],'20200102120000')
        with self.assertRaises(ValueError):study.header_fields(raw,'0000000002','0000000001-20-000001')
        with self.assertRaises(ValueError):study.header_fields(raw,'0000000001','0000000001-20-000002')

    def test_duplicate_submission_conflict_rejected(self):
        data=dict(accessionNumber=['a','a'],acceptanceDateTime=['2020-01-01T00:00:00Z','2020-01-02T00:00:00Z'],form=['10-K']*2,filingDate=['2020-01-01']*2)
        with self.assertRaises(ValueError):study.row_for(data,'a')
        self.assertIsNone(study.row_for(data,'absent'))

    def test_request_cap_prevents_calls(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(study,'ROOT',Path(tmp)),patch('requests.get') as get:
            item=dict(kind='header',cik='0000000001',accession='0000000001-20-000001')
            item['url']=study.canonical_url(item)
            study.save(Path(tmp)/'plan.json',[item]);study.save(Path(tmp)/'requests.json',[dict(url='other',outcome='IN_FLIGHT')]*20)
            with self.assertRaises(ValueError):study.fetch()
            get.assert_not_called()

    def test_failed_attempt_is_persisted_before_call(self):
        import requests
        with tempfile.TemporaryDirectory() as tmp,patch.object(study,'ROOT',Path(tmp)),patch('src.sec.sec_http._pace'):
            item=dict(kind='header',cik='0000000001',accession='0000000001-20-000001');item['url']=study.canonical_url(item)
            study.save(Path(tmp)/'plan.json',[item])
            def failure(*args,**kwargs):
                self.assertEqual(study.read(Path(tmp)/'requests.json')[0]['outcome'],'IN_FLIGHT')
                self.assertFalse(kwargs['allow_redirects'])
                raise requests.ConnectionError()
            with patch('requests.get',side_effect=failure):
                with self.assertRaises(RuntimeError):study.fetch()
            self.assertEqual(study.read(Path(tmp)/'requests.json')[0]['outcome'],'NETWORK_FAILURE')

    def test_original_raw_former_sources_match_all_22(self):
        saved=study.read(study.ROOT/'inputs.json')
        for row in saved['comparisons']:
            if row['label'] not in ('ATVI','TWTR'):continue
            for source in row['submissions_sources']:
                value=study.checked_fixture(Path(source['path']),'raw_json')
                actual=study.row_for(json.loads(value['raw_json']),row['accession'])
                self.assertEqual(actual['acceptanceDateTime'],row['submissions_raw'])

    def test_complete_offline_replay(self):
        expected=(study.ROOT/'results.json').read_bytes()
        with patch('requests.sessions.Session.request',side_effect=AssertionError('Network forbidden')),patch('psycopg.connect',side_effect=AssertionError('DB forbidden')),patch('dotenv.load_dotenv'),contextlib.redirect_stdout(io.StringIO()):
            study.analyze()
        self.assertEqual((study.ROOT/'results.json').read_bytes(),expected)
        r=json.loads(expected)
        self.assertEqual(r['summary']['former_patterns'],{'Z_REPEATS_EASTERN_WALL_CLOCK':22})
        self.assertEqual(r['summary']['former_repair_intersection'],{'ABSENT':22})
        self.assertEqual(r['summary']['control_patterns'],{'SAME_INSTANT':103})
        self.assertTrue(all(p['repaired_minus_header_seconds']==0 for p in r['header_probes'] if p['manifest_row']['category']=='safely_correctable'))
        changed=[e for e in r['event_impact'] if e['candidate_changed']]
        self.assertEqual(len(changed),1)
        self.assertEqual(changed[0]['reference_basis'],'INDEPENDENT_HEADER')
        self.assertFalse(changed[0]['exact_signal'])
        self.assertTrue(all(e['old_source_wall_equals_reference_eastern'] and e['source_delta_equals_eastern_offset'] for e in r['exceptional_population']))


if __name__=='__main__':unittest.main()
