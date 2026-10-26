"""
Decrypts a backup downloaded from the admin console.

    python scripts/decrypt_backup.py homenest-....sql.enc > restore.sql
    mysql homenest < restore.sql

Needs the same KEK_KEYS as the server that made it (any retired KEK id must
still be present).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from app.backups import decrypt_stream
from app.security.crypto import LocalKeyring

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    keyring = LocalKeyring(os.environ["KEK_KEYS"], os.environ["KEK_ACTIVE"])
    with open(sys.argv[1], "rb") as src:
        decrypt_stream(src, sys.stdout.buffer, keyring)
