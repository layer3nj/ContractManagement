# Contract Management App

A lightweight Flask app to manage:

- Vendors
- Applications/services you pay for
- Invoice entry + CSV invoice import
- Expense monitoring (monthly, by vendor, allocated by client)
- Linking services to Autotask clients for cost allocation

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

## CSV import format

Upload a CSV on the **Invoices** page with columns:

- `vendor_name`
- `service_name` (optional)
- `invoice_number`
- `invoice_date` (`YYYY-MM-DD`)
- `amount`
- `description`
