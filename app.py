from __future__ import annotations

import csv
import io
import os
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from flask import Flask, flash, g, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).parent
DATABASE_PATH = BASE_DIR / "contract_management.db"

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_: Any) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = sqlite3.connect(DATABASE_PATH)
    with closing(db):
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS vendors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                website TEXT,
                contact_name TEXT,
                contact_email TEXT,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor_id INTEGER NOT NULL,
                contract_name TEXT NOT NULL,
                contract_number TEXT,
                start_date TEXT NOT NULL,
                end_date TEXT,
                auto_renew INTEGER NOT NULL DEFAULT 0,
                monthly_cost REAL NOT NULL DEFAULT 0,
                payment_terms TEXT,
                notes TEXT,
                FOREIGN KEY(vendor_id) REFERENCES vendors(id)
            );

            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor_id INTEGER NOT NULL,
                contract_id INTEGER,
                name TEXT NOT NULL,
                category TEXT,
                recurring_cost REAL DEFAULT 0,
                billing_cycle TEXT,
                FOREIGN KEY(vendor_id) REFERENCES vendors(id),
                FOREIGN KEY(contract_id) REFERENCES contracts(id)
            );

            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor_id INTEGER NOT NULL,
                service_id INTEGER,
                invoice_number TEXT,
                invoice_date TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT,
                FOREIGN KEY(vendor_id) REFERENCES vendors(id),
                FOREIGN KEY(service_id) REFERENCES services(id)
            );

            CREATE TABLE IF NOT EXISTS autotask_clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                account_code TEXT,
                monthly_revenue REAL DEFAULT 0,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS service_client_map (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_id INTEGER NOT NULL,
                client_id INTEGER NOT NULL,
                allocation_percent REAL NOT NULL DEFAULT 100,
                UNIQUE(service_id, client_id),
                FOREIGN KEY(service_id) REFERENCES services(id),
                FOREIGN KEY(client_id) REFERENCES autotask_clients(id)
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                vendor_id INTEGER,
                expense_date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT,
                description TEXT,
                FOREIGN KEY(client_id) REFERENCES autotask_clients(id),
                FOREIGN KEY(vendor_id) REFERENCES vendors(id)
            );
            """
        )
        # Migrate existing DB: add new columns if they don't exist
        for sql in [
            "ALTER TABLE vendors ADD COLUMN website TEXT",
            "ALTER TABLE vendors ADD COLUMN contact_name TEXT",
            "ALTER TABLE vendors ADD COLUMN contact_email TEXT",
            "ALTER TABLE services ADD COLUMN contract_id INTEGER",
            "ALTER TABLE autotask_clients ADD COLUMN monthly_revenue REAL DEFAULT 0",
            "ALTER TABLE autotask_clients ADD COLUMN notes TEXT",
        ]:
            try:
                db.execute(sql)
            except sqlite3.OperationalError:
                pass  # column already exists
        db.commit()


# ─── helpers ────────────────────────────────────────────────────────────────

def contract_status(end_date_str: str | None, auto_renew: int) -> str:
    """Return 'active', 'expiring', 'expired', or 'ongoing' (no end date)."""
    if not end_date_str:
        return "ongoing"
    try:
        end = date.fromisoformat(end_date_str)
    except ValueError:
        return "unknown"
    today = date.today()
    if end < today:
        return "expired"
    if end <= today + timedelta(days=60):
        return "expiring"
    return "active"


# ─── dashboard ──────────────────────────────────────────────────────────────

@app.route("/")
def dashboard() -> str:
    db = get_db()
    totals = {
        "vendors": db.execute("SELECT COUNT(*) AS c FROM vendors").fetchone()["c"],
        "contracts": db.execute("SELECT COUNT(*) AS c FROM contracts").fetchone()["c"],
        "invoices": db.execute("SELECT COUNT(*) AS c FROM invoices").fetchone()["c"],
        "clients": db.execute("SELECT COUNT(*) AS c FROM autotask_clients").fetchone()["c"],
    }

    monthly_spend = db.execute(
        """
        SELECT substr(invoice_date, 1, 7) AS month, ROUND(SUM(amount), 2) AS total
        FROM invoices
        GROUP BY month
        ORDER BY month DESC
        LIMIT 6
        """
    ).fetchall()

    spend_by_vendor = db.execute(
        """
        SELECT v.name, ROUND(SUM(i.amount), 2) AS total
        FROM invoices i
        JOIN vendors v ON v.id = i.vendor_id
        GROUP BY v.id
        ORDER BY total DESC
        LIMIT 10
        """
    ).fetchall()

    spend_by_client = db.execute(
        """
        SELECT c.name,
               ROUND(SUM(i.amount * (m.allocation_percent / 100.0)), 2) AS allocated_spend
        FROM service_client_map m
        JOIN autotask_clients c ON c.id = m.client_id
        JOIN services s ON s.id = m.service_id
        JOIN invoices i ON i.service_id = s.id
        GROUP BY c.id
        ORDER BY allocated_spend DESC
        """
    ).fetchall()

    # Contracts expiring within 60 days
    today = date.today().isoformat()
    soon = (date.today() + timedelta(days=60)).isoformat()
    expiring_contracts = db.execute(
        """
        SELECT c.*, v.name AS vendor_name
        FROM contracts c
        JOIN vendors v ON v.id = c.vendor_id
        WHERE c.end_date IS NOT NULL AND c.end_date != ''
          AND c.end_date >= ? AND c.end_date <= ?
        ORDER BY c.end_date
        """,
        (today, soon),
    ).fetchall()

    # Expired contracts
    expired_contracts = db.execute(
        """
        SELECT c.*, v.name AS vendor_name
        FROM contracts c
        JOIN vendors v ON v.id = c.vendor_id
        WHERE c.end_date IS NOT NULL AND c.end_date != ''
          AND c.end_date < ?
        ORDER BY c.end_date DESC
        LIMIT 5
        """,
        (today,),
    ).fetchall()

    return render_template(
        "dashboard.html",
        totals=totals,
        monthly_spend=monthly_spend,
        spend_by_vendor=spend_by_vendor,
        spend_by_client=spend_by_client,
        expiring_contracts=expiring_contracts,
        expired_contracts=expired_contracts,
        today=today,
    )


# ─── vendors ────────────────────────────────────────────────────────────────

@app.route("/vendors", methods=["GET", "POST"])
def vendors() -> str:
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        website = request.form.get("website", "").strip()
        contact_name = request.form.get("contact_name", "").strip()
        contact_email = request.form.get("contact_email", "").strip()
        notes = request.form.get("notes", "").strip()
        if not name:
            flash("Vendor name is required.", "error")
        else:
            try:
                db.execute(
                    "INSERT INTO vendors(name, website, contact_name, contact_email, notes) VALUES (?, ?, ?, ?, ?)",
                    (name, website, contact_name, contact_email, notes),
                )
                db.commit()
                flash("Vendor created.", "success")
                return redirect(url_for("vendors"))
            except sqlite3.IntegrityError:
                flash("Vendor name already exists.", "error")

    records = db.execute("SELECT * FROM vendors ORDER BY name").fetchall()
    return render_template("vendors.html", vendors=records)


@app.route("/vendors/<int:vendor_id>/delete", methods=["POST"])
def delete_vendor(vendor_id: int) -> str:
    db = get_db()
    db.execute("DELETE FROM vendors WHERE id = ?", (vendor_id,))
    db.commit()
    flash("Vendor deleted.", "success")
    return redirect(url_for("vendors"))


# ─── contracts ──────────────────────────────────────────────────────────────

@app.route("/contracts", methods=["GET", "POST"])
def contracts() -> str:
    db = get_db()
    vendors = db.execute("SELECT id, name FROM vendors ORDER BY name").fetchall()

    if request.method == "POST":
        vendor_id = request.form.get("vendor_id")
        contract_name = request.form.get("contract_name", "").strip()
        contract_number = request.form.get("contract_number", "").strip()
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip() or None
        auto_renew = 1 if request.form.get("auto_renew") else 0
        monthly_cost = request.form.get("monthly_cost", "0").strip() or "0"
        payment_terms = request.form.get("payment_terms", "").strip()
        notes = request.form.get("notes", "").strip()

        if not vendor_id or not contract_name or not start_date:
            flash("Vendor, contract name, and start date are required.", "error")
        else:
            db.execute(
                """
                INSERT INTO contracts(vendor_id, contract_name, contract_number, start_date,
                    end_date, auto_renew, monthly_cost, payment_terms, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (vendor_id, contract_name, contract_number, start_date,
                 end_date, auto_renew, float(monthly_cost), payment_terms, notes),
            )
            db.commit()
            flash("Contract added.", "success")
            return redirect(url_for("contracts"))

    records = db.execute(
        """
        SELECT c.*, v.name AS vendor_name
        FROM contracts c
        JOIN vendors v ON v.id = c.vendor_id
        ORDER BY v.name, c.contract_name
        """
    ).fetchall()

    # Annotate with status
    contracts_with_status = []
    for row in records:
        row_dict = dict(row)
        row_dict["status"] = contract_status(row["end_date"], row["auto_renew"])
        contracts_with_status.append(row_dict)

    return render_template("contracts.html", contracts=contracts_with_status, vendors=vendors)


