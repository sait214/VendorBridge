"""
VendorBridge — Flask Application
Procurement Management System
Integrated with SQLite database layer (database.py).
"""
import os
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session
import database as db

app = Flask(__name__)
app.secret_key = os.environ.get('VENDORBRIDGE_SECRET_KEY', 'vendorbridge-enterprise-hackathon-2026-key')
app.permanent_session_lifetime = timedelta(days=7)

# Register automatic database connection cleanup per Flask request
app.teardown_appcontext(db.close_db)


def get_current_user():
    """Retrieve the currently logged-in user or None from database."""
    user_id = session.get('user_id')
    if user_id:
        return db.get_user_by_id(user_id)
    email = session.get('user_email')
    if email:
        user = db.get_user_by_email(email)
        if user:
            session['user_id'] = user['id']
        return user
    return None


# ── Authentication Protection Hook ──
@app.before_request
def require_login():
    """Ensure unauthenticated users are redirected to login for protected pages."""
    public_endpoints = {'login', 'register', 'static'}
    if request.endpoint and request.endpoint not in public_endpoints:
        if not get_current_user():
            if request.endpoint != 'index':
                flash('Please sign in to access VendorBridge.', 'warning')
            return redirect(url_for('login'))


# ── Root Route ──
@app.route('/')
def index():
    if get_current_user():
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


