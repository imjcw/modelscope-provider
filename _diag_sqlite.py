"""Diagnostic: test SQLite write operations on the project data/ directory."""
import os, sqlite3, tempfile, shutil
from pathlib import Path

DATA = "data"
DB = Path(DATA) / "ai_provider.db"
DB_TEST = Path(DATA) / "_diag_test.db"

print(f"=== Platform ===")
print(f"Platform       : {os.uname().sysname}")
print(f"Kernel         : {Path('/proc/version').read_text(errors='ignore')[:80]}")
print(f"PWD            : {Path.cwd()}")
print(f"DATA dir exists: {Path(DATA).exists()}")
print(f"DATA writable  : {os.access(Path(DATA), os.W_OK)}")
print()

# Check for leftover WAL files from previous runs
for suffix in [".db-wal", ".db-shm", ".db-journal"]:
    f = Path(DATA) / (DB.name[:-3] + suffix)
    if f.exists():
        print(f"LEFTOVER: {f}  size={f.stat().st_size}")
print()

print(f"=== DB file check ===")
if DB.exists():
    print(f"DB exists    : {DB.stat().st_size} bytes")
    print(f"DB writable  : {os.access(DB, os.W_OK)}")
else:
    print(f"DB does not exist")
print()

print(f"=== New DB in DATA dir ===")
if DB_TEST.exists():
    DB_TEST.unlink()
conn = sqlite3.connect(str(DB_TEST))
try:
    # 1. Read-only pragma
    r = conn.execute("PRAGMA page_size").fetchone()
    print(f"PRAGMA page_size     : {r}")
    # 2. Write: CREATE TABLE
    conn.execute("CREATE TABLE __test__(id INTEGER PRIMARY KEY)")
    conn.commit()
    print("CREATE TABLE          : OK")
    # 3. INSERT
    conn.execute("INSERT INTO __test__ VALUES (1)")
    conn.commit()
    print("INSERT                : OK")
    # 4. PRAGMA journal_mode=WAL
    r = conn.execute("PRAGMA journal_mode=WAL").fetchone()
    print(f"journal_mode=WAL      : {r}")
    # 5. Write after WAL
    conn.execute("INSERT INTO __test__ VALUES (2)")
    conn.commit()
    print("INSERT after WAL      : OK")
except Exception as e:
    print(f"FAILED at step: {e}")
finally:
    try:
        conn.close()
    except Exception:
        pass
    for suffix in [".db", "-wal", "-shm", "-journal"]:
        f = DB_TEST.parent / (DB_TEST.name + suffix)
        if f.exists():
            print(f"  leftover {f}  size={f.stat().st_size}")
    if DB_TEST.exists():
        DB_TEST.unlink()
print()

print(f"=== /tmp comparison ===")
tmp_db = Path(tempfile.gettempdir()) / "_ai_provider_diag.db"
conn = sqlite3.connect(str(tmp_db))
try:
    conn.execute("CREATE TABLE __test__(id INTEGER PRIMARY KEY)")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("INSERT INTO __test__ VALUES (1)")
    conn.commit()
    print("All ops in /tmp       : OK")
except Exception as e:
    print(f"/tmp FAILED: {e}")
finally:
    conn.close()
    for suffix in [".db", "-wal", "-shm", "-journal"]:
        f = tmp_db.parent / (tmp_db.name + suffix)
        if f.exists():
            f.unlink()