@app.route("/contracts/<int:contract_id>/delete", methods=["POST"])
def delete_contract(contract_id: int) -> str:
    db = get_db()
    db.execute("DELETE FROM contracts WHERE id = ?", (contract_id,))
    db.commit()
    flash("Contract deleted.", "success")
    return redirect(url_for("contracts"))


# ─── services ───────────────────────────────────────────────────────────────

@app.route("/services", methods=["GET", "POST"])
def services() -> str:
    db = get_db()
    vendors = db.execute("SELECT id, name FROM vendors ORDER BY name").fetchall()
    all_contracts = db.execute(
        "SELECT c.id, c.contract_name, v.name AS vendor_name FROM contracts c JOIN vendors v ON v.id=c.vendor_id ORDER BY v.name, c.contract_name"
    ).fetchall()

    if request.method == "POST":
        vendor_id = request.form.get("vendor_id")
        contract_id = request.form.get("contract_id") or None
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        recurring_cost = request.form.get("recurring_cost", "0").strip() or "0"
        billing_cycle = request.form.get("billing_cycle", "").strip()

        if not vendor_id or not name:
            flash("Vendor and service name are required.", "error")
        else:
            db.execute(
                """
                INSERT INTO services(vendor_id, contract_id, name, category, recurring_cost, billing_cycle)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (vendor_id, contract_id, name, category, float(recurring_cost), billing_cycle),
            )
            db.commit()
            flash("Service added.", "success")
            return redirect(url_for("services"))

    records = db.execute(
        """
        SELECT s.*, v.name AS vendor_name, c.contract_name
        FROM services s
        JOIN vendors v ON v.id = s.vendor_id
        LEFT JOIN contracts c ON c.id = s.contract_id
        ORDER BY v.name, s.name
        """
    ).fetchall()

    return render_template("services.html", services=records, vendors=vendors, contracts=all_contracts)


@app.route("/services/<int:service_id>/delete", methods=["POST"])
def delete_service(service_id: int) -> str:
    db = get_db()
    db.execute("DELETE FROM services WHERE id = ?", (service_id,))
    db.commit()
    flash("Service deleted.", "success")
    return redirect(url_for("services"))


# ─── clients ────────────────────────────────────────────────────────────────

@app.route("/clients", methods=["GET", "POST"])
def clients() -> str:
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        account_code = request.form.get("account_code", "").strip()
        monthly_revenue = request.form.get("monthly_revenue", "0").strip() or "0"
        notes = request.form.get("notes", "").strip()
        if not name:
            flash("Client name is required.", "error")
        else:
            try:
                db.execute(
                    "INSERT INTO autotask_clients(name, account_code, monthly_revenue, notes) VALUES (?, ?, ?, ?)",
                    (name, account_code, float(monthly_revenue), notes),
                )
                db.commit()
                flash("Client added.", "success")
                return redirect(url_for("clients"))
            except sqlite3.IntegrityError:
                flash("Client already exists.", "error")

    records = db.execute("SELECT * FROM autotask_clients ORDER BY name").fetchall()
    return render_template("clients.html", clients=records)


@app.route("/clients/<int:client_id>/edit", methods=["POST"])
def edit_client(client_id: int) -> str:
    db = get_db()
    monthly_revenue = request.form.get("monthly_revenue", "0").strip() or "0"
    notes = request.form.get("notes", "").strip()
    db.execute(
        "UPDATE autotask_clients SET monthly_revenue = ?, notes = ? WHERE id = ?",
        (float(monthly_revenue), notes, client_id),
    )
    db.commit()
    flash("Client updated.", "success")
    return redirect(url_for("clients"))


@app.route("/clients/<int:client_id>/delete", methods=["POST"])
def delete_client(client_id: int) -> str:
    db = get_db()
    db.execute("DELETE FROM autotask_clients WHERE id = ?", (client_id,))
    db.commit()
    flash("Client deleted.", "success")
    return redirect(url_for("clients"))


# ─── invoices ───────────────────────────────────────────────────────────────

@app.route("/invoices", methods=["GET", "POST"])
def invoices() -> str:
    db = get_db()
    vendors = db.execute("SELECT id, name FROM vendors ORDER BY name").fetchall()
    all_services = db.execute(
        "SELECT s.id, s.name, v.name AS vendor_name FROM services s JOIN vendors v ON v.id=s.vendor_id ORDER BY v.name, s.name"
    ).fetchall()

    if request.method == "POST":
        vendor_id = request.form.get("vendor_id")
        service_id = request.form.get("service_id") or None
        invoice_number = request.form.get("invoice_number", "").strip()
        invoice_date = request.form.get("invoice_date", "").strip()
        amount = request.form.get("amount", "0").strip()
        description = request.form.get("description", "").strip()

        if not vendor_id or not invoice_date:
            flash("Vendor and invoice date are required.", "error")
        else:
            db.execute(
                """
                INSERT INTO invoices(vendor_id, service_id, invoice_number, invoice_date, amount, description)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (vendor_id, service_id, invoice_number, invoice_date, float(amount), description),
            )
            db.commit()
            flash("Invoice added.", "success")
            return redirect(url_for("invoices"))

    records = db.execute(
        """
        SELECT i.*, v.name AS vendor_name, s.name AS service_name
        FROM invoices i
        JOIN vendors v ON v.id = i.vendor_id
        LEFT JOIN services s ON s.id = i.service_id
        ORDER BY i.invoice_date DESC, i.id DESC
        """
    ).fetchall()
    return render_template("invoices.html", invoices=records, vendors=vendors, services=all_services)


