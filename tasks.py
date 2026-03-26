import sqlite3


class Task:
    def __init__(self, task_id, difficulty, title, description, target_description, setup_fn, target_check_fn, data_check_fn, max_steps):
        self.task_id = task_id
        self.difficulty = difficulty
        self.title = title
        self.description = description
        self.target_description = target_description
        self.setup_fn = setup_fn
        self.target_check_fn = target_check_fn
        self.data_check_fn = data_check_fn
        self.max_steps = max_steps


def _safe(fn):
    try:
        return fn()
    except Exception:
        return 0.0


def setup_task_easy(conn):
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            salary REAL NOT NULL
        );
        INSERT INTO employees (id, name, department, salary) VALUES
            (1, 'Alice Chen', 'Engineering', 95000),
            (2, 'Bob Kumar', 'Engineering', 88000),
            (3, 'Carol Davis', 'Marketing', 72000),
            (4, 'Dan Wilson', 'Marketing', 68000),
            (5, 'Eve Martinez', 'Sales', 78000),
            (6, 'Frank Lee', 'Sales', 82000),
            (7, 'Grace Park', 'Engineering', 105000),
            (8, 'Hank Brown', 'HR', 65000);
    """)
    conn.commit()


def check_task_easy_schema(conn):
    c = conn.cursor()
    total = 6
    checks = 0

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='employees'")
    if not c.fetchone():
        return 0.0
    checks += 1

    c.execute("PRAGMA table_info(employees)")
    columns = {row[1]: {"type": row[2].upper(), "notnull": bool(row[3]), "default": row[4], "pk": bool(row[5])} for row in c.fetchall()}

    if "email" in columns:
        checks += 1

    if "hire_date" in columns:
        checks += 1

    if "is_active" in columns:
        checks += 1
        col = columns["is_active"]
        if col["type"] in ("INTEGER", "INT", "BOOLEAN"):
            checks += 1
        if col["default"] is not None and str(col["default"]) == "1":
            checks += 1

    return checks / total


def check_task_easy_data(conn):
    c = conn.cursor()
    total = 5
    checks = 0

    def _check():
        nonlocal checks

        c.execute("SELECT COUNT(*) FROM employees")
        count = c.fetchone()[0]
        if count != 8:
            return
        checks += 1

        c.execute("SELECT name, department, salary FROM employees ORDER BY id")
        rows = c.fetchall()
        original = [
            ('Alice Chen', 'Engineering', 95000),
            ('Bob Kumar', 'Engineering', 88000),
            ('Carol Davis', 'Marketing', 72000),
            ('Dan Wilson', 'Marketing', 68000),
            ('Eve Martinez', 'Sales', 78000),
            ('Frank Lee', 'Sales', 82000),
            ('Grace Park', 'Engineering', 105000),
            ('Hank Brown', 'HR', 65000),
        ]
        if len(rows) == len(original):
            match = sum(1 for a, b in zip(rows, original) if a == b)
            checks += match / len(original)

        c.execute("SELECT COUNT(*) FROM employees WHERE is_active = 1 OR is_active IS NULL")
        active_count = c.fetchone()[0]
        if active_count == 8:
            checks += 1

        c.execute("SELECT COUNT(DISTINCT id) FROM employees")
        if c.fetchone()[0] == 8:
            checks += 1

        c.execute("SELECT COUNT(*) FROM employees WHERE name IS NULL OR department IS NULL OR salary IS NULL")
        if c.fetchone()[0] == 0:
            checks += 1

    try:
        _check()
    except Exception:
        pass

    return checks / total


def setup_task_medium(conn):
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            city TEXT,
            country TEXT,
            created_at TEXT DEFAULT '2024-01-01'
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            price REAL NOT NULL,
            order_date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        INSERT INTO users VALUES
            (1, 'Priya Sharma', 'priya@example.com', 'Mumbai', 'India', '2023-06-15'),
            (2, 'James O''Brien', 'james@example.com', 'Dublin', 'Ireland', '2023-07-20'),
            (3, 'Yuki Tanaka', 'yuki@example.com', 'Tokyo', 'Japan', '2023-08-10'),
            (4, 'Maria Garcia', 'maria@example.com', 'Madrid', 'Spain', '2024-01-05');
        INSERT INTO orders VALUES
            (1, 1, 'Laptop', 1, 999.99, '2024-01-10'),
            (2, 1, 'Mouse', 2, 29.99, '2024-01-10'),
            (3, 2, 'Keyboard', 1, 149.99, '2024-02-15'),
            (4, 3, 'Monitor', 1, 599.99, '2024-03-01'),
            (5, 3, 'Webcam', 1, 79.99, '2024-03-01'),
            (6, 4, 'Headphones', 3, 199.99, '2024-03-20'),
            (7, 1, 'SSD', 1, 129.99, '2024-04-05');
    """)
    conn.commit()


