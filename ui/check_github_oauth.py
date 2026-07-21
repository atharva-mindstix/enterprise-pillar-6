"""Self-check: GitHub authorize URL shape when client id is set."""
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env.shared", override=True)

from github_oauth import authorize_url, new_oauth_state, resolve_repo  # noqa: E402

assert resolve_repo("agent-demo", "alice") == ("alice", "agent-demo")
assert resolve_repo("acme/agent-demo", "alice") == ("acme", "agent-demo")

if os.getenv("GITHUB_CLIENT_ID", "").strip():
    state = new_oauth_state()
    url = authorize_url(state)
    parsed = urlparse(url)
    assert parsed.netloc == "github.com"
    q = parse_qs(parsed.query)
    assert q["client_id"][0] == os.environ["GITHUB_CLIENT_ID"].strip()
    assert q["state"][0] == state
    assert "read:user" in q["scope"][0] or "repo" in q["scope"][0]
print("ok")
