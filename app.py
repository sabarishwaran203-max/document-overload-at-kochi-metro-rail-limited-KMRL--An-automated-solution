"""
app.py
------------------------------------------------------------
KMRL Document Management System
Main Flask Application - Routes & Business Logic
------------------------------------------------------------
An automated document management solution for
Kochi Metro Rail Limited (KMRL) to solve document overload
issues across departments.
------------------------------------------------------------
"""

import os
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, send_from_directory, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from database import get_db_connection, init_db, log_audit

# ------------------------------------------------------------
# App Configuration
# ------------------------------------------------------------
app = Flask(__name__)
app.secret_key = "kmrl_secret_key_change_in_production_2026"

UPLOAD_FOLDER = os.path.join("static", "uploads")
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx",
                       "png", "jpg", "jpeg", "gif"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB max upload

DEPARTMENTS = ["Civil", "Electrical", "Mechanical", "Operations",
               "Finance", "HR", "Signal", "IT", "Rolling Stock",
               "Stores", "Safety"]

CATEGORIES = ["Circular", "Report", "Tender", "Drawing", "Policy",
              "Invoice", "Manual", "Memo", "Contract", "Other"]


# ------------------------------------------------------------
# Helper functions & decorators
# ------------------------------------------------------------
def allowed_file(filename):
    """Checks whether the uploaded file extension is permitted."""
    return "." in filename and \
        filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    """Ensures a user is logged in before accessing a route."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Ensures the logged-in user has an Admin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "danger")
            return redirect(url_for("login"))
        if session.get("role") != "Admin":
            flash("Access denied. Admins only.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated


# ------------------------------------------------------------
# Authentication Routes
# ------------------------------------------------------------
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        employee_id = request.form.get("employee_id", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE employee_id = ?", (employee_id,)
        ).fetchone()
        conn.close()

        if user is None or not check_password_hash(user["password"], password):
            flash("Invalid Employee ID or Password.", "danger")
            log_audit("Login Failed", employee_id)
            return redirect(url_for("login"))

        if user["status"] != "Approved":
            flash("Your account is pending admin approval.", "warning")
            return redirect(url_for("login"))

        session["user_id"] = user["id"]
        session["name"] = user["name"]
        session["employee_id"] = user["employee_id"]
        session["role"] = user["role"]
        session["department"] = user["department"]

        log_audit("Login Success", user["employee_id"])
        flash(f"Welcome back, {user['name']}!", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        employee_id = request.form.get("employee_id", "").strip()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        department = request.form.get("department", "")
        role = request.form.get("role", "Employee")
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not all([employee_id, name, email, department, password]):
            flash("All fields are required.", "danger")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return redirect(url_for("register"))

        conn = get_db_connection()
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ? OR employee_id = ?",
            (email, employee_id)
        ).fetchone()

        if existing:
            flash("An account with this Email or Employee ID already exists.", "danger")
            conn.close()
            return redirect(url_for("register"))

        hashed_pw = generate_password_hash(password)
        conn.execute(
            """INSERT INTO users
               (employee_id, name, email, department, role, password, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (employee_id, name, email, department, role, hashed_pw, "Approved")
        )
        conn.commit()
        conn.close()

        log_audit("User Registered", employee_id)
        flash("Registration successful! You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", departments=DEPARTMENTS)


@app.route("/logout")
def logout():
    employee_id = session.get("employee_id", "unknown")
    log_audit("Logout", employee_id)
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("login"))


