"""
Rotate the key-encryption key (KEK).

  1. python scripts/gen_keys.py            # copy only the new KEK value
  2. .env: KEK_KEYS=v1:<old>,v2:<new>  and  KEK_ACTIVE=v2   (restart the API)
  3. python scripts/rotate_keys.py         # re-wraps every data key under v2
  4. when the report shows no v1 left, remove v1 from KEK_KEYS

    python scripts/rotate_keys.py --report   # usage per KEK id only
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from app.keyrotation import key_usage, rotate

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        if "--report" not in sys.argv:
            print(f"Re-wrapped {rotate()} values under {app.config['KEK_ACTIVE']}")
        print(json.dumps(key_usage(), indent=2))
