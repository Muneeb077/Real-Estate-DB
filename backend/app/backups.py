"""
Encrypted database backups.

mysqldump runs as the read-only backup account (password passed via the
MYSQL_PWD environment variable, never on the command line where `ps` shows it)
and its output is encrypted while it streams, so plaintext never touches disk.

File format (all integers big-endian):
    b"HNBK1"                       magic + version
    1 byte n, n bytes              KEK id
    12 bytes, 48 bytes             nonce + wrapped data key (AES-GCM under the KEK)
    repeated chunks:
        4 bytes length L, 12 bytes nonce, L bytes ciphertext+tag
Each chunk's associated data is (chunk index, is_last), so chunks can't be
reordered, dropped or truncated without decryption failing.
"""
import hashlib
import logging
import os
import struct
import subprocess
from datetime import datetime
from urllib.parse import unquote, urlparse

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"HNBK1"
CHUNK = 1024 * 1024
log = logging.getLogger("backups")


def _aad(index, last):
    return struct.pack(">Q?", index, last)


def encrypt_stream(src, dst, keyring):
    kid = keyring.active_id()
    dek = AESGCM.generate_key(bit_length=256)
    wrap_nonce, wrapped = keyring.wrap(kid, dek, b"backup")
    dst.write(MAGIC + bytes([len(kid)]) + kid.encode() + wrap_nonce + wrapped)
    aes = AESGCM(dek)
    index, chunk = 0, src.read(CHUNK)
    while True:
        nxt = src.read(CHUNK)
        last = not nxt
        nonce = os.urandom(12)
        ct = aes.encrypt(nonce, chunk, _aad(index, last))
        dst.write(struct.pack(">I", len(ct)) + nonce + ct)
        if last:
            return kid
        index, chunk = index + 1, nxt


def decrypt_stream(src, dst, keyring):
    if src.read(5) != MAGIC:
        raise ValueError("Not a HomeNest backup file")
    kid = src.read(src.read(1)[0]).decode()
    wrap_nonce, wrapped = src.read(12), src.read(48)
    aes = AESGCM(keyring.unwrap(kid, wrap_nonce, wrapped, b"backup"))
    index = 0
    header = src.read(4)
    while header:
        (length,) = struct.unpack(">I", header)
        nonce, ct = src.read(12), src.read(length)
        header = src.read(4)
        dst.write(aes.decrypt(nonce, ct, _aad(index, not header)))
        index += 1


def run_backup(backup_id, url, backup_dir, keyring, ssl=False):
    from . import db
    u = urlparse(url)
    name = f"homenest-{datetime.now():%Y%m%d-%H%M%S}-{backup_id}.sql.enc"
    path = os.path.join(backup_dir, name)
    os.makedirs(backup_dir, exist_ok=True)
    cmd = ["mysqldump", f"--host={u.hostname}", f"--port={u.port or 3306}", f"--user={unquote(u.username)}",
           "--single-transaction", "--routines", "--triggers", "--events", "--no-tablespaces",
           "--set-gtid-purged=OFF", u.path.lstrip("/").split("?")[0]]
    if ssl:
        cmd.insert(1, "--ssl-mode=REQUIRED")
    env = {**os.environ, "MYSQL_PWD": unquote(u.password or "")}
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        with open(path, "wb") as out:
            kid = encrypt_stream(proc.stdout, out, keyring)
        stderr = proc.stderr.read().decode()[-400:]
        if proc.wait() != 0:
            raise RuntimeError(f"mysqldump failed: {stderr}")
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(CHUNK), b""):
                digest.update(block)
        db.execute("""UPDATE backups SET status = 'succeeded', file_name = :f, size_bytes = :s, sha256 = :h,
                      kek_id = :k, finished_at = NOW() WHERE id = :id""",
                   {"f": name, "s": os.path.getsize(path), "h": digest.hexdigest(), "k": kid, "id": backup_id})
    except Exception as e:  # recorded for the admin UI; details stay in the server log
        log.exception("Backup %s failed", backup_id)
        if os.path.exists(path):
            os.remove(path)
        db.execute("UPDATE backups SET status = 'failed', error = :e, finished_at = NOW() WHERE id = :id",
                   {"e": str(e)[:500], "id": backup_id})


def run_backup_job(backup_id):
    from flask import current_app, has_app_context

    def go():
        from .security.crypto import cipher
        cfg = current_app.config
        run_backup(backup_id, cfg["BACKUP_DATABASE_URL"], cfg["BACKUP_DIR"], cipher().keyring,
                   ssl=bool(cfg.get("DB_SSL_REQUIRED") or cfg.get("DB_SSL_CA")))

    if has_app_context():
        go()
    else:
        from . import create_app
        with create_app().app_context():
            go()
