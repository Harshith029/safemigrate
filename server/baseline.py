import os
import json

from models import MigrationAction
from server.environment import SafeMigrateEnvironment
from server.grader import grade_episode
from tasks import TASKS


EASY_STEPS = [
    MigrationAction(command="inspect_schema"),
    MigrationAction(command="plan", plan="Add three columns to employees: email (TEXT nullable), hire_date (TEXT nullable), is_active (INTEGER DEFAULT 1). Use ALTER TABLE for each. Then UPDATE is_active to 1 for all rows."),
    MigrationAction(command="create_savepoint", savepoint_name="before_migration"),
    MigrationAction(command="execute_sql", sql="ALTER TABLE employees ADD COLUMN email TEXT"),
    MigrationAction(command="execute_sql", sql="ALTER TABLE employees ADD COLUMN hire_date TEXT"),
    MigrationAction(command="execute_sql", sql="ALTER TABLE employees ADD COLUMN is_active INTEGER DEFAULT 1"),
    MigrationAction(command="execute_sql", sql="UPDATE employees SET is_active = 1 WHERE is_active IS NULL"),
    MigrationAction(command="validate_schema"),
    MigrationAction(command="finish"),
]

MEDIUM_STEPS = [
    MigrationAction(command="inspect_schema"),
    MigrationAction(command="inspect_data", table="users"),
    MigrationAction(command="inspect_data", table="orders"),
    MigrationAction(command="plan", plan="1. Create addresses table with FK to users. 2. Copy city/country from users to addresses. 3. Recreate users without city/country. 4. Create order_items table. 5. Create new orders table without product columns. 6. Migrate order data preserving relationships."),
    MigrationAction(command="create_savepoint", savepoint_name="before_normalize"),
    MigrationAction(command="execute_sql", sql="CREATE TABLE addresses (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, city TEXT, country TEXT, FOREIGN KEY (user_id) REFERENCES users(id))"),
    MigrationAction(command="execute_sql", sql="INSERT INTO addresses (user_id, city, country) SELECT id, city, country FROM users"),
    MigrationAction(command="execute_sql", sql="CREATE TABLE new_users (id INTEGER PRIMARY KEY, full_name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, created_at TEXT DEFAULT '2024-01-01')"),
    MigrationAction(command="execute_sql", sql="INSERT INTO new_users SELECT id, full_name, email, created_at FROM users"),
    MigrationAction(command="execute_sql", sql="PRAGMA foreign_keys = OFF"),
    MigrationAction(command="execute_sql", sql="DROP TABLE users"),
    MigrationAction(command="execute_sql", sql="ALTER TABLE new_users RENAME TO users"),
    MigrationAction(command="execute_sql", sql="PRAGMA foreign_keys = ON"),
    MigrationAction(command="execute_sql", sql="CREATE TABLE order_items (id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL, product_name TEXT NOT NULL, quantity INTEGER NOT NULL DEFAULT 1, price REAL NOT NULL, FOREIGN KEY (order_id) REFERENCES orders(id))"),
    MigrationAction(command="execute_sql", sql="CREATE TABLE new_orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, order_date TEXT NOT NULL, FOREIGN KEY (user_id) REFERENCES users(id))"),
    MigrationAction(command="execute_sql", sql="INSERT INTO new_orders (user_id, order_date) SELECT DISTINCT user_id, order_date FROM orders"),
    MigrationAction(command="execute_sql", sql="INSERT INTO order_items (order_id, product_name, quantity, price) SELECT no.id, o.product_name, o.quantity, o.price FROM orders o JOIN new_orders no ON o.user_id = no.user_id AND o.order_date = no.order_date"),
    MigrationAction(command="execute_sql", sql="PRAGMA foreign_keys = OFF"),
    MigrationAction(command="execute_sql", sql="DROP TABLE orders"),
    MigrationAction(command="execute_sql", sql="ALTER TABLE new_orders RENAME TO orders"),
    MigrationAction(command="execute_sql", sql="PRAGMA foreign_keys = ON"),
    MigrationAction(command="validate_schema"),
    MigrationAction(command="finish"),
]

