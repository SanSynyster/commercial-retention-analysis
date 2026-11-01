import unittest
import tempfile,csv
from decimal import Decimal
from pathlib import Path
import numpy as np, pandas as pd
from COMMERCIAL_DS_002B_INTEGRATION import build_report, EXPECTED_ROWS, EXPECTED, assert_integrity, row_customer_fingerprints, integrity_fingerprints, validate_reference_pins
from COMMERCIAL_DS_002B_TAXONOMY import classify, load_seed, INVENTORY_CONTEXT_CODES, SEED, SEED_SHA256, sha256, validate_seed
import COMMERCIAL_DS_002_ANALYSIS as audit

class CorrectedV2IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.report=build_report()

    def test_corrected_v2_rows_and_category_reconciliation(self):
        r=self.report
        self.assertEqual(r['corrected_v2_rows'],EXPECTED_ROWS)
        self.assertEqual(r['source_reconciliation']['category_rows_sum'],EXPECTED_ROWS)
        self.assertTrue(r['source_reconciliation']['rows_reconcile'])
        self.assertEqual(sum(Decimal(x['signed_amount']) for x in r['category_totals'].values()),Decimal(r['source_reconciliation']['signed_amount_all']))
        self.assertEqual(Decimal(r['source_reconciliation']['signed_amount_all']),Decimal('18909762.118'))
        self.assertEqual(Decimal(r['source_reconciliation']['identifiable_signed_amount']),Decimal('16343669.038'))
        self.assertEqual(Decimal(r['source_reconciliation']['unattributed_signed_amount']),Decimal('2566093.08'))
        self.assertEqual(r['canonical_key_coverage']['coverage_fraction'][:7],'0.93061')
        for name,expected in EXPECTED.items():
            d=r['category_totals'][name]
            actual=(d['rows'],d['positive_amount'],d['negative_amount'],d['signed_amount'],d['identifiable_amount'],d['unattributed_amount'])
            self.assertEqual(actual[0],expected[0]);self.assertEqual(tuple(map(Decimal,actual[1:])),tuple(map(Decimal,expected[1:])))
        self.assertEqual(r['seed_sha256'],SEED_SHA256)
        self.assertEqual(r['row_identity']['rows'],EXPECTED_ROWS)
        self.assertEqual(r['row_identity']['source_row_min'],0)
        self.assertEqual(r['row_identity']['source_row_max'],1067370)
        self.assertEqual(r['overlap_rows_removed'],22523)
        self.assertEqual(r['overlap_removed_raw_source_rows'],[502938,525460])
        self.assertEqual(r['customer_integrity']['identified_customers'],5942)
        self.assertEqual(r['row_identity']['sha256'],'d76696efc5d02069d1180c84286e813973f810ca8fbf2b356ebc03f45bca1a04')
        self.assertEqual(r['row_identity']['legacy_sha256'],'80a6d26ec87d2cb1d9988c4fc7f28c2b611f64491caa611405da9f7d7c184022')
        self.assertEqual(r['source_content_integrity']['sha256'],'59970949b45bf75263217525fa9f437c672d39503c7b2c605275601546299c6d')
        self.assertEqual(r['customer_integrity']['sha256'],'248f421fbcacfaf1e63b3a5a69da78ec3097ce0cfa73c50f1e6ed733e4736d51')
        self.assertEqual(r['customer_integrity']['identified_signed_amount'],'16343669.038')

    def test_no_unclassified_rows(self):
        self.assertEqual(self.report['unclassified_rows'],0)
        self.assertEqual(self.report['unclassified_commercially_relevant_rows'],0)

    def test_u1_and_five_inventory_context_codes(self):
        self.assertEqual(self.report['u1'],{'codes':351,'rows':357})
        expected={'23595':2,'35600A':1,'35605A':1,'35978':3,'84641':1}
        self.assertEqual({k:v['rows'] for k,v in self.report['inventory_adjustment_codes'].items()},expected)
        self.assertTrue(all(Decimal(v['amount'])==0 for v in self.report['inventory_adjustment_codes'].values()))
        self.assertEqual(INVENTORY_CONTEXT_CODES,set(expected))

    def test_weak_merchandise_notes_are_reported_without_remapping(self):
        expected={'15002':1,'20852':5,'22126':3,'23059':1,'35643':2,'35956':1,'72038B':1,'72732':2,'72759':2,'DCGS0067':1,'DCGS0073':1}
        weak=self.report['weak_merchandise_codes']
        self.assertEqual({k:v['rows'] for k,v in weak.items()},expected)
        self.assertTrue(all(Decimal(v['signed_amount'])==0 and v['identifiable_rows']==0 and v['positive_rows']==0 and v['negative_rows']==0 for v in weak.values()))
        self.assertEqual(sum(v['rows'] for v in weak.values()),20)
        self.assertTrue(all(v['categories']=={'merchandise':v['rows']} for v in weak.values()))
        self.assertTrue(all(load_seed()[k]=='merchandise' for k in expected))

    def test_366_admin_rows_and_merchandise_control(self):
        self.assertEqual(self.report['administrative_description_exception_rows'],366)
        seed=load_seed()
        self.assertEqual(classify({'StockCode':'PADS','Description':'PADS TO MATCH CUSHIONS','UnitPrice':0,'CustomerID':None},seed),'merchandise')
        self.assertEqual(classify({'StockCode':'35605A','Description':'damages','UnitPrice':0,'CustomerID':None},seed),'non_commercial_stock_movement')

    def test_m_standalone_embedded_and_order_independence(self):
        m=self.report['manual_invoice_context']
        self.assertEqual(m['standalone']['invoices'],755)
        self.assertEqual(m['embedded']['invoices'],535)
        cats=self.report['manual_M_categories']
        expected={
            'standalone_negative':(470,443,191,'-421770.38','-336332.43','-85437.95'),
            'standalone_positive':(330,311,109,'334379.51','146916.08','187463.43'),
            'standalone_zero':(2,2,2,'0','0','0'),
            'embedded_negative':(64,52,47,'-1168.70','-1159.37','-9.33'),
            'embedded_positive':(532,478,347,'5624.00','5250.24','373.76'),
            'embedded_zero':(5,5,5,'0','0','0')}
        for k,(rows,invoices,customers,amount,identified,unattributed) in expected.items():
            x=cats[k];self.assertEqual((x['rows'],x['invoices'],x['customers']),(rows,invoices,customers))
            self.assertEqual(tuple(map(Decimal,(x['signed_amount'],x['identifiable_amount'],x['unattributed_amount']))),tuple(map(Decimal,(amount,identified,unattributed))))
        seed=load_seed()
        rows=[{'StockCode':'M','Quantity':-1,'UnitPrice':5,'CustomerID':1,'invoice_has_merchandise':True},
              {'StockCode':'POST','UnitPrice':5,'CustomerID':1,'invoice_has_merchandise':False}]
        a={r['StockCode']:classify(r,seed) for r in rows}
        b={r['StockCode']:classify(r,seed) for r in reversed(rows)}
        self.assertEqual(a,b)
        self.assertEqual(a['M'],'manual_adjustment')
        self.assertEqual(classify({'StockCode':'M','Quantity':1,'UnitPrice':5,'CustomerID':1,'invoice_has_merchandise':False},seed),'standalone_manual_billing')
        self.assertEqual(classify({'StockCode':'M','Quantity':-1,'UnitPrice':5,'CustomerID':1,'invoice_has_merchandise':False},seed),'standalone_manual_credit')
        self.assertEqual(classify({'StockCode':'M','Quantity':0,'UnitPrice':5,'CustomerID':1,'invoice_has_merchandise':False},seed),'standalone_manual_zero_value')

    def test_unknown_described_code_still_fails(self):
        with self.assertRaises(ValueError): classify({'StockCode':'UNKNOWN-X','Description':'A plausible product','UnitPrice':1,'CustomerID':1},load_seed())

    def test_category_flip_and_category_swap_are_detected(self):
        original=SEED.read_text()
        with tempfile.TemporaryDirectory() as td:
            bad=Path(td)/'flip.csv';bad.write_text(original.replace(',85123A,merchandise,',',85123A,shipping,',1))
            self.assertEqual(load_seed(bad)['85123A'],'shipping')
            with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):build_report(bad)
            swap=Path(td)/'swap.csv';swap.write_text(original.replace(',85123A,merchandise,',',85123A,shipping,',1).replace(',POST,shipping,',',POST,merchandise,',1))
            altered=load_seed(swap);self.assertEqual(altered['85123A'],'shipping');self.assertEqual(altered['POST'],'merchandise')
            with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):build_report(swap)
        self.assertEqual(sha256(SEED),SEED_SHA256)

    def test_null_customer_forms_are_consistently_unattributed(self):
        seed=load_seed()
        for missing in (None,pd.NA,np.nan,float('nan')):
            row={'StockCode':'10124C','Description':None,'UnitPrice':0,'CustomerID':missing}
            self.assertEqual(classify(row,seed),'non_commercial_stock_movement')
        # Customer nullness does not change the approved standalone M category.
        for missing in (None,pd.NA,np.nan,float('nan')):
            self.assertEqual(classify({'StockCode':'M','Quantity':-1,'UnitPrice':1,'CustomerID':missing,'invoice_has_merchandise':False},seed),'standalone_manual_credit')
        # Literal text is evidence, not a null sentinel.
        with self.assertRaises(ValueError):classify({'StockCode':'10124C','Description':'nan','UnitPrice':0,'CustomerID':None},seed)

    def test_row_and_customer_fingerprints_detect_mutations(self):
        base=[{'source_sha256':'s','source_row_number':1,'raw_stock_code':'A','stock_code':'A','invoice':'I1','description':'A desc','country':'GB','customer_missing':False,'customer_id':'1','quantity':1,'unit_price':'10','date':'d','category':'merchandise'},
              {'source_sha256':'s','source_row_number':2,'raw_stock_code':'B','stock_code':'B','invoice':'I2','description':'B desc','country':'FR','customer_missing':False,'customer_id':'2','quantity':1,'unit_price':'10','date':'d','category':'merchandise'}]
        rh,ch,_=row_customer_fingerprints(base,2)
        assert_integrity(base,2,rh,ch)
        substitution=[dict(x) for x in base];substitution[0]['stock_code']='X'
        with self.assertRaisesRegex(AssertionError,'source-row'):assert_integrity(substitution,2,rh,ch)
        reassigned=[dict(x) for x in base];reassigned[0]['customer_id']='2'
        with self.assertRaises(AssertionError):assert_integrity(reassigned,2,rh,ch)
        deattributed=[dict(x) for x in base];deattributed[0]['customer_id']=None;deattributed[0]['customer_missing']=True
        with self.assertRaisesRegex(AssertionError,'source-row'):assert_integrity(deattributed,2,rh,ch)
        duplicate=[dict(base[0]),dict(base[0])]
        with self.assertRaisesRegex(ValueError,'duplicate source row'):row_customer_fingerprints(duplicate,2)
        # Equal-amount duplicate replacing a deleted source row preserves global
        # revenue but fails both source identity and customer allocation pins.
        deleted_duplicated=[dict(base[0]),dict(base[0])];deleted_duplicated[1]['source_row_number']=2
        with self.assertRaises(AssertionError):assert_integrity(deleted_duplicated,2,rh,ch)
        revenue_swap=[dict(x) for x in base];revenue_swap[0]['customer_id']='2';revenue_swap[1]['customer_id']='1'
        with self.assertRaises(AssertionError):assert_integrity(revenue_swap,2,rh,ch)
        country_change=[dict(x) for x in base];country_change[0]['country']='US'
        with self.assertRaises(AssertionError):assert_integrity(country_change,2,rh,ch)
        date_change=[dict(x) for x in base];date_change[0]['date']='d+1'
        with self.assertRaises(AssertionError):assert_integrity(date_change,2,rh,ch)
        source_substitution=[dict(x) for x in base];source_substitution[0]['source_row_number']=3
        with self.assertRaises(AssertionError):assert_integrity(source_substitution,2,rh,ch)
        category_change=[dict(x) for x in base];category_change[0]['category']='shipping'
        with self.assertRaises(AssertionError):assert_integrity(category_change,2,rh,ch)
        hashes,_=integrity_fingerprints(base,2)
        desc_change=[dict(x) for x in base];desc_change[0]['description']='different'
        changed,_=integrity_fingerprints(desc_change,2)
        self.assertEqual(hashes['row'],changed['row'])
        self.assertNotEqual(hashes['source_content'],changed['source_content'])
        self.assertEqual(integrity_fingerprints(list(reversed(base)),2)[0],hashes)

    def test_ingestion_source_identity_survives_filter_and_sort(self):
        frame=pd.DataFrame({'StockCode':['A','B','C'],'Quantity':[1,2,3]})
        identified=audit.assign_source_row_numbers(frame)
        self.assertEqual(identified.source_row_number.tolist(),[0,1,2])
        sliced=identified.loc[[0,2]].sort_values('Quantity',ascending=False)
        self.assertEqual(sliced.source_row_number.tolist(),[2,0])
        with self.assertRaisesRegex(ValueError,'already exists'):
            audit.assign_source_row_numbers(identified)

    def test_description_change_that_changes_context_is_fingerprinted(self):
        seed=load_seed()
        before={'StockCode':'15058A','Description':'wet/rusty','UnitPrice':0,'CustomerID':None}
        after={**before,'Description':'plain product description'}
        self.assertEqual(classify(before,seed),'non_commercial_stock_movement')
        self.assertEqual(classify(after,seed),'merchandise')

    def test_runtime_frozen_fingerprint_check_rejects_mutation(self):
        altered=dict(self.report);altered['row_identity']=dict(self.report['row_identity']);altered['row_identity']['sha256']='0'*64
        with self.assertRaisesRegex(AssertionError,'row_fingerprint'):
            validate_reference_pins(altered)

if __name__=='__main__': unittest.main()
