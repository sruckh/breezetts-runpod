import os
import sys
from pathlib import Path

os.environ.setdefault("BREEZE_TEST_MOCK_ENGINE", "1")

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
