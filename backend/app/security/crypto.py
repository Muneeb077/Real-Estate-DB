"""
Application-level field encryption.

Envelope encryption: every value gets its own random 256-bit data key (DEK).
The value is encrypted with AES-256-GCM under the DEK, and the DEK is wrapped
(encrypted) with a key-encryption key (KEK). Only the wrapped DEK is stored, so
rotating the KEK means re-wrapping 32-byte keys, not re-encrypting data.

Blob layout (bytes):
    0      format version (1)
    1      length of KEK id (n)
    2..    KEK id (ascii, n bytes)
    +12    nonce used to wrap the DEK
    +48    wrapped DEK (32 bytes + 16-byte GCM tag)
    +12    nonce used for the data
    rest   ciphertext + 16-byte GCM tag

The `context` (e.g. "users.email") is bound as GCM associated data, so a
ciphertext copied into a different column fails to decrypt.
"""
import base64
import hashlib
import hmac
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

FORMAT_VERSION = 1


class LocalKeyring:
    """
    KEKs supplied through the environment. A KMS/Vault keyring would implement
    the same three methods (wrap, unwrap, active_id) by calling the KMS API.
    """

    def __init__(self, keys_spec, active_id):
        self._keys = {}
        for part in filter(None, (p.strip() for p in keys_spec.split(","))):
            kid, b64 = part.split(":", 1)
            key = base64.b64decode(b64)
            if len(key) != 32:
                raise ValueError(f"KEK {kid} must be 32 bytes")
            self._keys[kid] = key
        if active_id not in self._keys:
            raise ValueError("KEK_ACTIVE does not name a key in KEK_KEYS")
        self._active = active_id

    def active_id(self):
        return self._active

    def wrap(self, kid, dek, aad):
        nonce = os.urandom(12)
        return nonce, AESGCM(self._keys[kid]).encrypt(nonce, dek, aad)

    def unwrap(self, kid, nonce, wrapped, aad):
        if kid not in self._keys:
            raise KeyError(f"Unknown KEK id {kid}; was it removed before rotation finished?")
        return AESGCM(self._keys[kid]).decrypt(nonce, wrapped, aad)


class FieldCipher:
    def __init__(self, keyring, blind_index_key):
        self.keyring = keyring
        self._bi_key = base64.b64decode(blind_index_key) if blind_index_key else b""
        if len(self._bi_key) < 32:
            raise ValueError("BLIND_INDEX_KEY must be at least 32 bytes (base64)")

    def encrypt(self, plaintext, context):
        if plaintext is None:
            return None
        aad = context.encode()
        kid = self.keyring.active_id()
        dek = AESGCM.generate_key(bit_length=256)
        wrap_nonce, wrapped = self.keyring.wrap(kid, dek, aad)
        nonce = os.urandom(12)
        ct = AESGCM(dek).encrypt(nonce, plaintext.encode("utf-8"), aad)
        kid_b = kid.encode()
        return bytes([FORMAT_VERSION, len(kid_b)]) + kid_b + wrap_nonce + wrapped + nonce + ct

    def _parse(self, blob):
        blob = bytes(blob)
        if blob[0] != FORMAT_VERSION:
            raise ValueError("Unknown ciphertext format")
        n = blob[1]
        kid = blob[2:2 + n].decode()
        p = 2 + n
        wrap_nonce, wrapped = blob[p:p + 12], blob[p + 12:p + 60]
        nonce, ct = blob[p + 60:p + 72], blob[p + 72:]
        return kid, wrap_nonce, wrapped, nonce, ct

    def decrypt(self, blob, context):
        if blob is None:
            return None
        aad = context.encode()
        kid, wrap_nonce, wrapped, nonce, ct = self._parse(blob)
        dek = self.keyring.unwrap(kid, wrap_nonce, wrapped, aad)
        return AESGCM(dek).decrypt(nonce, ct, aad).decode("utf-8")

    def key_id(self, blob):
        return self._parse(blob)[0]

    def rewrap(self, blob, context):
        """
        Re-wraps the DEK under the active KEK without touching the data ciphertext.
        Returns the new blob, or the same blob if it already uses the active KEK.
        """
        aad = context.encode()
        kid, wrap_nonce, wrapped, nonce, ct = self._parse(blob)
        active = self.keyring.active_id()
        if kid == active:
            return bytes(blob)
        dek = self.keyring.unwrap(kid, wrap_nonce, wrapped, aad)
        new_nonce, new_wrapped = self.keyring.wrap(active, dek, aad)
        kid_b = active.encode()
        return bytes([FORMAT_VERSION, len(kid_b)]) + kid_b + new_nonce + new_wrapped + nonce + ct

    def blind_index(self, value, context):
        """
        Deterministic HMAC-SHA256 of a normalised value: lets the database enforce
        uniqueness and do equality lookups without ever seeing the plaintext.
        """
        if value is None:
            return None
        msg = f"{context}|{value.strip().lower()}".encode()
        return hmac.new(self._bi_key, msg, hashlib.sha256).digest()


_cipher = None


def init_app(app):
    global _cipher
    keyring = LocalKeyring(app.config["KEK_KEYS"], app.config["KEK_ACTIVE"])
    _cipher = FieldCipher(keyring, app.config["BLIND_INDEX_KEY"])


def cipher():
    return _cipher


def encrypt(value, context):
    return _cipher.encrypt(value, context)


def decrypt(blob, context):
    return _cipher.decrypt(blob, context)


def blind_index(value, context):
    return _cipher.blind_index(value, context)


def sha256(token):
    """
    One-way hash for high-entropy secrets (reset/refresh tokens): a DB leak
    does not reveal usable tokens.
    """
    return hashlib.sha256(token.encode()).digest()
