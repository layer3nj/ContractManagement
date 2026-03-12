from __future__ import annotations

import csv
import io
import os
import sqlite3
from contextlib import closing
from datetime import datetime
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
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                category TEXT,
                recurring_cost REAL DEFAULT 0,
                billing_cycle TEXT,
                FOREIGN KEY(vendor_id) REFERENCES vendors(id)
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
                account_code TEXT
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
            """
        )
        db.commit()


@app.route("/")
def dashboard() -> str:
    db = get_db()
    totals = {
        "vendors": db.execute("SELECT COUNT(*) AS c FROM vendors").fetchone()["c"],
        "services": db.execute("SELECT COUNT(*) AS c FROM services").fetchone()["c"],
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

    return render_template(
        "dashboard.html",
        totals=totals,
        monthly_spend=monthly_spend,
        spend_by_vendor=spend_by_vendor,
        spend_by_client=spend_by_client,
    )


@app.route("/vendors", methods=["GET", "POST"])
def vendors() -> str:
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        notes = request.form.get("notes", "").strip()
        if not name:
            flash("Vendor name is required.", "error")
        else:
            try:
                db.execute("INSERT INTO vendors(name, notes) VALUES (?, ?)", (name, notes))
                db.commit()
                flash("Vendor created.", "success")
                return redirect(url_for("vendors"))
            except sqlite3.IntegrityError:
                flash("Vendor name already exists.", "error")

    records = db.execute("SELECT * FROM vendors ORDER BY name").fetchall()
    return render_template("vendors.html", vendors=records)


@app.route("/services", methods=["GET", "POST"])
def services() -> str:
    db = get_db()
    vendors = db.execute("SELECT id, name FROM vendors ORDER BY name").fetchall()

    if request.method == "POST":
        vendor_id = request.form.get("vendor_id")
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        recurring_cost = request.form.get("recurring_cost", "0").strip() or "0"
        billing_cycle = request.form.get("billing_cycle", "").strip()

        if not vendor_id or not name:
            flash("Vendor and service name are required.", "error")
        else:
            db.execute(
                """
                INSERT INTO services(vendor_id, name, category, recurring_cost, billing_cycle)
                VALUES (?, ?, ?, ?, ?)
                """,
                (vendor_id, name, category, float(recurring_cost), billing_cycle),
            )
            db.commit()
            flash("Service added.", "success")
            return redirect(url_for("services"))

    records = db.execute(
        """
        SELECT s.*, v.name AS vendor_name
        FROM services s
        JOIN vendors v ON v.id = s.vendor_id
        ORDER BY v.name, s.name
        """
    ).fetchall()

    return render_template("services.html", services=records, vendors=vendors)


@app.route("/clients", methods=["GET", "POST"])
def clients() -> str:
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        account_code = request.form.get("account_code", "").strip()
        if not name:
            flash("Client name is required.", "error")
        else:
            try:
                db.execute(
                    "INSERT INTO autotask_clients(name, account_code) VALUES (?, ?)",
                    (name, account_code),
                )
                db.commit()
                flash("Client added.", "success")
                return redirect(url_for("clients"))
            except sqlite3.IntegrityError:
                flash("Client already exists.", "error")

    records = db.execute("SELECT * FROM autotask_clients ORDER BY name").fetchall()
    return render_template("clients.html", clients=records)


@app.route("/mapping", methods=["GET", "POST"])
def mapping() -> str:
    db = get_db()
    services = db.execute(
        "SELECT s.id, s.name, v.name AS vendor_name FROM services s JOIN vendors v ON v.id = s.vendor_id ORDER BY v.name, s.name"
    ).fetchall()
    clients = db.execute("SELECT id, name FROM autotask_clients ORDER BY name").fetchall()

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

    return render_template("mapping.html", services=services, clients=clients, mappings=mappings)


@app.route("/invoices", methods=["GET", "POST"])
def invoices() -> str:
    db = get_db()
    vendors = db.execute("SELECT id, name FROM vendors ORDER BY name").fetchall()
    services = db.execute(
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
    return render_template("invoices.html", invoices=records, vendors=vendors, services=services)


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


@app.template_filter("money")
def money_filter(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