def check_task_medium_schema(conn):
    c = conn.cursor()
    total = 8
    checks = 0

    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in c.fetchall()}

    if "users" in tables:
        checks += 1
        c.execute("PRAGMA table_info(users)")
        user_cols = {row[1] for row in c.fetchall()}
        if "city" not in user_cols and "country" not in user_cols:
            checks += 1

    if "addresses" in tables:
        checks += 1
        c.execute("PRAGMA table_info(addresses)")
        addr_cols = {row[1] for row in c.fetchall()}
        if "city" in addr_cols and "country" in addr_cols and "user_id" in addr_cols:
            checks += 1
        c.execute(f"PRAGMA foreign_key_list(addresses)")
        fks = [row[2] for row in c.fetchall()]
        if "users" in fks:
            checks += 1

    if "order_items" in tables:
        checks += 1
        c.execute("PRAGMA table_info(order_items)")
        item_cols = {row[1] for row in c.fetchall()}
        if "order_id" in item_cols and "product_name" in item_cols and "quantity" in item_cols and "price" in item_cols:
            checks += 1

    if "orders" in tables:
        c.execute("PRAGMA table_info(orders)")
        order_cols = {row[1] for row in c.fetchall()}
        if "product_name" not in order_cols and "quantity" not in order_cols:
            checks += 1

    return checks / total


def check_task_medium_data(conn):
    c = conn.cursor()
    total = 7
    checks = 0

    try:
        c.execute("SELECT COUNT(*) FROM users")
        if c.fetchone()[0] == 4:
            checks += 1

        c.execute("SELECT COUNT(*) FROM addresses")
        if c.fetchone()[0] >= 4:
            checks += 1

        c.execute("SELECT a.city, a.country FROM addresses a JOIN users u ON a.user_id = u.id WHERE u.full_name = 'Priya Sharma'")
        row = c.fetchone()
        if row and row[0] == 'Mumbai' and row[1] == 'India':
            checks += 1

        c.execute("SELECT a.city, a.country FROM addresses a JOIN users u ON a.user_id = u.id WHERE u.full_name = 'Yuki Tanaka'")
        row = c.fetchone()
        if row and row[0] == 'Tokyo' and row[1] == 'Japan':
            checks += 1

        c.execute("SELECT COUNT(*) FROM order_items")
        if c.fetchone()[0] == 7:
            checks += 1

        c.execute("SELECT COUNT(DISTINCT user_id) FROM addresses")
        if c.fetchone()[0] == 4:
            checks += 1

        c.execute("""
            SELECT oi.product_name, oi.quantity, oi.price
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN users u ON o.user_id = u.id
            WHERE u.full_name = 'Yuki Tanaka'
            ORDER BY oi.product_name
        """)
        rows = c.fetchall()
        expected_products = {'Monitor', 'Webcam'}
        if len(rows) == 2 and {r[0] for r in rows} == expected_products:
            checks += 1

    except Exception:
        pass

    return checks / total


