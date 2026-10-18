import json
import unittest
from copy import deepcopy
from src.isl_v2.autonomous_agent import run_cycle, evaluate_hypothesis


def obs(code, day, available, price, revision=1, interval='1mo', src='wb_pink_monthly'):
    return {'instrument_code':code,'source_code':src,'interval_code':interval,'observed_for':day,
            'price_value':str(price),'value_concept':'MONTHLY_AVERAGE','revision_no':revision,
            'available_at':available,'document':{'canonical_url':'https://example.org/report.pdf',
            'sha256_hex':f'{revision:064x}','published_at':available,
            'publication_precision':'EXACT'}}

class AgentTests(unittest.TestCase):
    def job(self):
        return {'run_key':'agent-test-2026-10','as_of':'2026-10-17T00:00:00Z',
                'code_version':'2.0.0-rc1','observations':[], 'requirements':{}}
    def test_no_prices_stays_in_cash(self):
        r=run_cycle(self.job())
        self.assertEqual([d['decision_type'] for d in r['paper_decisions']], ['HOLD_CASH']*3)
        self.assertEqual(r['paper_fills_created'],0)
        self.assertTrue(r['no_live_execution'])
    def test_reproducible(self):
        a=run_cycle(self.job());b=run_cycle(self.job());self.assertEqual(a,b)
    def test_cannot_use_later_published_reference_price(self):
        d=self.job();d['observations']=[obs('COPPER_WB_USD_T','2026-09-30T00:00:00Z',
                               '2026-10-18T00:00:00Z',14474)]
        self.assertEqual(run_cycle(d)['observations_available'],0)
    def test_monthly_commodity_average_cannot_authorize_paper_fill(self):
        d=self.job();d['observations']=[obs('EQUITY_TR_PLN','2026-06-30T00:00:00Z','2026-07-02T00:00:00Z',100),
                         obs('EQUITY_TR_PLN','2026-07-31T00:00:00Z','2026-08-02T00:00:00Z',105),
                         obs('EQUITY_TR_PLN','2026-08-31T00:00:00Z','2026-09-02T00:00:00Z',106),
                         obs('EQUITY_TR_PLN','2026-09-30T00:00:00Z','2026-10-02T00:00:00Z',108)]
        d['requirements']={'EQUITY_TR_PLN':{'basis':'MONTHLY_AVERAGE','currency':'PLN'}}
        r=run_cycle(d)
        self.assertEqual(r['paper_decisions'][0]['decision_type'],'HOLD_CASH')
        self.assertEqual(r['paper_fills_created'],0)
    def test_hypothesis_is_only_research(self):
        d=self.job()
        for month in range(1,14):
            y=2025+(month-1)//12;mo=(month-1)%12+1
            day=f'{y}-{mo:02d}-01T00:00:00Z'
            # Sample fully published monthly-like historical data.
            d['observations'].append(obs('COPPER_WB_USD_T',day,f'{y}-{mo:02d}-10T00:00:00Z',100+month))
        a=run_cycle(d)
        self.assertEqual(len(a['hypotheses']),1)
        self.assertEqual(a['hypotheses'][0]['status'],'RESEARCH_ONLY_UNVALIDATED')
        self.assertEqual(a['paper_fills_created'],0)
    def test_evaluation_waits_for_publication(self):
        d=self.job()
        h={'instrument_code':'COPPER_WB_USD_T','observation_date':'2026-08-31T00:00:00Z',
           'hypothesis_key':'abc','direction':'UP','reference_value':'120'}
        rows=[obs('COPPER_WB_USD_T','2026-09-30T00:00:00Z','2026-10-18T00:00:00Z',125)]
        self.assertEqual(evaluate_hypothesis(h,rows,'2026-10-17T00:00:00Z')['status'],'PENDING')
        self.assertTrue(evaluate_hypothesis(h,rows,'2026-10-19T00:00:00Z')['direction_correct'])
    def test_future_revision_does_not_change_prior_cycle(self):
        d=self.job()
        d['observations']=[obs('COPPER_WB_USD_T','2026-09-30T00:00:00Z','2026-10-01T00:00:00Z',100)]
        before=run_cycle(d)
        d['observations'].append(obs('COPPER_WB_USD_T','2026-09-30T00:00:00Z','2026-10-20T00:00:00Z',110,2))
        after=run_cycle(d)
        self.assertEqual(before['observations_available'],after['observations_available'])
        self.assertEqual(before['paper_decisions'],after['paper_decisions'])

if __name__=='__main__': unittest.main()
