"""Launch the local service independently of the launcher console."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
with (root/'outputs/server.stdout.log').open('ab') as out, (root/'outputs/server.stderr.log').open('ab') as err:
    process = subprocess.Popen([sys.executable, str(root/'server.py')], cwd=root,
        stdin=subprocess.DEVNULL, stdout=out, stderr=err,
        creationflags=subprocess.CREATE_NO_WINDOW)
print(process.pid)
