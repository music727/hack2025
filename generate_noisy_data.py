import pandas as pd
import numpy as np
import random
from faker import Faker

fake = Faker()
vendors = ['Contoso Ltd', 'Fabrikam Inc', 'Northwind Traders', 'Adventure Works', 'Proseware']
currencies = ['USD', 'EUR', 'GBP']

def random_amount():
    amt = round(random.uniform(500, 5000), 2)
    # Add noise: sometimes as string, sometimes with comma, sometimes with space
    if random.random() < 0.1:
        return f"{amt:,.2f}"
    elif random.random() < 0.1:
        return f" {amt} "
    else:
        return amt

def random_date():
    d = fake.date_between(start_date='-2y', end_date='today')
    # Add noise: different formats
    if random.random() < 0.2:
        return d.strftime('%d-%m-%Y')
    elif random.random() < 0.2:
        return d.strftime('%Y/%m/%d')
    else:
        return d.strftime('%Y-%m-%d')

def maybe_missing(val):
    if random.random() < 0.03:
        return ''
    return val

def maybe_typo(val):
    if isinstance(val, str) and random.random() < 0.05:
        idx = random.randint(0, len(val)-1)
        return val[:idx] + random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ') + val[idx+1:]
    return val

def maybe_case(val):
    if isinstance(val, str) and random.random() < 0.05:
        return val.lower()
    return val

def maybe_space(val):
    if isinstance(val, str) and random.random() < 0.05:
        return f" {val} "
    return val

def add_noise(val):
    val = maybe_typo(val)
    val = maybe_case(val)
    val = maybe_space(val)
    val = maybe_missing(val)
    return val

# Generate invoices
invoice_rows = []
for i in range(1, 2001):
    inv_num = f"INV-{1000+i}"
    order_id = f"PO-{i:04d}"
    vendor = random.choice(vendors)
    amount = random_amount()
    currency = random.choice(currencies)
    date = random_date()
    row = [
        add_noise(inv_num),
        add_noise(order_id),
        add_noise(vendor),
        add_noise(amount),
        add_noise(currency),
        add_noise(date)
    ]
    invoice_rows.append(row)
    # Add duplicate row sometimes
    if random.random() < 0.01:
        invoice_rows.append(row)

invoices_df = pd.DataFrame(invoice_rows, columns=['InvoiceNumber','OrderID','Vendor','Amount','Currency','Date'])
invoices_df.to_csv('invoices_large_noisy.csv', index=False)

# Generate payments (some overlap, some not)
payment_rows = []
for i in range(1, 2001):
    pay_num = f"PAY-{2000+i}"
    # 90% chance to match an invoice order, 10% random
    if random.random() < 0.9:
        order_id = f"PO-{i:04d}"
    else:
        order_id = f"PO-{random.randint(2001, 3000):04d}"
    vendor = random.choice(vendors)
    amount = random_amount()
    currency = random.choice(currencies)
    date = random_date()
    row = [
        add_noise(pay_num),
        add_noise(order_id),
        add_noise(vendor),
        add_noise(amount),
        add_noise(currency),
        add_noise(date)
    ]
    payment_rows.append(row)
    # Add duplicate row sometimes
    if random.random() < 0.01:
        payment_rows.append(row)

payments_df = pd.DataFrame(payment_rows, columns=['PaymentNumber','OrderID','Vendor','Amount','Currency','Date'])
payments_df.to_csv('payments_large_noisy.csv', index=False)

print("Generated invoices_large_noisy.csv and payments_large_noisy.csv with 2000+ noisy records each.")