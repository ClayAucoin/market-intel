"""Offline Stage 3 form eligibility, accounting, identity and complete replay."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

with patch('dotenv.load_dotenv'):
    from src.backtesting import sic_stage3 as study


def header(role='FILER', cik='0000000001', sic='1234', form='8-K'):
    return f'''<pre>ACCESSION NUMBER: 0000000001-20-000001
ACCEPTANCE-DATETIME: 20200102120000
CONFORMED SUBMISSION TYPE: {form}
FILED AS OF DATE: 20200102
{role}:
COMPANY CONFORMED NAME: EXAMPLE
CENTRAL INDEX KEY: {cik}
STANDARD INDUSTRIAL CLASSIFICATION: EXAMPLE [{sic}]
</pre>'''


class Stage3Tests(unittest.TestCase):
    def test_periodic_families(self):
        for f in ('10-K','10-K/A','10-KT','10-Q','10-Q/A','10-QT/A'):
            self.assertTrue(study.periodic(f))
        for f in ('8-K','4','10-K405','NT 10-K','DEF 14A'):
            self.assertFalse(study.periodic(f))

    def test_matching_filer_required(self):
        o=study.parse_observation(header(),'0000000001','0000000001-20-000001')
        self.assertEqual((o['form'],o['sic'],o['role']),('8-K','1234','FILER'))
        for role in ('ISSUER','SUBJECT COMPANY','REPORTING-OWNER'):
            with self.assertRaises(ValueError):
                study.parse_observation(header(role),'0000000001','0000000001-20-000001')
        with self.assertRaises(ValueError):
            study.parse_observation(header(cik='0000000002'),'0000000001','0000000001-20-000001')

    def test_cofiler_cannot_supply_target_sic(self):
        raw=header(cik='0000000002').replace('</pre>','')+'FILER:\nCENTRAL INDEX KEY: 0000000001\n</pre>'
        with self.assertRaises(ValueError):study.parse_observation(raw,'0000000001','0000000001-20-000001')

    def test_conflicting_blocks_rejected(self):
        raw=header().replace('</pre>','')+header(sic='5678')
        with self.assertRaises(ValueError):study.parse_observation(raw,'0000000001','0000000001-20-000001')

    def test_identity_preserves_class_context_no_intervals(self):
        raw='''<html><xbrli:context id="A"><xbrldi:explicitMember>ClassA</xbrldi:explicitMember></xbrli:context>
        <ix:nonNumeric name="dei:TradingSymbol" contextRef="A">AAA</ix:nonNumeric>
        <ix:nonNumeric name="dei:TradingSymbol" contextRef="C">CCC</ix:nonNumeric></html>'''
        result=study.body_identity(raw)
        self.assertEqual([f['value'] for f in result['facts']],['AAA','CCC'])
        self.assertEqual(result['contexts']['A'],'ClassA')
        self.assertFalse(result['interval_proven'])

    def setup_fetch(self, tmp):
        item=dict(kind='header',cik='0000000001',accession='0000000001-20-000001')
        item['url']=study.canonical_url(item)
        study.atomic_json(Path(tmp)/'plan.json',[item])
        return item

    def test_cap_denial_and_crashed_attempts_block_network(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(study,'ROOT',Path(tmp)), patch.object(study.requests,'get') as get:
            self.setup_fetch(tmp)
            for ledger in ([dict(url='x',status=403)], [dict(url='x',outcome='IN_FLIGHT')]*120):
                study.atomic_json(Path(tmp)/'requests.json',ledger)
                with self.assertRaises(ValueError):study.fetch()
            get.assert_not_called()

    def test_failure_persisted_before_network_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(study,'ROOT',Path(tmp)), patch.object(study,'_pace'):
            self.setup_fetch(tmp)
            def fail(*args,**kwargs):
                self.assertEqual(study.read(Path(tmp)/'requests.json')[0]['outcome'],'IN_FLIGHT')
                self.assertFalse(kwargs['allow_redirects'])
                raise study.requests.ConnectionError()
            with patch.object(study.requests,'get',side_effect=fail):
                with self.assertRaises(RuntimeError):study.fetch()
            ledger=study.read(Path(tmp)/'requests.json')
            self.assertEqual(len(ledger),1)
            self.assertEqual(ledger[0]['outcome'],'NETWORK_FAILURE')

    def test_reused_success_costs_no_request(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(study,'ROOT',Path(tmp)), patch.object(study.requests,'get') as get:
            item=self.setup_fetch(tmp);study.atomic_json(study.fixture(item),{'fixture':True})
            study.fetch();get.assert_not_called()

    def test_urls_cannot_escape_or_redirect(self):
        item=dict(kind='body',cik='0000000001',accession='0000000001-20-000001',document='../bad.htm')
        with self.assertRaises(ValueError):study.canonical_url(item)

    def test_catalog_clock_conflict_retained_without_reinterpretation(self):
        obs=dict(accession='example',accepted_at='2021-02-23T16:19:41-05:00',form='10-K')
        row=dict(acceptanceDateTime='2021-02-23T16:19:41.000Z',form='10-K')
        self.assertEqual(study.catalog_discrepancy(obs,row)['header_minus_catalog_seconds'],18000)
        self.assertEqual(row['acceptanceDateTime'],'2021-02-23T16:19:41.000Z')
        row['acceptanceDateTime']='2021-02-23T21:19:41.000Z'
        self.assertIsNone(study.catalog_discrepancy(obs,row))

    def test_full_offline_replay(self):
        if not (study.ROOT/'results.json').exists(): self.skipTest('Study evidence not yet finalized')
        before=(study.ROOT/'results.json').read_bytes()
        with patch.object(study.requests,'get',side_effect=AssertionError('Network forbidden')):
            study.analyze()
        self.assertEqual(before,(study.ROOT/'results.json').read_bytes())
        saved=json.loads(before)
        self.assertEqual(len(saved['windows']),10)
        self.assertLessEqual(saved['requests']['attempted'],120)
        self.assertTrue(all(not w['missing_periodic'] for w in saved['windows']))


if __name__=='__main__':unittest.main()
