"""Entry point for running Hard Lock from source and for PyInstaller.

Running this script by full path puts the repo root on sys.path, so
`import hard_lock` works regardless of the current working directory — which
matters when Task Scheduler launches it at logon.
"""

import sys

from hard_lock.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
