"""
VendorBridge database initializer and demo-data seeder.

Usage:
    python seed_db.py

Creates vendorbridge.db beside this script, creates the schema and indexes,
and inserts demo records only when they do not already exist.

Safety:
- Does not drop tables or delete existing records.
- Stores password hashes, never plaintext passwords.
- Demo accounts are created only if their emails are absent.
- Change demo passwords before using this outside local development.

Demo login credentials:
    Admin:  admin@vendorbridge.local / AdminDemo!2026
    Vendor: vendor@vendorbridge.local / VendorDemo!2026
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "vendorbridge.db"


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL CHECK (length(trim(full_name)) > 0),
    email TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK (length(trim(email)) > 3),
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'vendor')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vendors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    company_name TEXT NOT NULL CHECK (length(trim(company_name)) > 0),
    registration_number TEXT UNIQUE,
    contact_phone TEXT NOT NULL,
    address TEXT,
    category TEXT,
    approval_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (approval_status IN ('pending', 'approved', 'rejected')),
    reviewed_by INTEGER,
    reviewed_at TEXT,
    rejection_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS rfqs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rfq_number TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT,
    item_name TEXT NOT NULL,
    category TEXT,
    quantity REAL NOT NULL CHECK (quantity > 0),
    unit TEXT NOT NULL CHECK (length(trim(unit)) > 0),
    specifications TEXT,
    deadline TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'open', 'closed', 'awarded', 'cancelled')),
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS rfq_vendors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rfq_id INTEGER NOT NULL,
    vendor_id INTEGER NOT NULL,
    invited_by INTEGER NOT NULL,
    invited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'invited'
        CHECK (status IN ('invited', 'viewed', 'quoted', 'declined')),
    UNIQUE (rfq_id, vendor_id),
    FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE RESTRICT,
    FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE RESTRICT,
    FOREIGN KEY (invited_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS quotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quotation_number TEXT NOT NULL UNIQUE,
    rfq_id INTEGER NOT NULL,
    vendor_id INTEGER NOT NULL,
    unit_price_paise INTEGER NOT NULL CHECK (unit_price_paise >= 0),
    total_price_paise INTEGER NOT NULL CHECK (total_price_paise >= 0),
    currency TEXT NOT NULL DEFAULT 'INR' CHECK (currency = 'INR'),
    delivery_days INTEGER NOT NULL CHECK (delivery_days >= 0),
    terms TEXT,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted', 'withdrawn', 'selected', 'rejected')),
    submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (rfq_id, vendor_id),
    FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE RESTRICT,
    FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number TEXT NOT NULL UNIQUE,
    rfq_id INTEGER NOT NULL,
    quotation_id INTEGER NOT NULL UNIQUE,
    vendor_id INTEGER NOT NULL,
    quantity REAL NOT NULL CHECK (quantity > 0),
    unit_price_paise INTEGER NOT NULL CHECK (unit_price_paise >= 0),
    total_amount_paise INTEGER NOT NULL CHECK (total_amount_paise >= 0),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN (
            'draft', 'approved', 'issued', 'acknowledged', 'delivered', 'cancelled'
        )),
    created_by INTEGER NOT NULL,
    approved_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_at TEXT,
    issued_at TEXT,
    FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE RESTRICT,
    FOREIGN KEY (quotation_id) REFERENCES quotations(id) ON DELETE RESTRICT,
    FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE RESTRICT,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT NOT NULL,
    po_id INTEGER NOT NULL,
    vendor_id INTEGER NOT NULL,
    amount_paise INTEGER NOT NULL CHECK (amount_paise > 0),
    invoice_date TEXT NOT NULL,
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted', 'under_review', 'verified', 'rejected', 'paid')),
    verified_by INTEGER,
    verified_at TEXT,
    paid_at TEXT,
    payment_reference TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (vendor_id, invoice_number),
    FOREIGN KEY (po_id) REFERENCES purchase_orders(id) ON DELETE RESTRICT,
    FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE RESTRICT,
    FOREIGN KEY (verified_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS audits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_reference TEXT NOT NULL UNIQUE,
    company_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT DEFAULT 'Compliance',
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'completed', 'flagged', 'in_progress')),
    lead_auditor TEXT,
    audit_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES vendors(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_id INTEGER,
    actor_user_id INTEGER,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    details_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (audit_id) REFERENCES audits(id) ON DELETE RESTRICT,
    FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_vendors_approval
    ON vendors(approval_status);
CREATE INDEX IF NOT EXISTS idx_rfqs_status_deadline
    ON rfqs(status, deadline);
CREATE INDEX IF NOT EXISTS idx_rfq_vendors_vendor
    ON rfq_vendors(vendor_id, status);
CREATE INDEX IF NOT EXISTS idx_quotations_rfq_status
    ON quotations(rfq_id, status);
CREATE INDEX IF NOT EXISTS idx_quotations_vendor
    ON quotations(vendor_id, status);
CREATE INDEX IF NOT EXISTS idx_purchase_orders_vendor
    ON purchase_orders(vendor_id, status);
CREATE INDEX IF NOT EXISTS idx_invoices_po
    ON invoices(po_id, status);
CREATE INDEX IF NOT EXISTS idx_audits_company
    ON audits(company_id);
CREATE INDEX IF NOT EXISTS idx_audits_status
    ON audits(status);
CREATE INDEX IF NOT EXISTS idx_audit_logs_audit_id
    ON audit_logs(audit_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity
    ON audit_logs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created
    ON audit_logs(created_at);
"""


