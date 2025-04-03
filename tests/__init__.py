# tests/__init__.py
import sys
from pathlib import Path

# Add project root to Python path for testing
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from dotenv import load_dotenv

# Load test environment variables
load_dotenv(PROJECT_ROOT / ".env.example")

# Configure pytest-asyncio
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()