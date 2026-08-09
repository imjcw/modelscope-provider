import os, sqlite3, tempfile

db = "/mnt/d/workspace/third/provider/data/modelscope_provider.db"
print(f"exists: {os.path.exists(db)}")
print(f"writable: {os.access(db, os.W_OK)}")

conn = sqlite3.connect(db)
try:
    r = conn.execute("SELECT count(*) FROM accounts").fetchone()
    print(f"read query OK: {r}")
except Exception as e:
    print(f"read query FAIL: {e}")

try:
    conn.execute("PRAGMA synchronous=NORMAL")
    print("synchronous=NORMAL OK")
except Exception as e:
    print(f"synchronous=NORMAL FAIL: {e}")

try:
    conn.execute("PRAGMA journal_mode=WAL")
    print("journal_mode=WAL OK")
except Exception as e:
    print(f"journal_mode=WAL FAIL: {e}")

conn.close()

tmp = tempfile.gettempdir()
tmp_db = f"{tmp}/_ai_provider_diag.db"
conn2 = sqlite3.connect(tmp_db)
conn2.execute("PRAGMA synchronous=NORMAL")
conn2.execute("PRAGMA journal_mode=WAL")
conn2.execute("CREATE TABLE t(id INTEGER)")
conn2.commit()
print(f"tmp db ({tmp_db}) OK")
conn2.close()

import os as o2
for suffix in [".db", "-wal", "-shm"]:
    f = tmp_db + suffix
    if o2.path.exists(f):
        o2.unlink(f)