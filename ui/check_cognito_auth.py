"""Self-check: SECRET_HASH shape when client secret is set."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env.shared")

from cognito_auth import _secret_hash  # noqa: E402

assert os.getenv("COGNITO_APP_CLIENT_ID")
h = _secret_hash("testuser")
if os.getenv("COGNITO_APP_CLIENT_SECRET"):
    assert h and len(h) > 20
else:
    assert h is None
print("ok")