# ── Authentication Routes ──
@app.route('/login', methods=['GET', 'POST'])
def login():
    if get_current_user():
        return redirect(url_for('dashboard'))

    form_errors = {}
    mode = request.args.get('mode', 'login')
    active_role = request.args.get('role', 'user')

    if request.method == 'POST':
        action = request.form.get('action', 'login')
        if action == 'register':
            return handle_registration()

        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))
        login_type = request.form.get('login_type', 'user')
        active_role = login_type

        user = db.get_user_by_email(email)
        if user and db.verify_user_password(user['password'], password):
            # If user submitted through Admin login but account is a vendor
            if login_type == 'admin' and user.get('role') != 'admin':
                form_errors['general'] = 'This is a Vendor account. Please use the User Login option.'
                flash('This is a Vendor account. Please use the User Login option.', 'warning')
                return render_template('login.html', form_errors=form_errors, mode='login', active_role='user')

            session.clear()
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            if remember:
                session.permanent = True

            status_val = (user.get('status') or 'Active').lower()
            if status_val == 'pending':
                flash(f"Welcome, {user['name']}. Your vendor application is currently awaiting administrator review.", 'warning')
            elif status_val == 'rejected':
                flash("Notice: Your account application was rejected. Please contact procurement support.", 'error')
            else:
                flash(f"Welcome back, {user['name']}!", 'success')
            return redirect(url_for('dashboard'))
        else:
            form_errors['general'] = 'Invalid email or password. Please verify your credentials.'
            flash('Invalid email or password. Please check your credentials.', 'error')
            return render_template('login.html', form_errors=form_errors, mode='login', active_role=active_role)

    return render_template('login.html', form_errors=form_errors, mode=mode, active_role=active_role)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Vendor Self-Registration route."""
    if get_current_user():
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        return handle_registration()

    return render_template('login.html', mode='register', form_errors={}, active_role='user')


def handle_registration():
    """Processes vendor registration with strict validation, secure hashing, and database persistence."""
    form_errors = {}
    name = request.form.get('name', '').strip()
    company = request.form.get('company', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')

    # Validations
    if not name:
        form_errors['name'] = "Contact person's name is required."
    if not company:
        form_errors['company'] = 'Business/company name is required.'
    if not email:
        form_errors['email'] = 'Business email address is required.'
    elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        form_errors['email'] = 'Please provide a valid business email address.'
    elif db.get_user_by_email(email):
        form_errors['email'] = 'An account with this email already exists.'

    if not phone:
        form_errors['phone'] = 'Contact phone number is required.'
    if not password:
        form_errors['password'] = 'Password is required.'
    elif len(password) < 6:
        form_errors['password'] = 'Password must be at least 6 characters.'
    if password != confirm_password:
        form_errors['confirm_password'] = 'Passwords do not match.'

    if form_errors:
        flash('Please correct the errors in the registration form below.', 'error')
        return render_template('login.html', mode='register', form_errors=form_errors, form_data=request.form, active_role='user')

    # Register into SQLite database (strictly role='vendor', status='pending')
    db.register_vendor_account(
        contact_name=name,
        company_name=company,
        email=email,
        phone=phone,
        password=password,
        initial_status='pending',
    )

    flash(
        'Your vendor registration was submitted successfully and awaits review by our procurement administration. '
        'You may log in to monitor your application status.',
        'success',
    )
    return redirect(url_for('login'))


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('You have been signed out successfully.', 'info')
    return redirect(url_for('login'))


# ── Dashboard & Profile ──
@app.route('/dashboard')
def dashboard():
    user = get_current_user()
    is_vendor = user and user.get('role') == 'vendor'

    stats = db.get_dashboard_stats(user)
    recent_rfqs = db.get_rfqs(user)[:4]
    recent_orders = db.get_purchase_orders(user)[:4]
    recent_activity = db.get_audit_logs(limit=10)
    pending_vendors, active_rfq_count, pending_approval_count = db.get_system_counts()

    return render_template('dashboard.html',
        active_page='dashboard',
        current_user=user,
        stats=stats,
        recent_activity=recent_activity if not is_vendor else [],
        pending_tasks=[],
        recent_rfqs=recent_rfqs,
        recent_orders=recent_orders,
        pending_vendor_count=pending_vendors if not is_vendor else 0,
        active_rfq_count=active_rfq_count,
        pending_approval_count=pending_approval_count if not is_vendor else 0,
    )


@app.route('/profile')
def profile():
    user = get_current_user()
    pending_vendors, active_rfq_count, pending_approval_count = db.get_system_counts()
    return render_template('dashboard.html',
        active_page='profile',
        current_user=user,
        pending_vendor_count=pending_vendors if (user and user.get('role') == 'admin') else 0,
        active_rfq_count=active_rfq_count,
        pending_approval_count=pending_approval_count if (user and user.get('role') == 'admin') else 0,
    )


@app.route('/profile/update', methods=['POST'])
def update_profile():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    name = request.form.get('name', user['name']).strip()
    phone = request.form.get('phone', user.get('phone', '')).strip()
    address = request.form.get('address', user.get('address', '')).strip()

    db.update_user_profile(user['id'], name=name, phone=phone, address=address)
    flash('Your profile changes have been saved successfully.', 'success')
    return redirect(url_for('profile'))


# ── Vendors Management & Filtering ──
@app.route('/vendors', methods=['GET'])
def vendors():
    user = get_current_user()
    is_vendor = user and user.get('role') == 'vendor'

    q = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    category_filter = request.args.get('category', '').strip()

    vendor_data = db.get_vendors(
        status=status_filter,
        category=category_filter,
        search=q,
        user_id=user['id'] if is_vendor else None,
    )

    pending_vendors, active_rfq_count, pending_approval_count = db.get_system_counts()

    return render_template('vendors.html',
        active_page='vendors',
        current_user=user,
        vendors=vendor_data,
        total_vendors=len(vendor_data),
        page=1,
        total_pages=1,
        pending_vendor_count=pending_vendors if not is_vendor else 0,
        active_rfq_count=active_rfq_count,
        pending_approval_count=pending_approval_count if not is_vendor else 0,
    )


@app.route('/vendors/register', methods=['POST'])
def register_vendor():
    """Admin-initiated vendor creation."""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Unauthorized: Only administrators can register vendors directly.', 'error')
        return redirect(url_for('vendors'))

    name = request.form.get('name', '').strip()
    company = request.form.get('company', '').strip() or name
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    category = request.form.get('category', 'supplies')
    tax_id = request.form.get('tax_id', '').strip()
    address = request.form.get('address', '').strip()

    if not name or not email:
        flash('Vendor name and email address are required.', 'error')
        return redirect(url_for('vendors'))

    if db.get_user_by_email(email):
        flash('An account with this email already exists.', 'error')
        return redirect(url_for('vendors'))

    db.register_vendor_account(
        contact_name=name,
        company_name=company,
        email=email,
        phone=phone,
        password='ChangeMe!2026',
        category=category,
        address=address,
        tax_id=tax_id,
        initial_status='pending',
        actor_user_id=user['id'],
    )

    flash(f"Vendor '{company}' registered successfully. Awaiting approval.", 'success')
    return redirect(url_for('vendors'))


@app.route('/vendors/<int:vendor_id>/approve', methods=['POST'])
def approve_vendor(vendor_id):
    """Admin approves a pending vendor registration."""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Unauthorized: Only administrators can approve vendor registrations.', 'error')
        return redirect(url_for('vendors'))

    success = db.approve_vendor_in_db(vendor_id, admin_user_id=user['id'])
    if not success:
        flash('Vendor not found.', 'error')
    else:
        flash("Vendor registration has been officially approved. Account is now active.", 'success')
    return redirect(url_for('vendors'))


@app.route('/vendors/<int:vendor_id>/reject', methods=['POST'])
def reject_vendor(vendor_id):
    """Admin rejects a vendor registration with recorded reason."""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Unauthorized: Only administrators can reject vendor registrations.', 'error')
        return redirect(url_for('vendors'))

    reason = request.form.get('reason', '').strip() or 'Registration criteria not met upon review.'
    success = db.reject_vendor_in_db(vendor_id, admin_user_id=user['id'], reason=reason)
    if not success:
        flash('Vendor not found.', 'error')
    else:
        flash("Vendor registration was rejected.", 'warning')
    return redirect(url_for('vendors'))


# ── Procurement Workspace & Dynamic Quotation Comparison ──
@app.route('/procurement')
def procurement():
    user = get_current_user()
    is_vendor = user and user.get('role') == 'vendor'
    active_tab = request.args.get('tab', 'rfqs')

    # Security: Vendors cannot access bid comparison or administrative approvals
    if is_vendor and active_tab in ['comparison', 'approvals']:
        flash('Restricted: Vendors cannot access comparative bidding analysis or administrative approvals.', 'warning')
        return redirect(url_for('procurement', tab='rfqs'))

    visible_rfqs = db.get_rfqs(user)
    visible_quotations = db.get_quotations(user)
    visible_pos = db.get_purchase_orders(user)

    compare_rfq_id = request.args.get('compare_rfq')
    selected_rfq = None
    comparison_data = None

    if compare_rfq_id and not is_vendor:
        selected_rfq = db.get_rfq_by_id(compare_rfq_id)
    elif active_tab == 'comparison' and not is_vendor and visible_rfqs:
        selected_rfq = next((r for r in visible_rfqs if r.get('bid_count', 0) > 0), visible_rfqs[0])

    if selected_rfq and not is_vendor:
        comparison_data = db.get_quotation_comparison(selected_rfq['id'])

    pending_approvals = db.get_pending_approvals() if not is_vendor else []
    approved_vendors = db.get_vendors(status='approved') if not is_vendor else []
    pending_vendors, active_rfq_count, pending_approval_count = db.get_system_counts()

    return render_template('procurement.html',
        active_page='procurement',
        active_tab=active_tab,
        current_user=user,
        rfqs=visible_rfqs,
        invitations=[],
        quotations=visible_quotations,
        comparison_data=comparison_data,
        selected_rfq=selected_rfq,
        pending_approvals=pending_approvals,
        purchase_orders=visible_pos,
        procurement_history=[],
        approved_vendors=approved_vendors,
        pending_vendor_count=pending_vendors if not is_vendor else 0,
        active_rfq_count=active_rfq_count,
        pending_approval_count=pending_approval_count if not is_vendor else 0,
    )


@app.route('/procurement/rfq/create', methods=['POST'])
def create_rfq():
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Unauthorized: Only procurement officers can create RFQs.', 'error')
        return redirect(url_for('procurement', tab='rfqs'))

    title = request.form.get('title', '').strip()
    budget = request.form.get('budget', '').strip()
    deadline = request.form.get('deadline', '').strip()
    description = request.form.get('description', '').strip()

    if not title:
        flash('RFQ title is required.', 'error')
        return redirect(url_for('procurement', tab='rfqs'))

    db.create_rfq_in_db(
        title=title,
        description=description,
        deadline=deadline or (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d"),
        created_by_user_id=user['id'],
        budget=budget,
    )

    flash("Request for Quotation created successfully.", 'success')
    return redirect(url_for('procurement', tab='rfqs'))


@app.route('/procurement/invitation/send', methods=['POST'])
def send_invitation():
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Unauthorized: Only administrators can send vendor invitations.', 'error')
        return redirect(url_for('procurement', tab='invitations'))

    rfq_id = request.form.get('rfq_id')
    vendor_name = request.form.get('vendor_name', '').strip()

    rfq = db.get_rfq_by_id(rfq_id)
    all_vendors = db.get_vendors()
    vendor = next((v for v in all_vendors if v['company'] == vendor_name or str(v['id']) == vendor_name), None)

    if rfq and vendor:
        db.invite_vendor_to_rfq(rfq['id'], vendor['id'], admin_user_id=user['id'])
        flash(f"Invitation sent to {vendor['company']} for tender {rfq['number']}.", 'success')
    else:
        flash('Please select a valid RFQ and approved vendor partner.', 'error')

    return redirect(url_for('procurement', tab='invitations'))


@app.route('/procurement/quotation/submit', methods=['POST'])
def submit_quotation():
    """Allows eligible approved vendors to submit quotation bids before deadline."""
    user = get_current_user()
    if not user or user.get('role') != 'vendor':
        flash('Unauthorized: Only authorized vendors can submit quotation bids.', 'error')
        return redirect(url_for('procurement', tab='quotations'))

    status_val = (user.get('status') or '').lower()
    if status_val not in ('active', 'approved'):
        flash('Your vendor account is pending verification. You cannot submit quotations until approved.', 'error')
        return redirect(url_for('procurement', tab='quotations'))

    rfq_id_str = request.form.get('rfq_id', '')
    rfq = db.get_rfq_by_id(rfq_id_str)

    if not rfq:
        flash('Selected RFQ tender does not exist.', 'error')
        return redirect(url_for('procurement', tab='quotations'))

    if rfq.get('is_overdue') or rfq.get('status') != 'open':
        flash('Quotation submission closed: The deadline for this RFQ has already passed.', 'error')
        return redirect(url_for('procurement', tab='quotations'))

    # Check invitation if restricted
    vendor_company = user.get('company') or user.get('name')
    if rfq.get('invited_vendors') and vendor_company not in rfq['invited_vendors']:
        flash('Your organization has not been invited to submit bids for this specific RFQ.', 'error')
        return redirect(url_for('procurement', tab='quotations'))

    price_str = request.form.get('total_price', '').strip()
    delivery_days = request.form.get('delivery_days', '14').strip()
    notes = request.form.get('notes', '').strip()

    if not price_str or not delivery_days:
        flash('Quoted price and delivery days are required.', 'error')
        return redirect(url_for('procurement', tab='quotations'))

    db.submit_quotation_in_db(
        rfq_id=rfq['id'],
        vendor_id=user['vendor_id'],
        total_price=price_str,
        delivery_days=int(delivery_days) if delivery_days.isdigit() else 14,
        notes=notes,
    )

    flash(f"Quotation submitted successfully for tender {rfq['number']}.", 'success')
    return redirect(url_for('procurement', tab='quotations'))


@app.route('/procurement/quotation/select', methods=['POST'])
def select_quotation():
    """Procurement admin selects a quotation from comparison to submit for approval."""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Unauthorized: Only procurement officers can select quotations for approval.', 'error')
        return redirect(url_for('procurement', tab='rfqs'))

    quote_id = request.form.get('quotation_id')
    if not quote_id:
        flash('Selected quotation could not be found.', 'error')
        return redirect(url_for('procurement', tab='comparison'))

    success = db.select_quotation_for_approval(int(quote_id), admin_user_id=user['id'])
    if success:
        flash("Quotation bid selected and advanced to the approval queue.", 'success')
        return redirect(url_for('procurement', tab='approvals'))
    else:
        flash('Quotation could not be selected.', 'error')
        return redirect(url_for('procurement', tab='comparison'))


@app.route('/procurement/approve', methods=['POST'])
def approve_procurement():
    """Authorizes procurement proposal and generates official Purchase Order."""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Unauthorized: Only administrators can authorize procurement proposals.', 'error')
        return redirect(url_for('procurement', tab='approvals'))

    action = request.form.get('action', 'approve')
    approval_id = request.form.get('approval_id')

    if not approval_id:
        flash('Approval record could not be found.', 'error')
        return redirect(url_for('procurement', tab='approvals'))

    if action == 'approve':
        po_num = db.authorize_procurement_proposal(int(approval_id), admin_user_id=user['id'])
        if po_num:
            flash(f"Procurement proposal authorized! Purchase Order {po_num} generated successfully.", 'success')
            return redirect(url_for('procurement', tab='orders'))
        else:
            flash('Approval record could not be found or was already authorized.', 'error')
            return redirect(url_for('procurement', tab='approvals'))
    else:
        db.reject_procurement_proposal(int(approval_id), admin_user_id=user['id'])
        flash('Procurement proposal rejected.', 'warning')
        return redirect(url_for('procurement', tab='approvals'))


# ── Finance & Invoice Verification ──
@app.route('/finance')
def finance():
    user = get_current_user()
    is_vendor = user and user.get('role') == 'vendor'
    active_tab = request.args.get('tab', 'invoices')

    # Security: Vendors cannot access administrative audit trails
    if is_vendor and active_tab == 'audit':
        flash('Restricted: Audit trail records are reserved for internal accounting administration.', 'warning')
        return redirect(url_for('finance', tab='invoices'))

    q = request.args.get('q', '').strip()
    v_status = request.args.get('verification_status', '').strip()
    p_status = request.args.get('payment_status', '').strip()

    invoices = db.get_invoices(user=user, verification_status=v_status, payment_status=p_status, search=q)
    payments = db.get_payment_records(user=user)
    orders = db.get_purchase_orders(user=user)
    audit_records = db.get_audit_logs(limit=50) if not is_vendor else []

    pending_vendors, active_rfq_count, pending_approval_count = db.get_system_counts()

    return render_template('finance.html',
        active_page='finance',
        active_tab=active_tab,
        current_user=user,
        finance_stats={
            'total_invoices': len(invoices),
            'pending_verification': sum(1 for i in invoices if i['verification_status'] == 'pending'),
            'unpaid': sum(1 for i in invoices if i['payment_status'] != 'paid'),
            'total_paid': sum(1 for i in invoices if i['payment_status'] == 'paid'),
        },
        invoices=invoices,
        payment_records=payments,
        audit_logs=audit_records,
        purchase_orders=orders,
        approved_vendors=db.get_vendors(status='approved') if not is_vendor else [],
        pending_vendor_count=pending_vendors if not is_vendor else 0,
        active_rfq_count=active_rfq_count,
        pending_approval_count=pending_approval_count if not is_vendor else 0,
    )


@app.route('/finance/invoice/register', methods=['POST'])
def register_invoice():
    user = get_current_user()
    inv_num = request.form.get('invoice_number', '').strip()
    po_num = request.form.get('po_number', '').strip()
    amount_str = request.form.get('amount', '').strip()

    if not inv_num or not po_num:
        flash('Invoice number and valid PO reference are required.', 'error')
        return redirect(url_for('finance', tab='invoices'))

    try:
        inv_id, has_mismatch, mismatch_reason = db.register_invoice_in_db(
            invoice_number=inv_num,
            po_number=po_num,
            amount_str=amount_str,
            user_id=user['id'] if user else None,
        )
        if has_mismatch:
            flash(f"Invoice {inv_num} registered with warning: PO mismatch detected! Awaiting review.", 'warning')
        else:
            flash(f"Invoice {inv_num} registered successfully and matched against {po_num}.", 'success')
    except Exception as e:
        flash(f"Failed to register invoice: {str(e)}", 'error')

    return redirect(url_for('finance', tab='invoices'))


@app.route('/finance/invoice/verify', methods=['POST'])
def verify_invoice():
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Unauthorized: Only finance officers can verify supplier invoices.', 'error')
        return redirect(url_for('finance', tab='invoices'))

    action = request.form.get('action', 'verify')
    inv_id = request.form.get('invoice_id')

    if not inv_id:
        flash('Invoice record not found.', 'error')
        return redirect(url_for('finance', tab='invoices'))

    db.verify_invoice_in_db(int(inv_id), admin_user_id=user['id'], action=action)
    if action == 'verify':
        flash("Invoice verified successfully against Purchase Order.", 'success')
    else:
        flash("Invoice rejected. Discrepancy noted.", 'warning')

    return redirect(url_for('finance', tab='invoices'))


@app.route('/finance/payment/update', methods=['POST'])
def update_payment():
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Unauthorized: Only finance officers can record payment updates.', 'error')
        return redirect(url_for('finance', tab='payments'))

    inv_id = request.form.get('invoice_id')
    status = request.form.get('status', 'paid')

    if not inv_id:
        flash('Invoice record not found.', 'error')
        return redirect(url_for('finance', tab='payments'))

    db.record_payment_in_db(int(inv_id), admin_user_id=user['id'], status=status)
    flash(f"Payment record updated to {status.title()}.", 'success')
    return redirect(url_for('finance', tab='payments'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)
