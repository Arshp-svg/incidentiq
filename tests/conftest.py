"""Global pytest configuration and fixtures for IncidentIQ."""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure repository root is in sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv()
