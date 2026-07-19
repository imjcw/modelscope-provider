"""Test that mapping_models table is created correctly."""
import pytest
from provider.core.database import DatabaseManager


def test_mapping_models_table_exists():
    """Verify mapping_models table is created with correct structure."""
    db = DatabaseManager('modelscope_proxy_test.db')
    db.initialize_tables()

    # Check table exists
    import sqlite3
    conn = sqlite3.connect('modelscope_proxy_test.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='mapping_models'")
    result = cursor.fetchone()
    assert result is not None, "mapping_models table should exist"

    # Check columns
    cursor.execute("PRAGMA table_info(mapping_models)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    expected_columns = {
        'id': 'INTEGER',
        'alias_name': 'TEXT',
        'supplier_id': 'INTEGER',
        'model_name': 'TEXT',
        'sort_order': 'INTEGER',
        'created_at': 'TIMESTAMP',
        'updated_at': 'TIMESTAMP',
    }
    assert columns == expected_columns, f"Columns mismatch. Expected {expected_columns}, got {columns}"

    # Check indexes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_mapping_models_alias'")
    alias_idx = cursor.fetchone()
    assert alias_idx is not None, "idx_mapping_models_alias index should exist"

    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_mapping_models_supplier'")
    supplier_idx = cursor.fetchone()
    assert supplier_idx is not None, "idx_mapping_models_supplier index should exist"

    conn.close()
    print("✓ All database structure checks passed!")
