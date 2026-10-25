"""
Prints fresh secrets for .env: Flask/JWT secret, a 256-bit KEK and a blind-index key.
"""
import base64
import secrets

print(f"SECRET_KEY={secrets.token_hex(32)}")
print(f"KEK_KEYS=v1:{base64.b64encode(secrets.token_bytes(32)).decode()}")
print("KEK_ACTIVE=v1")
print(f"BLIND_INDEX_KEY={base64.b64encode(secrets.token_bytes(32)).decode()}")
