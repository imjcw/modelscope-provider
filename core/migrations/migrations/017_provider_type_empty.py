"""Change provider_type column default from 'modelscope' to '' (empty = no restrictions)."""

def upgrade(db):
    cursor = db.cursor()
    # SQLite does not support ALTER COLUMN DEFAULT directly;
    # rebuild the accounts table with the new default.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL DEFAULT '',
            api_key TEXT NOT NULL,
            base_url TEXT NOT NULL,
            provider_type TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        INSERT INTO accounts_new (id, account_id, name, api_key, base_url, provider_type, status, created_at, updated_at)
        SELECT id, account_id, name, api_key, base_url, provider_type, status, created_at, updated_at
        FROM accounts
    """)
    cursor.execute("DROP TABLE accounts")
    cursor.execute("ALTER TABLE accounts_new RENAME TO accounts")
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_account_id ON accounts (account_id)"
    )
    db.commit()


def downgrade(db):
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL DEFAULT '',
            api_key TEXT NOT NULL,
            base_url TEXT NOT NULL,
            provider_type TEXT NOT NULL DEFAULT 'modelscope',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        INSERT INTO accounts_new (id, account_id, name, api_key, base_url, provider_type, status, created_at, updated_at)
        SELECT id, account_id, name, api_key, base_url, provider_type, status, created_at, updated_at
        FROM accounts
    """)
    cursor.execute("DROP TABLE accounts")
    cursor.execute("ALTER TABLE accounts_new RENAME TO accounts")
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_account_id ON accounts (account_id)"
    )
    db.commit()