# ------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db_connection()

    total_documents = conn.execute(
        "SELECT COUNT(*) AS c FROM documents").fetchone()["c"]
    pending = conn.execute(
        "SELECT COUNT(*) AS c FROM documents WHERE status = 'Pending'").fetchone()["c"]
    approved = conn.execute(
        "SELECT COUNT(*) AS c FROM documents WHERE status = 'Approved'").fetchone()["c"]
    rejected = conn.execute(
        "SELECT COUNT(*) AS c FROM documents WHERE status = 'Rejected'").fetchone()["c"]

    recent_uploads = conn.execute(
        "SELECT * FROM documents ORDER BY upload_date DESC LIMIT 5"
    ).fetchall()

    dept_rows = conn.execute(
        """SELECT department, COUNT(*) AS total
           FROM documents GROUP BY department"""
    ).fetchall()

    category_rows = conn.execute(
        """SELECT category, COUNT(*) AS total
           FROM documents GROUP BY category"""
    ).fetchall()

    conn.close()

    dept_labels = [row["department"] for row in dept_rows]
    dept_values = [row["total"] for row in dept_rows]
    cat_labels = [row["category"] for row in category_rows]
    cat_values = [row["total"] for row in category_rows]

    return render_template(
        "dashboard.html",
        total_documents=total_documents,
        pending=pending,
        approved=approved,
        rejected=rejected,
        recent_uploads=recent_uploads,
        dept_labels=dept_labels,
        dept_values=dept_values,
        cat_labels=cat_labels,
        cat_values=cat_values
    )


