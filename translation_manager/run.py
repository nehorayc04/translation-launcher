"""
Bootstrap script used by PyInstaller (relative imports don't survive
`pyinstaller --onefile path/to/module.py`, so we wrap the entry point here).
"""

import sys
from pathlib import Path

# Make the parent directory importable when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from translation_manager.main import main  # noqa: E402

if __name__ == "__main__":
    main()