@app.route("/invoices/<int:invoice_id>/delete", methods=["POST"])
def delete_invoice(invoice_id: int) -> str:
    db = get_db()
    db.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
    db.commit()
    flash("Invoice deleted.", "success")
    return redirect(url_for("invoices"))


@app.route("/invoices/import", methods=["POST"])
def import_invoices() -> str:
    db = get_db()
    uploaded = request.files.get("invoice_csv")
    if not uploaded or not uploaded.filename:
        flash("Please upload a CSV file.", "error")
        return redirect(url_for("invoices"))

    decoded = uploaded.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(decoded))
    inserted = 0

    for row in reader:
        vendor_name = row.get("vendor_name", "").strip()
        service_name = row.get("service_name", "").strip()
        invoice_number = row.get("invoice_number", "").strip()
        invoice_date = row.get("invoice_date", "").strip()
        amount = row.get("amount", "0").strip()
        description = row.get("description", "").strip()

        if not vendor_name or not invoice_date:
            continue

        vendor = db.execute("SELECT id FROM vendors WHERE name = ?", (vendor_name,)).fetchone()
        if vendor is None:
            db.execute("INSERT INTO vendors(name) VALUES (?)", (vendor_name,))
            vendor = db.execute("SELECT id FROM vendors WHERE name = ?", (vendor_name,)).fetchone()

        service_id = None
        if service_name:
            service = db.execute(
                "SELECT id FROM services WHERE vendor_id = ? AND name = ?",
                (vendor["id"], service_name),
            ).fetchone()
            if service:
                service_id = service["id"]

        db.execute(
            """
            INSERT INTO invoices(vendor_id, service_id, invoice_number, invoice_date, amount, description)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (vendor["id"], service_id, invoice_number, invoice_date, float(amount), description),
        )
        inserted += 1

    db.commit()
    flash(f"Imported {inserted} invoice rows.", "success")
    return redirect(url_for("invoices"))


# ─── expenses (direct client assignment) ─────────────────────────────────────

@app.route("/expenses", methods=["GET", "POST"])
def expenses() -> str:
    db = get_db()
    all_clients = db.execute("SELECT id, name FROM autotask_clients ORDER BY name").fetchall()
    vendors = db.execute("SELECT id, name FROM vendors ORDER BY name").fetchall()

    if request.method == "POST":
        client_id = request.form.get("client_id")
        vendor_id = request.form.get("vendor_id") or None
        expense_date = request.form.get("expense_date", "").strip()
        amount = request.form.get("amount", "0").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()

        if not client_id or not expense_date:
            flash("Client and date are required.", "error")
        else:
            db.execute(
                """
                INSERT INTO expenses(client_id, vendor_id, expense_date, amount, category, description)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (client_id, vendor_id, expense_date, float(amount), category, description),
            )
            db.commit()
            flash("Expense recorded.", "success")
            return redirect(url_for("expenses"))

    records = db.execute(
        """
        SELECT e.*, c.name AS client_name, v.name AS vendor_name
        FROM expenses e
        JOIN autotask_clients c ON c.id = e.client_id
        LEFT JOIN vendors v ON v.id = e.vendor_id
        ORDER BY e.expense_date DESC, e.id DESC
        """
    ).fetchall()
    return render_template("expenses.html", expenses=records, clients=all_clients, vendors=vendors)


