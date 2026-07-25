"""Public inert fixture: every expression below must remain unexecuted."""

import os
import socket
import subprocess
from pathlib import Path
from urllib.request import urlopen

Path("ZSCRIPT_ANALYZER_MUST_NOT_CREATE").write_text("executed", encoding="utf-8")
os.system("echo analyzer-executed")
subprocess.run(["python", "-c", "print('analyzer-executed')"], check=True)
socket.create_connection(("127.0.0.1", 9))
urlopen("https://example.invalid", timeout=1)
SECRET = os.environ["ZSCRIPT_ANALYZER_SECRET"]
raise RuntimeError("import-time fixture must remain inert")


def public_function(value: int, /, option: str = "safe", *, enabled: bool = True) -> str:
    """Return a deterministic string when called by a human, never by the analyzer."""

    return f"{value}:{option}:{enabled}"
