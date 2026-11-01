import unittest
import numpy as np
import tempfile
from pathlib import Path
from COMMERCIAL_DS_002B_TAXONOMY import classify, generate_seed, load_seed, normalize_code, SEED, sha256, SEED_SHA256, validate_seed

class TaxonomyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before=sha256(SEED)
        with tempfile.TemporaryDirectory() as td:
            generated=Path(td)/'seed.csv';generate_seed(output=generated)
            if sha256(generated)!=SEED_SHA256: raise AssertionError('generated projection differs from frozen seed')
        cls.seed=validate_seed()

    @classmethod
    def tearDownClass(cls):
        if sha256(SEED)!=SEED_SHA256: raise AssertionError('authoritative seed changed during tests')
    def test_unique_and_normalized(self):
        self.assertEqual(len(self.seed),len(set(self.seed)))
        self.assertTrue(all(k==normalize_code(k) for k in self.seed))
    def test_approved_codes(self):
        for code,cat in {'23444':'shipping','TEST001':'test','TEST002':'test','PADS':'merchandise','ADJUST':'manual_adjustment','ADJUST2':'manual_adjustment','POST':'shipping','DOT':'shipping','C2':'shipping','D':'discount','CRUK':'commission','B':'bad_debt','S':'sample','AMAZONFEE':'fee','BANK CHARGES':'fee'}.items():
            self.assertEqual(self.seed[code],cat)
    def test_m_context(self):
        self.assertEqual(classify({'StockCode':' M ','Quantity':2,'UnitPrice':5,'CustomerID':1,'invoice_has_merchandise':False},self.seed),'standalone_manual_billing')
        self.assertEqual(classify({'StockCode':'M','Quantity':-2,'UnitPrice':5,'CustomerID':1,'invoice_has_merchandise':False},self.seed),'standalone_manual_credit')
        self.assertEqual(classify({'StockCode':'M','Quantity':0,'UnitPrice':5,'CustomerID':1,'invoice_has_merchandise':False},self.seed),'standalone_manual_zero_value')
        self.assertEqual(classify({'StockCode':'M','Quantity':-2,'UnitPrice':5,'CustomerID':1,'invoice_has_merchandise':True},self.seed),'manual_adjustment')
        self.assertEqual(classify({'StockCode':'M','Quantity':0,'UnitPrice':5,'CustomerID':1,'invoice_has_merchandise':True},self.seed),'manual_adjustment')
    def test_unseen_fails(self):
        for code,desc in [('TEST003','This is a test product.'),('POST2','POSTAGE'),('999991','Next Day Carriage')]:
            with self.assertRaises(ValueError): classify({'StockCode':code,'Description':desc,'UnitPrice':1,'CustomerID':1},self.seed)

    def test_weak_merchandise_codes_fail_closed_on_future_exposure(self):
        for code in ('15002','20852','22126','23059','35643','35956','72038B','72732','72759','DCGS0067','DCGS0073'):
            with self.assertRaisesRegex(ValueError,'commercial exposure'):
                classify({'StockCode':code,'Description':'future line','UnitPrice':1,'Quantity':1,'CustomerID':None},self.seed)
            with self.assertRaisesRegex(ValueError,'commercial exposure'):
                classify({'StockCode':code,'Description':'future line','UnitPrice':0,'Quantity':1,'CustomerID':12345},self.seed)
    def test_u1_context_and_future_value_fails(self):
        with self.assertRaises(ValueError): classify({'StockCode':'10124C','Description':None,'UnitPrice':1,'CustomerID':1},self.seed)
        self.assertEqual(classify({'StockCode':'10124C','Description':None,'UnitPrice':0,'CustomerID':None},self.seed),'non_commercial_stock_movement')

    def test_seed_unchanged_and_corruption_detected(self):
        self.assertEqual(self.before,SEED_SHA256)
        self.assertEqual(sha256(SEED),SEED_SHA256)
        with tempfile.TemporaryDirectory() as td:
            bad=Path(td)/'corrupt.csv';text=SEED.read_text();bad.write_text(text.replace(',85123A,merchandise,',',85123A,shipping,',1))
            with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):validate_seed(bad)
        self.assertEqual(sha256(SEED),SEED_SHA256)

    def test_m_context_requires_explicit_boolean(self):
        for context in (None,'True',1):
            with self.assertRaisesRegex(ValueError,'explicit'):
                classify({'StockCode':'M','Quantity':1,'UnitPrice':1,'CustomerID':1,'invoice_has_merchandise':context},self.seed)
        self.assertEqual(classify({'StockCode':'M','Quantity':1,'UnitPrice':1,'CustomerID':1,'invoice_has_merchandise':False},self.seed),'standalone_manual_billing')
        self.assertEqual(classify({'StockCode':'M','Quantity':1,'UnitPrice':1,'CustomerID':1,'invoice_has_merchandise':np.bool_(True)},self.seed),'manual_adjustment')
        self.assertEqual(classify({'StockCode':'M','Quantity':0,'UnitPrice':5,'CustomerID':None,'invoice_has_merchandise':False},self.seed),'standalone_manual_zero_value')
        with self.assertRaisesRegex(ValueError,'Quantity and UnitPrice'):
            classify({'StockCode':'M','UnitPrice':1,'CustomerID':1,'invoice_has_merchandise':False},self.seed)

if __name__=='__main__': unittest.main()
