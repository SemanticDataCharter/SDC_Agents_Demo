#!/usr/bin/env python3
"""Build the employees SQLite database for the SDC Agents Demo.

Run:
    python scripts/build_employees_db.py

Produces: data/employees.db
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "employees.db"


def build() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # --- departments ---
    cur.execute("""
        CREATE TABLE departments (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT NOT NULL UNIQUE,
            location  TEXT NOT NULL,
            budget    REAL CHECK (budget > 0)
        )
    """)

    departments = [
        ("Engineering", "Building A, Floor 3", 1_200_000.00),
        ("Marketing", "Building B, Floor 1", 450_000.00),
        ("Finance", "Building A, Floor 2", 600_000.00),
        ("Human Resources", "Building C, Floor 1", 350_000.00),
    ]
    cur.executemany(
        "INSERT INTO departments (name, location, budget) VALUES (?, ?, ?)",
        departments,
    )

    # --- employees ---
    cur.execute("""
        CREATE TABLE employees (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name  TEXT NOT NULL,
            email      TEXT NOT NULL UNIQUE,
            hire_date  TEXT NOT NULL,
            salary     REAL NOT NULL CHECK (salary >= 30000),
            dept_id    INTEGER REFERENCES departments(id),
            is_active  INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
        )
    """)

    employees = [
        ("Alice", "Chen", "alice.chen@example.com", "2021-03-15", 95000, 1, 1),
        ("Bob", "Martinez", "bob.martinez@example.com", "2020-07-01", 88000, 1, 1),
        ("Carol", "Williams", "carol.williams@example.com", "2019-11-20", 110000, 1, 1),
        ("David", "Kim", "david.kim@example.com", "2022-01-10", 72000, 2, 1),
        ("Eva", "Johnson", "eva.johnson@example.com", "2023-06-05", 65000, 2, 1),
        ("Frank", "Brown", "frank.brown@example.com", "2018-09-12", 98000, 3, 1),
        ("Grace", "Lee", "grace.lee@example.com", "2021-04-22", 82000, 3, 1),
        ("Henry", "Davis", "henry.davis@example.com", "2020-02-28", 75000, 4, 1),
        ("Iris", "Wilson", "iris.wilson@example.com", "2017-08-14", 105000, 1, 1),
        ("Jack", "Taylor", "jack.taylor@example.com", "2022-05-30", 68000, 2, 1),
        ("Karen", "Anderson", "karen.anderson@example.com", "2019-12-01", 92000, 1, 1),
        ("Liam", "Thomas", "liam.thomas@example.com", "2023-09-18", 60000, 4, 1),
        ("Mia", "Jackson", "mia.jackson@example.com", "2016-03-07", 115000, 1, 0),
        ("Noah", "White", "noah.white@example.com", "2021-07-25", 78000, 3, 1),
        ("Olivia", "Harris", "olivia.harris@example.com", "2020-10-11", 87000, 2, 1),
        ("Peter", "Clark", "peter.clark@example.com", "2024-01-08", 55000, 4, 1),
        ("Quinn", "Lewis", "quinn.lewis@example.com", "2022-11-15", 71000, 3, 1),
        ("Rachel", "Robinson", "rachel.robinson@example.com", "2018-06-20", 99000, 1, 1),
        ("Sam", "Walker", "sam.walker@example.com", "2023-03-12", 63000, 2, 0),
        ("Tina", "Hall", "tina.hall@example.com", "2019-04-30", 91000, 1, 1),
    ]
    cur.executemany(
        "INSERT INTO employees (first_name, last_name, email, hire_date, salary, dept_id, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
        employees,
    )

    conn.commit()
    conn.close()

    print(f"[OK] Created {DB_PATH} ({DB_PATH.stat().st_size:,} bytes)")
    print(f"     departments: {len(departments)} rows")
    print(f"     employees:   {len(employees)} rows")


if __name__ == "__main__":
    build()
