"""
database.py
------------------------------------------------------------
Handles all SQLite database connections and initialization
for the KMRL Document Management System.
------------------------------------------------------------
"""

import sqlite3
import os
from werkzeug.security import generate_password_hash

DATABASE_NAME = "kmrl_documents.db"
SCHEMA_FILE = "schema.sql"


def get_db_connection():
    """
    Creates and returns a new SQLite database connection.
    Row factory is set so rows behave like dictionaries.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """
    Initializes the database using schema.sql if the database
    file does not already exist. Also seeds a default admin
    account (Employee ID: ADMIN001 / Password: admin123).
    """
    db_exists = os.path.exists(DATABASE_NAME)

    conn = get_db_connection()

    if not db_exists:
        with open(SCHEMA_FILE, "r") as f:
            conn.executescript(f.read())
        conn.commit()

        # Seed default admin account with a properly hashed password
        hashed_pw = generate_password_hash("admin123")
        conn.execute(
            """INSERT INTO users
               (employee_id, name, email, department, role, password, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("ADMIN001", "System Administrator", "admin@kmrl.co.in",
             "IT", "Admin", hashed_pw, "Approved")
        )
        conn.commit()
        print("Database initialized with default admin (ADMIN001 / admin123)")

    conn.close()


def log_audit(action, username, document=""):
    """
    Inserts a record into the audit_log table.
    """
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO audit_log (action, username, document) VALUES (?, ?, ?)",
        (action, username, document)
    )
    conn.commit()
    conn.close()