def setup_task_hard(conn):
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT,
            price REAL NOT NULL,
            cost REAL,
            supplier_name TEXT,
            supplier_email TEXT,
            supplier_country TEXT,
            stock_quantity INTEGER DEFAULT 0,
            reorder_level INTEGER DEFAULT 10,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT '2024-01-01',
            notes TEXT
        );
        INSERT INTO products VALUES
            (1, 'Gaming Laptop', 'Electronics', 'Computers', 1299.99, 900.00, 'TechCorp', 'sales@techcorp.com', 'USA', 25, 5, 1, '2024-01-15', 'Best seller'),
            (2, 'Wireless Mouse', 'Electronics', 'Peripherals', 49.99, 20.00, 'TechCorp', 'sales@techcorp.com', 'USA', 150, 30, 1, '2024-01-15', NULL),
            (3, 'Standing Desk', 'Furniture', 'Desks', 699.99, 350.00, 'OfficePro', 'info@officepro.com', 'Germany', 12, 3, 1, '2024-02-01', 'Premium oak'),
            (4, 'Ergonomic Chair', 'Furniture', 'Chairs', 499.99, 250.00, 'OfficePro', 'info@officepro.com', 'Germany', 8, 5, 1, '2024-02-01', NULL),
            (5, 'USB-C Hub', 'Electronics', 'Accessories', 79.99, 30.00, 'ConnectAll', 'orders@connectall.com', 'Taiwan', 200, 50, 1, '2024-03-01', NULL),
            (6, 'Noise Cancelling Headphones', 'Electronics', 'Audio', 349.99, 150.00, 'SoundWave', 'b2b@soundwave.jp', 'Japan', 45, 10, 1, '2024-03-15', 'New model'),
            (7, 'Whiteboard 6ft', 'Office Supplies', 'Boards', 129.99, 60.00, 'OfficePro', 'info@officepro.com', 'Germany', 0, 5, 0, '2024-01-20', 'Discontinued'),
            (8, 'Mechanical Keyboard', 'Electronics', 'Peripherals', 159.99, 70.00, 'TechCorp', 'sales@techcorp.com', 'USA', 80, 20, 1, '2024-04-01', 'Cherry MX'),
            (9, 'Monitor Arm', 'Furniture', NULL, 89.99, 35.00, NULL, NULL, NULL, 30, 10, 1, '2024-04-10', 'No supplier yet'),
            (10, 'Desk Lamp', 'Electronics', 'Accessories', 59.99, 25.00, 'techcorp', 'sales@techcorp.com', 'USA', 60, 15, 1, '2024-05-01', NULL);

        CREATE TABLE sales (
            id INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            sale_date TEXT NOT NULL,
            customer_name TEXT,
            discount_pct REAL DEFAULT 0,
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
        INSERT INTO sales VALUES
            (1, 1, 2, '2024-02-10', 'Acme Corp', 10),
            (2, 2, 10, '2024-02-15', 'Acme Corp', 5),
            (3, 3, 1, '2024-03-01', 'StartupXYZ', 0),
            (4, 6, 5, '2024-03-20', 'MegaBank', 15),
            (5, 1, 1, '2024-04-01', 'StartupXYZ', 0),
            (6, 5, 20, '2024-04-05', 'Acme Corp', 8),
            (7, 8, 5, '2024-04-10', 'DevShop', 0),
            (8, 4, 3, '2024-04-15', 'MegaBank', 12),
            (9, 9, 2, '2024-05-01', 'StartupXYZ', 0),
            (10, 10, 8, '2024-05-10', 'Acme Corp', 5);
    """)
    conn.commit()


def check_task_hard_schema(conn):
    c = conn.cursor()
    total = 12
    checks = 0

    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in c.fetchall()}

    if "suppliers" in tables:
        checks += 1
        c.execute("PRAGMA table_info(suppliers)")
        cols = {row[1]: row[2].upper() for row in c.fetchall()}
        if "name" in cols and "email" in cols and "country" in cols:
            checks += 1
        if cols.get("name", "") in ("TEXT",):
            checks += 0.5
        try:
            c.execute("SELECT COUNT(*) FROM suppliers")
            c.execute("SELECT COUNT(DISTINCT name) FROM suppliers WHERE name IS NOT NULL")
            distinct = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM suppliers WHERE name IS NOT NULL")
            total_with_name = c.fetchone()[0]
            if distinct == total_with_name:
                checks += 0.5
        except Exception:
            pass

    if "categories" in tables:
        checks += 1
        c.execute("PRAGMA table_info(categories)")
        cols = {row[1] for row in c.fetchall()}
        if "name" in cols:
            checks += 1

    if "products" in tables:
        checks += 1
        c.execute("PRAGMA table_info(products)")
        cols = {row[1] for row in c.fetchall()}
        if "supplier_id" in cols:
            checks += 1
        if "category_id" in cols:
            checks += 1
        if "supplier_name" not in cols and "supplier_email" not in cols and "supplier_country" not in cols:
            checks += 1
        if "category" not in cols and "subcategory" not in cols:
            checks += 1
        c.execute("PRAGMA foreign_key_list(products)")
        fk_tables = {row[2] for row in c.fetchall()}
        if "suppliers" in fk_tables and "categories" in fk_tables:
            checks += 1

    if "sales" in tables:
        checks += 0.5

    if "inventory_log" in tables or "stock_levels" in tables:
        checks += 0.5

    return min(checks / total, 1.0)


def check_task_hard_data(conn):
    c = conn.cursor()
    total = 9
    checks = 0

    try:
        c.execute("SELECT COUNT(*) FROM products")
        if c.fetchone()[0] == 10:
            checks += 1
        else:
            return 0.0
    except Exception:
        return 0.0

    try:
        c.execute("SELECT COUNT(*) FROM suppliers WHERE name IS NOT NULL")
        sup_count = c.fetchone()[0]
        if sup_count >= 4:
            checks += 1
    except Exception:
        pass

    try:
        c.execute("SELECT COUNT(*) FROM categories")
        if c.fetchone()[0] >= 3:
            checks += 1
    except Exception:
        pass

    try:
        c.execute("SELECT p.name, s.name FROM products p JOIN suppliers s ON p.supplier_id = s.id WHERE p.name = 'Gaming Laptop'")
        row = c.fetchone()
        if row and row[1] and row[1].lower() == 'techcorp':
            checks += 1
    except Exception:
        pass

    try:
        c.execute("SELECT p.name, c.name FROM products p JOIN categories c ON p.category_id = c.id WHERE p.name = 'Standing Desk'")
        row = c.fetchone()
        if row and row[1] and row[1].lower() == 'furniture':
            checks += 1
    except Exception:
        pass

    try:
        c.execute("SELECT COUNT(*) FROM sales")
        if c.fetchone()[0] == 10:
            checks += 1
    except Exception:
        pass

    try:
        c.execute("SELECT s.quantity FROM sales s JOIN products p ON s.product_id = p.id WHERE p.name = 'Gaming Laptop' ORDER BY s.sale_date")
        rows = c.fetchall()
        if len(rows) == 2 and rows[0][0] == 2 and rows[1][0] == 1:
            checks += 1
    except Exception:
        pass

    try:
        c.execute("SELECT p.name FROM products p WHERE p.supplier_id IS NULL AND p.name = 'Monitor Arm'")
        row = c.fetchone()
        if row:
            checks += 1
    except Exception:
        pass

    try:
        c.execute("SELECT p.name, s.name FROM products p JOIN suppliers s ON p.supplier_id = s.id WHERE p.name = 'Desk Lamp'")
        row = c.fetchone()
        if row and row[1] and row[1].lower() == 'techcorp':
            checks += 1
    except Exception:
        pass

    return checks / total


TASKS = {
    "easy_add_columns": Task(
        task_id="easy_add_columns",
        difficulty="easy",
        title="Add columns to employee table",
        description="Add three new columns to the employees table: 'email' (TEXT, nullable), 'hire_date' (TEXT, nullable), and 'is_active' (INTEGER, default 1). Ensure all existing data is preserved and is_active defaults to 1 for all current employees.",
        target_description="The employees table should have 7 columns: id, name, department, salary, email, hire_date, is_active. The is_active column must be INTEGER type with DEFAULT 1. All 8 existing rows must be preserved with original values intact. No NULL values allowed in name, department, or salary.",
        setup_fn=setup_task_easy,
        target_check_fn=check_task_easy_schema,
        data_check_fn=check_task_easy_data,
        max_steps=15,
    ),
    "medium_normalize_tables": Task(
        task_id="medium_normalize_tables",
        difficulty="medium",
        title="Normalize database schema",
        description="Normalize the database: (1) Extract city/country from users into an 'addresses' table with a foreign key to users. Remove city/country from users. (2) Split orders into 'orders' (id, user_id, order_date) and 'order_items' (id, order_id, product_name, quantity, price). Remove product columns from orders. Preserve all data and ensure referential integrity with proper foreign keys.",
        target_description="Four tables: users (without city/country), addresses (id, user_id FK->users, city, country), orders (id, user_id, order_date — no product columns), order_items (id, order_id FK->orders, product_name, quantity, price). All 4 users, 4 addresses (one per user, no duplicates), and 7 order items preserved with correct FK relationships.",
        setup_fn=setup_task_medium,
        target_check_fn=check_task_medium_schema,
        data_check_fn=check_task_medium_data,
        max_steps=25,
    ),
    "hard_full_restructure": Task(
        task_id="hard_full_restructure",
        difficulty="hard",
        title="Full schema restructure with dirty data handling",
        description="Major restructure with real-world data quality issues: (1) Extract supplier info into 'suppliers' table — BUT beware: product #9 has NULL supplier, product #10 has 'techcorp' (lowercase) which is the same as 'TechCorp'. Deduplicate case-insensitively, handle NULLs gracefully. (2) Extract categories into 'categories' table — product #9 has NULL subcategory. (3) Create 'stock_levels' table for inventory tracking. (4) Add proper foreign keys, drop denormalized columns. All 10 products and 10 sales must be preserved.",
        target_description="Tables: suppliers (deduplicated case-insensitively, 4 unique: TechCorp, OfficePro, ConnectAll, SoundWave), categories (with NULL subcategory handling), products (10 rows with supplier_id and category_id FKs, no denormalized columns — product #9 should have NULL supplier_id), sales (10 rows unchanged), stock_levels (10 rows). 'Desk Lamp' must map to TechCorp despite case mismatch in source data.",
        setup_fn=setup_task_hard,
        target_check_fn=check_task_hard_schema,
        data_check_fn=check_task_hard_data,
        max_steps=40,
    ),
}