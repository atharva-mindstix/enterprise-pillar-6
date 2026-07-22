"""Self-check: agent_task_payload shape for post-issue invoke."""

from agentcore_identity import agent_task_payload

p = agent_task_payload(
    task="Update README with local deployment instructions.",
    task_type="Documentation",
    repo="acme/agent-demo",
    issue_number=42,
    sub="cognito-user-123",
    email="developer@example.com",
)
assert p["session"]["issue_number"] == 42
assert p["session"]["repository"] == "acme/agent-demo"
assert "#42" in p["prompt"] and "agent-demo" in p["prompt"]
assert "Do not modify application source" in p["prompt"]
print("ok")
