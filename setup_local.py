"""Prepare local Docker demo configuration; creates random credentials and a matching db secret."""
from pathlib import Path
import json,secrets
root=Path(__file__).resolve().parent
(root/'secrets').mkdir(exist_ok=True)
for name in ('.env','secrets/db_password.txt'):
    if (root/name).exists():
        raise SystemExit(f'{name} already exists; refusing to overwrite credentials')
password=secrets.token_urlsafe(30)
keys={role:secrets.token_urlsafe(30) for role in ('lead','reviewer','approver','finance')}
identities={key:{'user':f'local-{role}','tenant':'local-demo','role':role} for role,key in keys.items()}
from urllib.parse import quote
lines=[
    'DATABASE_URL=postgresql+psycopg://decision:'+quote(password,safe='')+'@db:5432/decision_os',
    'DECISION_OS_UI_TOKEN='+keys['lead'],
    'DECISION_OS_IDENTITIES='+json.dumps(identities,separators=(',',':')),
]
(root/'secrets/db_password.txt').write_text(password,encoding='utf8')
(root/'.env').write_text('\n'.join(lines)+'\n',encoding='utf8')
print('Local configuration generated. Keep secrets/ and .env private.')
print('Bootstrap role tokens (keep private):')
for role,key in keys.items(): print(f'  {role}: {key}')
