"""Standard-library example: Jenkins workspace uploads its *actual bytes*.

Required Jenkins credential binding: collector key as hex (never print it).
Use HTTPS outside Docker's private network; use scoped credentials per tenant/source.
"""
import hashlib
import hmac
import secrets
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import json

def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()

def submit(path, api, tenant, source, source_record, key_id, key_hex):
    payload = Path(path).read_bytes()
    if not payload or len(payload) > 1024 * 1024:
        raise ValueError('Evidence file must be 1 byte to 1 MiB')
    
    timestamp = datetime.now(timezone.utc).isoformat()
    nonce = secrets.token_urlsafe(24)
    digest = hashlib.sha256(payload).hexdigest()
    
    message = canonical({'timestamp': timestamp, 'nonce': nonce, 'tenant': tenant, 'source': source,
                       'source_record': source_record, 'sha256': digest})
    sig = hmac.new(bytes.fromhex(key_hex), message, hashlib.sha256).hexdigest()
    
    headers = {
        'X-Tenant': tenant, 'X-Source': source, 'X-Source-Record': source_record,
        'X-Key-Id': key_id, 'X-Timestamp': timestamp, 'X-Nonce': nonce,
        'X-Content-SHA256': digest, 'X-Signature': sig, 'Content-Type': 'application/octet-stream'
    }
    
    # Ensure it targets the backend API port (8000)
    req = urllib.request.Request(api.rstrip('/') + '/v1/source-evidence/ingest', data=payload, headers=headers, method='POST')
    
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: python submit_jenkins_evidence.py path/to/real-test-report.json')
    
    # HARDCODED FOR LOCAL WINDOWS TESTING
    API_URL = "http://127.0.0.1:8001" 
    TENANT = "local-demo"
    SOURCE = "jenkins"
    SOURCE_RECORD = "build-1042"
    KEY_ID = "key-1"
    SECRET = "b5a61ad7ed143fc0886cd61d6ed3955669dedf4fdeb0f08462ec3c572192b5b5"

    result = submit(sys.argv[1], API_URL, TENANT, SOURCE, SOURCE_RECORD, KEY_ID, SECRET)
    print(json.dumps(result, indent=2))