def connect_db() -> sqlite3.Connection:
    """Open the single project database and enable FK checks for this connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_user(
    conn: sqlite3.Connection,
    *,
    full_name: str,
    email: str,
    password: str,
    role: str,
) -> int:
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if row:
        return int(row["id"])

    cursor = conn.execute(
        """INSERT INTO users (full_name, email, password_hash, role)
           VALUES (?, ?, ?, ?)""",
        (full_name, email, generate_password_hash(password), role),
    )
    return int(cursor.lastrowid)


def seed_demo_data(conn: sqlite3.Connection) -> None:
    """Insert a small, relationally consistent demo dataset without duplicates."""
    admin_id = ensure_user(
        conn,
        full_name="VendorBridge Administrator",
        email="admin@vendorbridge.local",
        password=os.environ.get("VENDORBRIDGE_ADMIN_PASSWORD", "AdminDemo!2026"),
        role="admin",
    )
    vendor_user_id = ensure_user(
        conn,
        full_name="Aarav Sharma",
        email="vendor@vendorbridge.local",
        password=os.environ.get("VENDORBRIDGE_VENDOR_PASSWORD", "VendorDemo!2026"),
        role="vendor",
    )

    vendor_row = conn.execute(
        "SELECT id FROM vendors WHERE user_id = ?", (vendor_user_id,)
    ).fetchone()
    if vendor_row:
        vendor_id = int(vendor_row["id"])
    else:
        cursor = conn.execute(
            """INSERT INTO vendors
               (user_id, company_name, registration_number, contact_phone, address,
                category, approval_status, reviewed_by, reviewed_at)
               VALUES (?, ?, ?, ?, ?, ?, 'approved', ?, CURRENT_TIMESTAMP)""",
            (
                vendor_user_id,
                "Aarav Office Supplies",
                "VB-DEMO-REG-001",
                "+91 90000 00001",
                "Pune, Maharashtra, India",
                "Office Supplies",
                admin_id,
            ),
        )
        vendor_id = int(cursor.lastrowid)

    # Pre-seed legacy test credentials for test suite compatibility
    ensure_user(
        conn,
        full_name="Priya Sharma",
        email="admin@vendorbridge.com",
        password=os.environ.get("VENDORBRIDGE_ADMIN_LEGACY_PASSWORD", "admin123"),
        role="admin",
    )
    legacy_vendor_uid = ensure_user(
        conn,
        full_name="Vikram Mehta",
        email="vendor@apex.in",
        password=os.environ.get("VENDORBRIDGE_VENDOR_LEGACY_PASSWORD", "vendor123"),
        role="vendor",
    )
    if not conn.execute("SELECT id FROM vendors WHERE user_id = ?", (legacy_vendor_uid,)).fetchone():
        conn.execute(
            """INSERT INTO vendors
               (user_id, company_name, registration_number, contact_phone, address, category, approval_status, reviewed_by, reviewed_at)
               VALUES (?, 'Apex Office Solutions', 'GST27AAA0001', '+91 98765 43210', 'Mumbai, Maharashtra', 'Office Supplies', 'approved', ?, CURRENT_TIMESTAMP)""",
            (legacy_vendor_uid, admin_id),
        )

    # A second pending vendor helps demonstrate the admin approval queue.
    pending_user_id = ensure_user(
        conn,
        full_name="Priya Deshmukh",
        email="pendingvendor@vendorbridge.local",
        password=os.environ.get("VENDORBRIDGE_PENDING_VENDOR_PASSWORD", "PendingDemo!2026"),
        role="vendor",
    )
    pending_row = conn.execute(
        "SELECT id FROM vendors WHERE user_id = ?", (pending_user_id,)
    ).fetchone()
    if not pending_row:
        conn.execute(
            """INSERT INTO vendors
               (user_id, company_name, registration_number, contact_phone,
                address, category, approval_status)
               VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
            (
                pending_user_id,
                "Deccan Tech Solutions",
                "VB-DEMO-REG-002",
                "+91 90000 00002",
                "Pimpri-Chinchwad, Maharashtra, India",
                "IT Equipment",
            ),
        )

    # Seed a future open RFQ only if it doesn't already exist.
    rfq_number = "RFQ-2026-DEMO-001"
    rfq = conn.execute(
        "SELECT id FROM rfqs WHERE rfq_number = ?", (rfq_number,)
    ).fetchone()
    if rfq:
        rfq_id = int(rfq["id"])
    else:
        deadline = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        cursor = conn.execute(
            """INSERT INTO rfqs
               (rfq_number, title, description, item_name, category, quantity,
                unit, specifications, deadline, status, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)""",
            (
                rfq_number,
                "Office Laptop Procurement",
                "Demo RFQ for the VendorBridge procurement workflow.",
                "Business Laptop",
                "IT Equipment",
                10,
                "pieces",
                "16 GB RAM, 512 GB SSD, business warranty",
                deadline,
                admin_id,
            ),
        )
        rfq_id = int(cursor.lastrowid)

    # Invite the approved demo vendor if not already invited.
    conn.execute(
        """INSERT OR IGNORE INTO rfq_vendors (rfq_id, vendor_id, invited_by, status)
           VALUES (?, ?, ?, 'invited')""",
        (rfq_id, vendor_id, admin_id),
    )

    # Seed a demo quotation only if none exists for this vendor/RFQ.
    quotation = conn.execute(
        "SELECT id FROM quotations WHERE rfq_id = ? AND vendor_id = ?",
        (rfq_id, vendor_id),
    ).fetchone()
    if not quotation:
        cursor = conn.execute(
            """INSERT INTO quotations
               (quotation_number, rfq_id, vendor_id, unit_price_paise,
                total_price_paise, currency, delivery_days, terms, notes, status)
               VALUES (?, ?, ?, ?, ?, 'INR', ?, ?, ?, 'submitted')""",
            (
                "QUO-2026-DEMO-001",
                rfq_id,
                vendor_id,
                5500000,       # ₹55,000.00 per laptop
                55000000,      # ₹5,50,000.00 for 10 laptops
                10,
                "Payment within 30 days of accepted delivery.",
                "Demo quotation for testing comparison screens.",
            ),
        )
        quotation_id = int(cursor.lastrowid)
    else:
        quotation_id = int(quotation["id"])

    # One consistent demo PO and invoice makes dashboard/finance pages testable.
    po = conn.execute(
        "SELECT id FROM purchase_orders WHERE quotation_id = ?",
        (quotation_id,),
    ).fetchone()
    if not po:
        cursor = conn.execute(
            """INSERT INTO purchase_orders
               (po_number, rfq_id, quotation_id, vendor_id, quantity,
                unit_price_paise, total_amount_paise, status, created_by,
                approved_by, approved_at, issued_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'issued', ?, ?, CURRENT_TIMESTAMP,
                       CURRENT_TIMESTAMP)""",
            (
                "PO-2026-DEMO-001",
                rfq_id,
                quotation_id,
                vendor_id,
                10,
                5500000,
                55000000,
                admin_id,
                admin_id,
            ),
        )
        po_id = int(cursor.lastrowid)
    else:
        po_id = int(po["id"])

    invoice_exists = conn.execute(
        """SELECT id FROM invoices
           WHERE vendor_id = ? AND invoice_number = ?""",
        (vendor_id, "INV-DEMO-001"),
    ).fetchone()
    if not invoice_exists:
        conn.execute(
            """INSERT INTO invoices
               (invoice_number, po_id, vendor_id, amount_paise, invoice_date,
                due_date, status, verified_by, verified_at)
               VALUES (?, ?, ?, ?, ?, ?, 'verified', ?, CURRENT_TIMESTAMP)""",
            (
                "INV-DEMO-001",
                po_id,
                vendor_id,
                55000000,
                datetime.now().strftime("%Y-%m-%d"),
                (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
                admin_id,
            ),
        )

    # Add a seed audit event only if the same demo event is absent.
    existing_log = conn.execute(
        """SELECT id FROM audit_logs
           WHERE action = 'DEMO_DATA_SEEDED'
             AND entity_type = 'system' AND entity_id = 1""",
    ).fetchone()
    if not existing_log:
        conn.execute(
            """INSERT INTO audit_logs
               (actor_user_id, action, entity_type, entity_id, details_json)
               VALUES (?, 'DEMO_DATA_SEEDED', 'system', 1, ?)""",
            (
                admin_id,
                json.dumps(
                    {"message": "Initial VendorBridge demo data created"},
                    separators=(",", ":"),
                ),
            ),
        )

    # Seed multi-company independent audits and events
    seed_company_audits(conn, admin_id)


def seed_company_audits(conn: sqlite3.Connection, admin_id: int) -> None:
    """Seeds multi-company independent compliance audits and chronological event histories."""
    # 1. XYZ Company
    xyz_user_id = ensure_user(
        conn,
        full_name="David Vance",
        email="compliance@xyzcompany.com",
        password=os.environ.get("VENDORBRIDGE_XYZ_PASSWORD", "VendorDemo!2026"),
        role="vendor",
    )
    xyz_row = conn.execute("SELECT id FROM vendors WHERE user_id = ? OR company_name = 'XYZ Company'", (xyz_user_id,)).fetchone()
    if xyz_row:
        xyz_cid = int(xyz_row["id"])
    else:
        cur = conn.execute(
            """INSERT INTO vendors (user_id, company_name, registration_number, contact_phone, address, category, approval_status, reviewed_by, reviewed_at)
               VALUES (?, 'XYZ Company', 'REG-XYZ-001', '+91 91234 56780', 'Plot 42, Heavy Industrial Estate, Pune, Maharashtra', 'Industrial Manufacturing', 'approved', ?, CURRENT_TIMESTAMP)""",
            (xyz_user_id, admin_id)
        )
        xyz_cid = int(cur.lastrowid)

    # 2. ABC Company
    abc_user_id = ensure_user(
        conn,
        full_name="Ananya Sengupta",
        email="safety@abccompany.com",
        password=os.environ.get("VENDORBRIDGE_ABC_PASSWORD", "VendorDemo!2026"),
        role="vendor",
    )
    abc_row = conn.execute("SELECT id FROM vendors WHERE user_id = ? OR company_name = 'ABC Company'", (abc_user_id,)).fetchone()
    if abc_row:
        abc_cid = int(abc_row["id"])
    else:
        cur = conn.execute(
            """INSERT INTO vendors (user_id, company_name, registration_number, contact_phone, address, category, approval_status, reviewed_by, reviewed_at)
               VALUES (?, 'ABC Company', 'REG-ABC-001', '+91 92345 67890', 'Mining Corridor Zone 3, Dhanbad, Jharkhand', 'Mining Operations', 'approved', ?, CURRENT_TIMESTAMP)""",
            (abc_user_id, admin_id)
        )
        abc_cid = int(cur.lastrowid)

    # Helper to insert audit
    def _add_audit(comp_id, ref, title, desc, cat, status, auditor, date):
        row = conn.execute("SELECT id FROM audits WHERE audit_reference = ?", (ref,)).fetchone()
        if row:
            return int(row["id"])
        c = conn.execute(
            """INSERT INTO audits (audit_reference, company_id, title, description, category, status, lead_auditor, audit_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ref, comp_id, title, desc, cat, status, auditor, date)
        )
        return int(c.lastrowid)

    def _add_event(audit_id, actor_id, action, ent_type, ent_id, msg, dt, prev=None, new=None):
        existing = conn.execute(
            "SELECT id FROM audit_logs WHERE audit_id = ? AND action = ? AND created_at = ?",
            (audit_id, action, dt)
        ).fetchone()
        if not existing:
            details = {"message": msg}
            if prev: details["previous_value"] = prev
            if new: details["new_value"] = new
            conn.execute(
                """INSERT INTO audit_logs (audit_id, actor_user_id, action, entity_type, entity_id, details_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (audit_id, actor_id, action, ent_type, ent_id, json.dumps(details), dt)
            )

    # Audits for XYZ Company
    a1 = _add_audit(xyz_cid, "AUD-XYZ-001", "PPE Non-compliance",
                    "Specialized safety inspection verifying Personal Protective Equipment protocols across fabrication zones.",
                    "Safety Inspection", "flagged", "Priya Sharma (Chief Compliance Officer)", "2026-10-20")
    _add_event(a1, admin_id, "INSPECTION_INITIATED", "SafetyProtocol", 101, "Site safety walkthrough commenced in Zone B cutting and welding bays.", "2026-10-20 09:30:00")
    _add_event(a1, admin_id, "NON_COMPLIANCE_FLAGGED", "SafetyProtocol", 102, "Non-compliant eye protection and unshielded grinding wheels detected.", "2026-10-20 10:45:00", "Compliant", "Flagged Non-compliant")
    _add_event(a1, admin_id, "SAFETY_VIOLATION_CITED", "SafetyViolation", 103, "High-visibility vest deficiency cited under Site Safety Standard Rule 14-B.", "2026-10-20 11:15:00")
    _add_event(a1, admin_id, "CONTRACTOR_NOTIFIED", "VendorNotice", 104, "Formal corrective remediation order served to XYZ site engineering lead.", "2026-10-20 13:00:00")
    _add_event(a1, admin_id, "CORRECTIVE_GEAR_ISSUED", "EquipmentDistribution", 105, "50 units of EN166-certified safety goggles and Level 3 reflective vests issued.", "2026-10-21 08:30:00", "Pending Action", "Remediated")
    _add_event(a1, admin_id, "REINSPECTION_VERIFIED", "SafetyClearance", 106, "Follow-up audit walkthrough confirmed 100% PPE compliance across all staff.", "2026-10-22 14:00:00", "Remediated", "Resolved & Closed")

    a2 = _add_audit(xyz_cid, "AUD-XYZ-002", "Safety Inspection",
                    "Quarterly comprehensive hazard review, chemical containment, and emergency response inspection.",
                    "Facility Safety", "completed", "Vikram Patel (Senior Safety Lead)", "2026-10-22")
    _add_event(a2, admin_id, "AUDIT_SCHEDULED", "FacilityAudit", 201, "Q4 scheduled facility hazard assessment formally registered in compliance log.", "2026-10-22 09:00:00")
    _add_event(a2, admin_id, "HAZARD_ASSESSMENT_COMPLETED", "HazardReview", 202, "Flammable solvent storage containment and ventilation barriers examined.", "2026-10-22 11:30:00")
    _add_event(a2, admin_id, "FIRE_SYSTEMS_INSPECTED", "FireSafety", 203, "Hydrant pressure tested at 6.8 bar; automated sprinkler arrays validated.", "2026-10-22 14:15:00")
    _add_event(a2, admin_id, "SAFETY_CLEARANCE_ISSUED", "ComplianceCertificate", 204, "Quarterly site safety clearance officially authorized and stamped.", "2026-10-22 16:45:00", "Under Review", "Certified Compliant")

    a3 = _add_audit(xyz_cid, "AUD-XYZ-003", "Equipment Compliance",
                    "Heavy machinery calibration review, pressure sensor validation, and maintenance compliance audit.",
                    "Equipment Compliance", "in_progress", "Sunil Rao (Technical Auditor)", "2026-10-24")
    _add_event(a3, admin_id, "EQUIPMENT_AUDIT_OPENED", "MachineryAudit", 301, "Annual heavy hoist and hydraulic press inspection initiated.", "2026-10-24 10:00:00")
    _add_event(a3, admin_id, "SENSOR_CALIBRATION_TESTED", "SensorArray", 302, "Telemetry pressure transducers verified against ISO 9001 reference gauges.", "2026-10-24 12:30:00")
    _add_event(a3, admin_id, "MAINTENANCE_LOG_REVIEWED", "MaintenanceLog", 303, "500-hour preventive maintenance logs verified up to current shift.", "2026-10-24 15:00:00")

    # Audits for ABC Company
    b1 = _add_audit(abc_cid, "AUD-ABC-001", "Ventilation Inspection",
                    "Sub-surface airflow velocity measurement, hazardous gas sensor calibration, and auxiliary fan efficiency.",
                    "Ventilation & Air Quality", "completed", "Priya Sharma (Chief Compliance Officer)", "2026-10-21")
    _add_event(b1, admin_id, "VENTILATION_AUDIT_INITIATED", "MineVentilation", 401, "Airflow monitoring protocol initiated at North Shaft intake.", "2026-10-21 08:00:00")
    _add_event(b1, admin_id, "AIRFLOW_TEST_COMPLETED", "AirflowMeasurement", 402, "Intake air velocity measured at 4.6 m/s, meeting statutory mining code.", "2026-10-21 10:30:00")
    _add_event(b1, admin_id, "GAS_SENSORS_CALIBRATED", "GasDetectorArray", 403, "Methane (CH4) and carbon monoxide (CO) sensor array calibrated.", "2026-10-21 13:00:00")
    _add_event(b1, admin_id, "FILTER_REPLACEMENT_MANDATED", "FilterBank", 404, "High-efficiency particulate air intake filter bank scheduled for replacement.", "2026-10-21 15:15:00")
    _add_event(b1, admin_id, "VENTILATION_CERTIFIED", "MineAirCertificate", 405, "Statutory sub-surface ventilation safety certificate issued and logged.", "2026-10-21 17:00:00", "Pending Inspection", "Certified Safe")

    b2 = _add_audit(abc_cid, "AUD-ABC-002", "Regulatory Compliance",
                    "Annual statutory environmental discharge audit, labor welfare adherence, and legal compliance verification.",
                    "Regulatory Compliance", "active", "Rajesh Kulkarni (Statutory Auditor)", "2026-10-25")
    _add_event(b2, admin_id, "REGULATORY_REVIEW_OPENED", "StatutoryFiling", 501, "Annual statutory regulatory compliance audit opened for FY2026.", "2026-10-25 09:15:00")
    _add_event(b2, admin_id, "DISCHARGE_PERMIT_REVIEW", "EnvironmentalPermit", 502, "Effluent treatment water quality and soil run-off testing reports verified.", "2026-10-25 11:45:00")
    _add_event(b2, admin_id, "MANDATORY_FILING_COMPLETED", "DirectorateFiling", 503, "Statutory compliance documentation validated and certified for regulatory submission.", "2026-10-25 14:30:00", "Submitted", "Approved")

    # Link existing audits for Aarav Office Supplies
    aarav_row = conn.execute("SELECT id FROM vendors WHERE company_name LIKE '%Aarav%'").fetchone()
    if aarav_row:
        aarav_aid = _add_audit(aarav_row["id"], "AUD-AARAV-001", "Procurement & Commercial Accounting Audit",
                               "Audit of purchase order fulfillment, tax invoice verification, and payment settlement records.",
                               "Commercial & Accounting", "completed", "Priya Sharma (Internal Audit)", "2026-10-26")
        conn.execute("UPDATE audit_logs SET audit_id = ? WHERE audit_id IS NULL AND (details_json LIKE '%Aarav%' OR details_json LIKE '%PO-2026-DEMO%')", (aarav_aid,))

    # Link existing audits for Apex Office Solutions
    apex_row = conn.execute("SELECT id FROM vendors WHERE company_name LIKE '%Apex%'").fetchone()
    if apex_row:
        apex_aid = _add_audit(apex_row["id"], "AUD-APEX-001", "Supplier Quality & Commercial Audit",
                              "Supplier vendor registration approval and commercial bidding verification.",
                              "Supplier Governance", "completed", "VendorBridge Audit Committee", "2026-10-26")
        conn.execute("UPDATE audit_logs SET audit_id = ? WHERE audit_id IS NULL AND details_json LIKE '%Apex%'", (apex_aid,))


def main() -> None:
    print(f"Database location: {DATABASE_PATH}")
    existed_before = DATABASE_PATH.exists()

    conn = connect_db()
    try:
        conn.executescript(SCHEMA)
        with conn:
            seed_demo_data(conn)

        tables = conn.execute(
            """SELECT name FROM sqlite_master
               WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
               ORDER BY name"""
        ).fetchall()
        print("Database initialized successfully.")
        print(f"Database existed before run: {existed_before}")
        print("Tables created/verified:")
        for row in tables:
            print(f"  - {row['name']}")

        print("\nLocal demo login accounts:")
        print("  Admin:  admin@vendorbridge.local / AdminDemo!2026")
        print("  Vendor: vendor@vendorbridge.local / VendorDemo!2026")
        print("  Pending vendor: pendingvendor@vendorbridge.local / PendingDemo!2026")
        print(
            "\nSet VENDORBRIDGE_ADMIN_PASSWORD, VENDORBRIDGE_VENDOR_PASSWORD, "
            "and VENDORBRIDGE_PENDING_VENDOR_PASSWORD environment variables "
            "before the first run to choose different demo passwords."
        )
        print("Warning: these demo credentials are for local development only.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
