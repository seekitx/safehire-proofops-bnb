from pathlib import Path
import sys
src = Path(__file__).resolve().parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))
