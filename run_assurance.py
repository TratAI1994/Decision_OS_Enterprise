"""Run local checks. A PASS here is a development test result, not certification."""
import json
import os
from pathlib import Path
import subprocess
import sys

def main():
    root=Path(__file__).resolve().parent
    completed=subprocess.run([sys.executable,'-m','pytest','-q',str(root/'tests')],cwd=root,check=False)
    live=bool(os.getenv('R98_POSTGRES_URL'))
    summary={'release':'R9.8','python_tests':'PASS' if completed.returncode==0 else 'FAIL',
             'postgresql_live':'EXERCISED' if live else 'NOT_TESTED',
             'signed_pipeline':'NOT_TESTED','deployment':'NOT_TESTED','erp_finance':'NOT_TESTED',
             'production_certified':False}
    print(json.dumps(summary,indent=2))
    return completed.returncode
if __name__=='__main__':sys.exit(main())
