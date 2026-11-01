"""Test-only oracle for the written C-1/O-9 purchase-occasion contract.

This is deliberately not a production occasion builder or retention analysis.
"""
from decimal import Decimal, InvalidOperation
from datetime import date, datetime
import math
import unittest

MERCH="merchandise"
MANUAL={"standalone_manual_billing","standalone_manual_credit","standalone_manual_zero_value","manual_adjustment"}
OTHER={"shipping","fee","commission","discount","bad_debt","sample","gift_voucher","test","non_commercial_stock_movement"}

def missing(x):
    if x is None or type(x).__name__=="NAType": return True
    if isinstance(x,str): return False
    try: return bool(math.isnan(x))
    except (TypeError,ValueError): return False

def eligible_line(row):
    try:
        q=Decimal(str(row["Quantity"]));p=Decimal(str(row["UnitPrice"]))
    except (KeyError,InvalidOperation,ValueError,TypeError): return False
    customer=row.get("CustomerID")
    if missing(customer): return False
    try:
        c=Decimal(str(customer))
        if not c.is_finite() or c!=c.to_integral_value(): return False
    except (InvalidOperation,ValueError,TypeError): return False
    invoice=row.get("InvoiceNo");transaction_date=row.get("InvoiceDate")
    try:
        if isinstance(transaction_date,(date,datetime)):
            valid_date=True
        elif isinstance(transaction_date,str):
            datetime.fromisoformat(transaction_date);valid_date=True
        else:
            valid_date=False
    except ValueError:
        valid_date=False
    return (row.get("category")==MERCH and q.is_finite() and p.is_finite() and q>0 and p>0
            and isinstance(invoice,str) and invoice!="" and not invoice.startswith("C") and valid_date)

def contract_occasion_rows(rows):
    """Test-only customer×invoice reducer; returns eligible row references."""
    groups={};invoice_customers={};invoice_dates={}
    for row in rows:
        if eligible_line(row):
            customer=str(int(Decimal(str(row['CustomerID']))));invoice=row['InvoiceNo']
            invoice_customers.setdefault(invoice,set()).add(customer)
            invoice_dates.setdefault(invoice,set()).add(str(row['InvoiceDate'])[:10])
            groups.setdefault((customer,invoice),[]).append(row)
    if any(len(customers)>1 for customers in invoice_customers.values()):
        raise ValueError('invoice maps to multiple customers')
    if any(len(dates)>1 for dates in invoice_dates.values()):
        raise ValueError('invoice has inconsistent calendar dates')
    return groups

class PurchaseOccasionContractTests(unittest.TestCase):
    def row(self,**kw):
        d={'StockCode':'A','InvoiceNo':'500001','InvoiceDate':'2011-01-01 10:00:00','CustomerID':12345,'Quantity':1,'UnitPrice':'2.50','category':'merchandise','source_row_number':10};d.update(kw);return d

    def test_strict_merchandise_line_eligibility(self):
        self.assertTrue(eligible_line(self.row()))
        for cat in MANUAL|OTHER:
            self.assertFalse(eligible_line(self.row(category=cat)),cat)
        for change in ({'Quantity':0},{'Quantity':-1},{'UnitPrice':0},{'UnitPrice':'-0.01'},
                       {'InvoiceNo':'C500001'},{'CustomerID':None},{'InvoiceNo':''},{'InvoiceDate':None},{'InvoiceDate':'not-a-date'}):
            self.assertFalse(eligible_line(self.row(**change)),change)

    def test_decimal_and_customer_validation(self):
        self.assertTrue(eligible_line(self.row(UnitPrice='0.001')))
        for cid in (float('nan'),'123.5','customer',None): self.assertFalse(eligible_line(self.row(CustomerID=cid)))

    def test_grouping_is_customer_invoice_and_keeps_lineage(self):
        rows=[self.row(source_row_number=10),self.row(source_row_number=11),self.row(InvoiceNo='500002',source_row_number=12),self.row(InvoiceNo='500003',CustomerID=67890,source_row_number=13)]
        groups=contract_occasion_rows(rows)
        self.assertEqual(set(groups),{('12345','500001'),('12345','500002'),('67890','500003')})
        self.assertEqual([r['source_row_number'] for r in groups[('12345','500001')]],[10,11])

    def test_primary_later_day_and_invoice_sensitivity(self):
        dates=[('500001','2020-01-01'),('500002','2020-01-01'),('500003','2020-01-03')]
        ordered=sorted(dates,key=lambda x:(x[1],x[0]))
        first_day=ordered[0][1]
        primary_second=next((x for x in ordered if x[1]>first_day),None)
        self.assertEqual(primary_second,('500003','2020-01-03'))
        self.assertEqual(ordered[1],('500002','2020-01-01')) # same-day invoice sensitivity

    def test_invoice_customer_and_date_consistency_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'multiple customers'):
            contract_occasion_rows([self.row(CustomerID=12345),self.row(CustomerID=67890,source_row_number=11)])
        with self.assertRaisesRegex(ValueError,'inconsistent calendar dates'):
            contract_occasion_rows([self.row(),self.row(InvoiceDate='2020-01-02',source_row_number=11)])

if __name__=='__main__': unittest.main()