@app.route("/expenses/<int:expense_id>/delete", methods=["POST"])
def delete_expense(expense_id: int) -> str:
    db = get_db()
    db.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    db.commit()
    flash("Expense deleted.", "success")
    return redirect(url_for("expenses"))


# ─── service-to-client mapping ───────────────────────────────────────────────

@app.route("/mapping", methods=["GET", "POST"])
def mapping() -> str:
    db = get_db()
    all_services = db.execute(
        "SELECT s.id, s.name, v.name AS vendor_name FROM services s JOIN vendors v ON v.id = s.vendor_id ORDER BY v.name, s.name"
    ).fetchall()
    all_clients = db.execute("SELECT id, name FROM autotask_clients ORDER BY name").fetchall()

    if request.method == "POST":
        service_id = request.form.get("service_id")
        client_id = request.form.get("client_id")
        allocation_percent = request.form.get("allocation_percent", "100")
        if not service_id or not client_id:
            flash("Service and client are required.", "error")
        else:
            try:
                db.execute(
                    "INSERT INTO service_client_map(service_id, client_id, allocation_percent) VALUES (?, ?, ?)",
                    (service_id, client_id, float(allocation_percent)),
                )
                db.commit()
                flash("Mapping created.", "success")
                return redirect(url_for("mapping"))
            except sqlite3.IntegrityError:
                flash("That service-client mapping already exists.", "error")

    mappings = db.execute(
        """
        SELECT m.*, s.name AS service_name, v.name AS vendor_name, c.name AS client_name
        FROM service_client_map m
        JOIN services s ON s.id = m.service_id
        JOIN vendors v ON v.id = s.vendor_id
        JOIN autotask_clients c ON c.id = m.client_id
        ORDER BY c.name, v.name, s.name
        """
    ).fetchall()

    return render_template("mapping.html", services=all_services, clients=all_clients, mappings=mappings)