# ------------------------------------------------------------
# Upload Document
# ------------------------------------------------------------
@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        department = request.form.get("department", "")
        category = request.form.get("category", "")
        version = request.form.get("version", "1.0").strip()
        tags = request.form.get("tags", "").strip()

        file = request.files.get("document_file")

        if not title or not department or not category:
            flash("Please fill in all required fields.", "danger")
            return redirect(url_for("upload"))

        if file is None or file.filename == "":
            flash("Please select a file to upload.", "danger")
            return redirect(url_for("upload"))

        if not allowed_file(file.filename):
            flash("Invalid file type. Allowed: PDF, Word, Excel, Images.", "danger")
            return redirect(url_for("upload"))

        original_filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        stored_filename = f"{timestamp}_{original_filename}"

        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], stored_filename)
        file.save(filepath)
        file_size = os.path.getsize(filepath)

        conn = get_db_connection()
        conn.execute(
            """INSERT INTO documents
               (title, description, filename, original_filename, category,
                department, uploaded_by, version, tags, status, file_size)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, description, stored_filename, original_filename, category,
             department, session["name"], version, tags, "Pending", file_size)
        )
        conn.commit()
        conn.close()

        log_audit("Document Uploaded", session["employee_id"], title)
        flash("Document uploaded successfully and is pending approval.", "success")
        return redirect(url_for("documents"))

    return render_template("upload.html", departments=DEPARTMENTS, categories=CATEGORIES)


# ------------------------------------------------------------
# View All Documents
# ------------------------------------------------------------
@app.route("/documents")
@login_required
def documents():
    conn = get_db_connection()
    all_documents = conn.execute(
        "SELECT * FROM documents ORDER BY upload_date DESC"
    ).fetchall()
    conn.close()
    return render_template("documents.html", documents=all_documents,
                            departments=DEPARTMENTS, categories=CATEGORIES)


# ------------------------------------------------------------
# Search Documents
# ------------------------------------------------------------
@app.route("/search")
@login_required
def search():
    query = request.args.get("q", "").strip()
    results = []

    if query:
        conn = get_db_connection()
        like_query = f"%{query}%"
        results = conn.execute(
            """SELECT * FROM documents
               WHERE title LIKE ? OR category LIKE ? OR department LIKE ?
                  OR tags LIKE ? OR original_filename LIKE ?
                  OR uploaded_by LIKE ? OR status LIKE ?
               ORDER BY upload_date DESC""",
            (like_query, like_query, like_query, like_query,
             like_query, like_query, like_query)
        ).fetchall()
        conn.close()

    return render_template("search.html", results=results, query=query)


@app.route("/api/search")
@login_required
def api_search():
    """JSON endpoint used for instant client-side search suggestions."""
    query = request.args.get("q", "").strip()
    conn = get_db_connection()
    like_query = f"%{query}%"
    rows = conn.execute(
        """SELECT id, title, category, department, status FROM documents
           WHERE title LIKE ? OR tags LIKE ? LIMIT 10""",
        (like_query, like_query)
    ).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


# ------------------------------------------------------------
# Document Details / Download / Delete / Edit
# ------------------------------------------------------------
@app.route("/document/<int:doc_id>")
@login_required
def document_details(doc_id):
    conn = get_db_connection()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    approvals = conn.execute(
        "SELECT * FROM approvals WHERE document_id = ? ORDER BY date DESC", (doc_id,)
    ).fetchall()
    conn.close()

    if doc is None:
        flash("Document not found.", "danger")
        return redirect(url_for("documents"))

    return render_template("edit_document.html", doc=doc, approvals=approvals,
                            departments=DEPARTMENTS, categories=CATEGORIES)


@app.route("/document/<int:doc_id>/edit", methods=["POST"])
@login_required
def edit_document(doc_id):
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    department = request.form.get("department", "")
    category = request.form.get("category", "")
    version = request.form.get("version", "").strip()
    tags = request.form.get("tags", "").strip()

    conn = get_db_connection()
    conn.execute(
        """UPDATE documents
           SET title = ?, description = ?, department = ?, category = ?,
               version = ?, tags = ?
           WHERE id = ?""",
        (title, description, department, category, version, tags, doc_id)
    )
    conn.commit()
    conn.close()

    log_audit("Document Edited", session["employee_id"], title)
    flash("Document metadata updated successfully.", "success")
    return redirect(url_for("document_details", doc_id=doc_id))


@app.route("/document/<int:doc_id>/download")
@login_required
def download_document(doc_id):
    conn = get_db_connection()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()

    if doc is None:
        flash("Document not found.", "danger")
        return redirect(url_for("documents"))

    log_audit("Document Downloaded", session["employee_id"], doc["title"])
    return send_from_directory(
        app.config["UPLOAD_FOLDER"], doc["filename"],
        as_attachment=True, download_name=doc["original_filename"]
    )


@app.route("/document/<int:doc_id>/delete", methods=["POST"])
@login_required
def delete_document(doc_id):
    conn = get_db_connection()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()

    if doc:
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], doc["filename"])
        if os.path.exists(filepath):
            os.remove(filepath)

        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
        log_audit("Document Deleted", session["employee_id"], doc["title"])
        flash("Document deleted successfully.", "success")
    else:
        flash("Document not found.", "danger")

    conn.close()
    return redirect(url_for("documents"))


@app.route("/document/<int:doc_id>/approve", methods=["POST"])
@login_required
@admin_required
def approve_document(doc_id):
    remarks = request.form.get("remarks", "")

    conn = get_db_connection()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()

    conn.execute("UPDATE documents SET status = 'Approved' WHERE id = ?", (doc_id,))
    conn.execute(
        """INSERT INTO approvals (document_id, approved_by, status, remarks)
           VALUES (?, ?, ?, ?)""",
        (doc_id, session["name"], "Approved", remarks)
    )
    conn.commit()
    conn.close()

    log_audit("Document Approved", session["employee_id"], doc["title"] if doc else "")
    flash("Document approved successfully.", "success")
    return redirect(url_for("document_details", doc_id=doc_id))


@app.route("/document/<int:doc_id>/reject", methods=["POST"])
@login_required
@admin_required
def reject_document(doc_id):
    remarks = request.form.get("remarks", "")

    conn = get_db_connection()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()

    conn.execute("UPDATE documents SET status = 'Rejected' WHERE id = ?", (doc_id,))
    conn.execute(
        """INSERT INTO approvals (document_id, approved_by, status, remarks)
           VALUES (?, ?, ?, ?)""",
        (doc_id, session["name"], "Rejected", remarks)
    )
    conn.commit()
    conn.close()

    log_audit("Document Rejected", session["employee_id"], doc["title"] if doc else "")
    flash("Document rejected.", "warning")
    return redirect(url_for("document_details", doc_id=doc_id))


# ------------------------------------------------------------
# Profile
# ------------------------------------------------------------
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    conn = get_db_connection()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        department = request.form.get("department", "")

        conn.execute(
            "UPDATE users SET name = ?, email = ?, department = ? WHERE id = ?",
            (name, email, department, session["user_id"])
        )
        conn.commit()

        session["name"] = name
        session["department"] = department

        flash("Profile updated successfully.", "success")
        return redirect(url_for("profile"))

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()
    my_documents = conn.execute(
        "SELECT * FROM documents WHERE uploaded_by = ? ORDER BY upload_date DESC",
        (session["name"],)
    ).fetchall()
    conn.close()

    return render_template("profile.html", user=user, documents=my_documents,
                            departments=DEPARTMENTS)


@app.route("/profile/change-password", methods=["POST"])
@login_required
def change_password():
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()

    if not check_password_hash(user["password"], current_password):
        flash("Current password is incorrect.", "danger")
        conn.close()
        return redirect(url_for("profile"))

    if new_password != confirm_password:
        flash("New passwords do not match.", "danger")
        conn.close()
        return redirect(url_for("profile"))

    if len(new_password) < 6:
        flash("Password must be at least 6 characters long.", "danger")
        conn.close()
        return redirect(url_for("profile"))

    hashed_pw = generate_password_hash(new_password)
    conn.execute("UPDATE users SET password = ? WHERE id = ?",
                 (hashed_pw, session["user_id"]))
    conn.commit()
    conn.close()

    flash("Password changed successfully.", "success")
    return redirect(url_for("profile"))


# ------------------------------------------------------------
# Admin Panel
# ------------------------------------------------------------
@app.route("/admin")
@login_required
@admin_required
def admin():
    conn = get_db_connection()

    users = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    all_documents = conn.execute(
        "SELECT * FROM documents ORDER BY upload_date DESC"
    ).fetchall()
    audit_logs = conn.execute(
        "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 50"
    ).fetchall()

    total_users = len(users)
    total_documents = len(all_documents)
    pending_count = conn.execute(
        "SELECT COUNT(*) AS c FROM documents WHERE status = 'Pending'").fetchone()["c"]

    conn.close()

    return render_template(
        "admin.html", users=users, documents=all_documents,
        audit_logs=audit_logs, total_users=total_users,
        total_documents=total_documents, pending_count=pending_count
    )


@app.route("/admin/user/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    if user and user["employee_id"] != session.get("employee_id"):
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        log_audit("User Deleted", session["employee_id"], user["employee_id"])
        flash("User deleted successfully.", "success")
    else:
        flash("Cannot delete this user.", "danger")

    conn.close()
    return redirect(url_for("admin"))


@app.route("/admin/user/<int:user_id>/approve", methods=["POST"])
@login_required
@admin_required
def approve_user(user_id):
    conn = get_db_connection()
    conn.execute("UPDATE users SET status = 'Approved' WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    log_audit("User Approved", session["employee_id"], str(user_id))
    flash("User approved successfully.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/user/<int:user_id>/make-admin", methods=["POST"])
@login_required
@admin_required
def make_admin(user_id):
    conn = get_db_connection()
    conn.execute("UPDATE users SET role = 'Admin' WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    flash("User promoted to Admin.", "success")
    return redirect(url_for("admin"))


# ------------------------------------------------------------
# Reports
# ------------------------------------------------------------
@app.route("/reports")
@login_required
def reports():
    conn = get_db_connection()

    total_documents = conn.execute(
        "SELECT COUNT(*) AS c FROM documents").fetchone()["c"]

    dept_report = conn.execute(
        """SELECT department, COUNT(*) AS total,
                  SUM(CASE WHEN status = 'Approved' THEN 1 ELSE 0 END) AS approved,
                  SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) AS pending,
                  SUM(CASE WHEN status = 'Rejected' THEN 1 ELSE 0 END) AS rejected
           FROM documents GROUP BY department"""
    ).fetchall()

    category_report = conn.execute(
        """SELECT category, COUNT(*) AS total
           FROM documents GROUP BY category"""
    ).fetchall()

    monthly_report = conn.execute(
        """SELECT strftime('%Y-%m', upload_date) AS month, COUNT(*) AS total
           FROM documents GROUP BY month ORDER BY month"""
    ).fetchall()

    conn.close()

    return render_template(
        "search.html",  # reuse layout intentionally avoided; use dedicated block below
        results=[], query="", is_report=True,
        total_documents=total_documents, dept_report=dept_report,
        category_report=category_report, monthly_report=monthly_report
    )


# ------------------------------------------------------------
# Error Handlers
# ------------------------------------------------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


# ------------------------------------------------------------
# App Entry Point
# ------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    app.run(debug=True, host="0.0.0.0", port=5000)
