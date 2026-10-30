#!/usr/bin/env python3
"""
CLI script to manage Jules API keys.
Usage:
  # Create key (requires --owner)
  python3 scripts/create_jules_api_key.py --owner "user_123"

  # List keys (never displays full keys or hashes)
  python3 scripts/create_jules_api_key.py --list

  # Revoke key by visible prefix
  python3 scripts/create_jules_api_key.py --revoke "cgk_a1b2c3"
"""

import sys
import uuid
import time
import argparse
from pathlib import Path

# Add cognito-backend root to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import get_db_sync_session
from app.models.db import DBApiKey
from app.core.jules_auth import generate_api_key

def main():
    parser = argparse.ArgumentParser(description="Manage Jules API Keys")
    parser.add_argument("--owner", type=str, help="Owner ID / Org ID for the new API key (required when creating a key)")
    parser.add_argument("--list", action="store_true", help="List all API keys without sensitive hashes or full keys")
    parser.add_argument("--revoke", type=str, help="Revoke API key by visible prefix (e.g. cgk_a1b2c3)")

    args = parser.parse_args()

    db = get_db_sync_session()

    try:
        if args.list:
            keys = db.query(DBApiKey).order_by(DBApiKey.created_at.desc()).all()
            if not keys:
                print("No API keys found.")
                return

            print(f"{'KEY_ID':<36} | {'PREFIX':<12} | {'OWNER':<16} | {'REVOKED':<7} | {'CREATED_AT':<24} | {'LAST_USED_AT':<24}")
            print("-" * 130)
            for k in keys:
                created_str = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(k.created_at)) if k.created_at else "N/A"
                last_used_str = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(k.last_used_at)) if k.last_used_at else "Never"
                print(f"{k.key_id:<36} | {k.visible_prefix:<12} | {k.owner:<16} | {str(k.is_revoked):<7} | {created_str:<24} | {last_used_str:<24}")
            return

        if args.revoke:
            prefix = args.revoke.strip()
            keys = db.query(DBApiKey).filter(DBApiKey.visible_prefix == prefix).all()
            if not keys:
                print(f"No API key found with visible prefix '{prefix}'.")
                sys.exit(1)

            revoked_count = 0
            for k in keys:
                if not k.is_revoked:
                    k.is_revoked = True
                    revoked_count += 1
            db.commit()
            print(f"Successfully revoked {revoked_count} API key(s) with visible prefix '{prefix}'.")
            return

        # Create key
        if not args.owner:
            print("Error: --owner <id> is required to create a new API key.", file=sys.stderr)
            parser.print_help()
            sys.exit(1)

        owner = args.owner.strip()
        full_key, key_hash, visible_prefix = generate_api_key()
        key_id = f"key_{uuid.uuid4().hex[:16]}"

        api_key_obj = DBApiKey(
            key_id=key_id,
            key_hash=key_hash,
            visible_prefix=visible_prefix,
            owner=owner,
            is_revoked=False,
            created_at=time.time(),
            last_used_at=None
        )
        db.add(api_key_obj)
        db.commit()

        print("=" * 70)
        print("API KEY CREATED SUCCESSFULLY")
        print("=" * 70)
        print(f"Key ID:         {key_id}")
        print(f"Owner:          {owner}")
        print(f"Visible Prefix: {visible_prefix}")
        print(f"API Key:        {full_key}")
        print("=" * 70)
        print("WARNING: Save this key now! It will NEVER be shown again and cannot be recovered.")
        print("=" * 70)

    finally:
        db.close()

if __name__ == "__main__":
    main()