@app.route("/mapping/<int:map_id>/delete", methods=["POST"])
def delete_mapping(map_id: int) -> str:
    db = get_db()
    db.execute("DELETE FROM service_client_map WHERE id = ?", (map_id,))
    db.commit()
    flash("Mapping removed.", "success")
    return redirect(url_for("mapping"))


# ─── profitability ────────────────────────────────────────────────────────────

@app.route("/profitability")
def profitability() -> str:
    db = get_db()

    # Allocated cost from service mappings + invoices
    allocated = db.execute(
        """
        SELECT c.id, c.name, c.monthly_revenue,
               ROUND(SUM(i.amount * (m.allocation_percent / 100.0)), 2) AS total_allocated_cost
        FROM autotask_clients c
        LEFT JOIN service_client_map m ON m.client_id = c.id
        LEFT JOIN services s ON s.id = m.service_id
        LEFT JOIN invoices i ON i.service_id = s.id
        GROUP BY c.id
        """
    ).fetchall()

    # Direct expenses per client
    direct_expenses = db.execute(
        """
        SELECT client_id, ROUND(SUM(amount), 2) AS total_direct
        FROM expenses
        GROUP BY client_id
        """
    ).fetchall()
    direct_map = {row["client_id"]: row["total_direct"] for row in direct_expenses}

    # Date range for averaging monthly costs
    date_range = db.execute(
        """
        SELECT MIN(invoice_date) AS earliest, MAX(invoice_date) AS latest
        FROM invoices
        """
    ).fetchone()

    months_span = 1
    if date_range["earliest"] and date_range["latest"]:
        try:
            start = date.fromisoformat(date_range["earliest"][:7] + "-01")
            end = date.fromisoformat(date_range["latest"][:7] + "-01")
            diff_months = (end.year - start.year) * 12 + (end.month - start.month) + 1
            months_span = max(1, diff_months)
        except ValueError:
            pass

    client_rows = []
    for row in allocated:
        total_alloc = row["total_allocated_cost"] or 0.0
        total_direct = direct_map.get(row["id"], 0.0) or 0.0
        total_cost = total_alloc + total_direct
        avg_monthly_cost = round(total_cost / months_span, 2)
        monthly_rev = row["monthly_revenue"] or 0.0
        monthly_profit = round(monthly_rev - avg_monthly_cost, 2)
        margin_pct = round((monthly_profit / monthly_rev * 100), 1) if monthly_rev else None

        client_rows.append({
            "id": row["id"],
            "name": row["name"],
            "monthly_revenue": monthly_rev,
            "avg_monthly_cost": avg_monthly_cost,
            "monthly_profit": monthly_profit,
            "margin_pct": margin_pct,
            "total_allocated_cost": total_alloc,
            "total_direct_expenses": total_direct,
        })

    client_rows.sort(key=lambda r: r["monthly_revenue"], reverse=True)

    # Totals
    total_revenue = sum(r["monthly_revenue"] for r in client_rows)
    total_cost = sum(r["avg_monthly_cost"] for r in client_rows)
    total_profit = round(total_revenue - total_cost, 2)
    overall_margin = round((total_profit / total_revenue * 100), 1) if total_revenue else None

    return render_template(
        "profitability.html",
        clients=client_rows,
        months_span=months_span,
        total_revenue=total_revenue,
        total_cost=total_cost,
        total_profit=total_profit,
        overall_margin=overall_margin,
    )


# ─── template filters ─────────────────────────────────────────────────────────

@app.template_filter("money")
def money_filter(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


@app.template_filter("pct")
def pct_filter(value: Any) -> str:
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