HARD_STEPS = [
    MigrationAction(command="inspect_schema"),
    MigrationAction(command="inspect_data", table="products"),
    MigrationAction(command="inspect_data", table="sales"),
    MigrationAction(command="plan", plan="1. Create suppliers table from DISTINCT supplier data, case-insensitive dedup (techcorp=TechCorp). Handle NULLs. 2. Create categories from DISTINCT category+subcategory. 3. Create stock_levels from product inventory. 4. Rebuild products with supplier_id and category_id FKs. 5. Preserve NULL supplier for product #9. 6. Drop old columns."),
    MigrationAction(command="create_savepoint", savepoint_name="before_restructure"),
    MigrationAction(command="execute_sql", sql="CREATE TABLE suppliers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT, country TEXT)"),
    MigrationAction(command="execute_sql", sql="""
        INSERT INTO suppliers (name, email, country)
        SELECT DISTINCT
            CASE WHEN LOWER(supplier_name) = 'techcorp' THEN 'TechCorp' ELSE supplier_name END,
            CASE WHEN LOWER(supplier_name) = 'techcorp' THEN 'sales@techcorp.com' ELSE supplier_email END,
            CASE WHEN LOWER(supplier_name) = 'techcorp' THEN 'USA' ELSE supplier_country END
        FROM products
        WHERE supplier_name IS NOT NULL
        GROUP BY LOWER(supplier_name)
    """),
    MigrationAction(command="execute_sql", sql="CREATE TABLE categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, subcategory TEXT)"),
    MigrationAction(command="execute_sql", sql="INSERT INTO categories (name, subcategory) SELECT DISTINCT category, subcategory FROM products"),
    MigrationAction(command="execute_sql", sql="CREATE TABLE stock_levels (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, quantity INTEGER DEFAULT 0, reorder_level INTEGER DEFAULT 10, FOREIGN KEY (product_id) REFERENCES products(id))"),
    MigrationAction(command="execute_sql", sql="INSERT INTO stock_levels (product_id, quantity, reorder_level) SELECT id, stock_quantity, reorder_level FROM products"),
    MigrationAction(command="execute_sql", sql="""CREATE TABLE new_products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        supplier_id INTEGER,
        category_id INTEGER,
        price REAL NOT NULL,
        cost REAL,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT '2024-01-01',
        notes TEXT,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
        FOREIGN KEY (category_id) REFERENCES categories(id)
    )"""),
    MigrationAction(command="execute_sql", sql="""INSERT INTO new_products (id, name, supplier_id, category_id, price, cost, is_active, created_at, notes)
        SELECT p.id, p.name, s.id, c.id, p.price, p.cost, p.is_active, p.created_at, p.notes
        FROM products p
        LEFT JOIN suppliers s ON LOWER(p.supplier_name) = LOWER(s.name)
        LEFT JOIN categories c ON p.category = c.name AND (p.subcategory IS c.subcategory OR (p.subcategory IS NULL AND c.subcategory IS NULL))
    """),
    MigrationAction(command="execute_sql", sql="DROP TABLE products"),
    MigrationAction(command="execute_sql", sql="ALTER TABLE new_products RENAME TO products"),
    MigrationAction(command="validate_schema"),
    MigrationAction(command="finish"),
]

BASELINE_PLANS = {
    "easy_add_columns": EASY_STEPS,
    "medium_normalize_tables": MEDIUM_STEPS,
    "hard_full_restructure": HARD_STEPS,
}


def run_baseline_task(task_id: str) -> dict:
    env = SafeMigrateEnvironment()
    obs = env.reset(task_id=task_id)

    for action in BASELINE_PLANS.get(task_id, []):
        obs = env.step(action)
        if obs.done:
            break

    if not obs.done:
        obs = env.step(MigrationAction(command="finish"))

    result = grade_episode(env)
    env.close()
    return result


def run_baseline() -> dict:
    results = {}
    for task_id in TASKS:
        results[task_id] = run_baseline_task(task_id)
    return {"baseline_scores": results}


if __name__ == "__main__":
    results = run_baseline()
    print(json.dumps(results, indent=2))