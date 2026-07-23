"""
AgentCore Gateway Lambda target — demo tools in one function.

Tools:
  - inspect_repository
  - update_documentation
  - modify_source_code
  - create_pull_request

Gateway passes tool arguments in `event` and metadata in
`context.client_context.custom['bedrockAgentCoreToolName']`.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TOOL_DELIMITER = "___"
API = "https://api.github.com"
API_VERSION = "2022-11-28"


# ---------------------------------------------------------------------------
# Path rules (data-model.md)
# ---------------------------------------------------------------------------


def normalize_path(path: str) -> str:
    return path.strip().lstrip("/")


def is_documentation_path(path: str) -> bool:
    """True for README* files and paths under docs/."""
    p = normalize_path(path)
    if not p:
        return False
    filename = p.rsplit("/", 1)[-1]
    if filename.upper().startswith("README"):
        return True
    return p.startswith("docs/") or p == "docs"


def is_source_path(path: str) -> bool:
    """Non-documentation paths (blocked by Cedar in the primary demo)."""
    p = normalize_path(path)
    if not p:
        return False
    return not is_documentation_path(p)


# ---------------------------------------------------------------------------
# GitHub REST client
# ---------------------------------------------------------------------------


class GitHubError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def resolve_github_token(event: dict[str, Any], context: Any) -> str:
    """
    Resolve GitHub token for this invocation.

    Priority:
    1. Authorization forwarded by agent/Gateway (OAuth USER_FEDERATION — Option A)
    2. GITHUB_PERSONAL_ACCESS_TOKEN env (fixture only; remove in prod)
    """
    custom: dict[str, Any] = {}
    if context is not None and getattr(context, "client_context", None):
        custom = getattr(context.client_context, "custom", None) or {}

    for key in ("authorization", "Authorization", "bedrockAgentCoreAuthorization"):
        raw = custom.get(key) or (event.get("_headers") or {}).get(key)
        if raw:
            return _strip_bearer(str(raw))

    return os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", "").strip()


def _event_for_log(event: dict[str, Any]) -> dict[str, Any]:
    """Redact Authorization / _headers secrets before logging."""
    if "_headers" not in event and "authorization" not in {
        k.lower() for k in event
    }:
        return event
    redacted = dict(event)
    headers = dict(redacted.get("_headers") or {})
    for key in list(headers):
        if "auth" in key.lower():
            headers[key] = "***"
    if headers:
        redacted["_headers"] = headers
    for key in list(redacted):
        if key.lower() in ("authorization", "bedrockagentcoreauthorization"):
            redacted[key] = "***"
    return redacted


def _strip_bearer(value: str) -> str:
    value = value.strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return value


def _github_request(
    method: str,
    path: str,
    token: str,
    *,
    body: dict[str, Any] | None = None,
) -> Any:
    url = f"{API}{path}"
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
        "Authorization": f"Bearer {token}",
        "User-Agent": "enterprise-pillar-6-gateway-lambda",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return {}
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        logger.error("GitHub %s %s failed (%s): %s", method, path, exc.code, detail)
        raise GitHubError(exc.code, detail or str(exc)) from exc


def get_default_branch(owner: str, repo: str, token: str) -> str:
    meta = _github_request("GET", f"/repos/{owner}/{repo}", token)
    return str(meta.get("default_branch") or "main")


def get_repository_tree(
    owner: str,
    repo: str,
    token: str,
    *,
    ref: str | None = None,
    path_filter: str | None = None,
    recursive: bool = True,
) -> dict[str, Any]:
    branch = ref or get_default_branch(owner, repo, token)
    tree_sha = branch
    if "/" not in branch and len(branch) < 40:
        ref_data = _github_request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}", token)
        tree_sha = ref_data["object"]["sha"]

    params = urllib.parse.urlencode({"recursive": "1" if recursive else "0"})
    tree = _github_request("GET", f"/repos/{owner}/{repo}/git/trees/{tree_sha}?{params}", token)

    if path_filter:
        prefix = path_filter.strip().lstrip("/")
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        tree["tree"] = [
            item
            for item in tree.get("tree", [])
            if item.get("path", "").startswith(prefix) or item.get("path") == prefix.rstrip("/")
        ]
    return tree


def get_path_contents(
    owner: str,
    repo: str,
    path: str,
    token: str,
    *,
    ref: str | None = None,
) -> dict[str, Any]:
    query = f"?ref={urllib.parse.quote(ref)}" if ref else ""
    return _github_request("GET", f"/repos/{owner}/{repo}/contents/{path.lstrip('/')}{query}", token)


def decode_file_content(payload: dict[str, Any]) -> str:
    if payload.get("encoding") == "base64" and payload.get("content"):
        return base64.b64decode(payload["content"]).decode("utf-8", errors="replace")
    if isinstance(payload.get("content"), str):
        return payload["content"]
    return ""


def create_or_update_file(
    owner: str,
    repo: str,
    path: str,
    content: str,
    message: str,
    token: str,
    *,
    branch: str,
    sha: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        body["sha"] = sha
    return _github_request(
        "PUT",
        f"/repos/{owner}/{repo}/contents/{path.lstrip('/')}",
        token,
        body=body,
    )


def create_branch(
    owner: str,
    repo: str,
    branch: str,
    from_ref: str,
    token: str,
) -> dict[str, Any]:
    ref_data = _github_request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{from_ref}", token)
    return _github_request(
        "POST",
        f"/repos/{owner}/{repo}/git/refs",
        token,
        body={"ref": f"refs/heads/{branch}", "sha": ref_data["object"]["sha"]},
    )


def ensure_branch(
    owner: str,
    repo: str,
    branch: str,
    token: str,
    *,
    from_ref: str | None = None,
) -> str:
    try:
        _github_request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}", token)
        return branch
    except GitHubError as exc:
        if exc.status != 404:
            raise
    base = from_ref or get_default_branch(owner, repo, token)
    create_branch(owner, repo, branch, base, token)
    return branch


def build_pr_body(body: str | None, issue_number: int | None) -> str:
    """Append Fixes #N when issue_number is set and not already referenced."""
    text = (body or "").strip()
    if issue_number is None:
        return text
    marker = f"#{issue_number}"
    if marker in text:
        return text
    ref = f"Fixes #{issue_number}"
    return f"{text}\n\n{ref}".strip() if text else ref


def open_pull_request(
    owner: str,
    repo: str,
    title: str,
    head: str,
    base: str,
    token: str,
    *,
    body: str = "",
    draft: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": title,
        "head": head,
        "base": base,
        "body": body,
        "draft": draft,
    }
    return _github_request("POST", f"/repos/{owner}/{repo}/pulls", token, body=payload)


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


def _text_response(payload: Any) -> dict[str, Any]:
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, indent=2)
    return {"content": [{"type": "text", "text": text}]}


def _error_response(message: str) -> dict[str, Any]:
    return {"error": message}


def _require_token(event: dict[str, Any], context: Any) -> str | dict[str, Any]:
    token = resolve_github_token(event, context)
    if not token:
        return _error_response(
            "GitHub token not available. Forward OAuth via _headers.Authorization "
            "(agent Identity USER_FEDERATION), or set GITHUB_PERSONAL_ACCESS_TOKEN "
            "on the Lambda for fixture testing only."
        )
    return token


def inspect_repository(event: dict[str, Any], context: Any) -> dict[str, Any]:
    owner = (event.get("owner") or "").strip()
    repo = (event.get("repo") or "").strip()
    if not owner or not repo:
        return _error_response("owner and repo are required")

    token_or_err = _require_token(event, context)
    if isinstance(token_or_err, dict):
        return token_or_err
    token = token_or_err

    path = (event.get("path") or "").strip()
    ref = (event.get("ref") or "").strip() or None
    recursive = bool(event.get("recursive", True))

    try:
        if path:
            contents = get_path_contents(owner, repo, path, token, ref=ref)
            if isinstance(contents, list):
                summary = [
                    {
                        "path": item.get("path"),
                        "type": item.get("type"),
                        "size": item.get("size"),
                    }
                    for item in contents
                ]
                return _text_response({"path": path, "entries": summary})

            if contents.get("type") == "file":
                return _text_response(
                    {
                        "path": contents.get("path"),
                        "sha": contents.get("sha"),
                        "size": contents.get("size"),
                        "content": decode_file_content(contents),
                    }
                )
            return _text_response(contents)

        tree = get_repository_tree(
            owner,
            repo,
            token,
            ref=ref,
            path_filter=event.get("path_filter"),
            recursive=recursive,
        )
        entries = [
            {"path": item.get("path"), "type": item.get("type"), "size": item.get("size")}
            for item in tree.get("tree", [])
        ]
        return _text_response(
            {
                "owner": owner,
                "repo": repo,
                "ref": ref or get_default_branch(owner, repo, token),
                "truncated": tree.get("truncated", False),
                "entry_count": len(entries),
                "entries": entries[:500],
            }
        )
    except GitHubError as exc:
        return _error_response(f"GitHub API error ({exc.status}): {exc.message}")


def _write_file(
    event: dict[str, Any],
    context: Any,
    *,
    allowed_check,
    tool_label: str,
) -> dict[str, Any]:
    owner = (event.get("owner") or "").strip()
    repo = (event.get("repo") or "").strip()
    path = normalize_path(event.get("path") or "")
    content = event.get("content")
    message = (event.get("message") or "").strip()

    if not owner or not repo:
        return _error_response("owner and repo are required")
    if not path:
        return _error_response("path is required")
    if content is None:
        return _error_response("content is required")
    if not message:
        return _error_response("message is required")

    if not allowed_check(path):
        return _error_response(
            f"Path {path!r} is not allowed for {tool_label}. "
            "Documentation paths: README* and docs/**."
        )

    token_or_err = _require_token(event, context)
    if isinstance(token_or_err, dict):
        return token_or_err
    token = token_or_err

    base_ref = (event.get("base_ref") or "").strip() or None
    branch = (event.get("branch") or "").strip()
    if not branch:
        issue = event.get("issue_number")
        suffix = f"issue-{issue}" if issue else "update"
        branch = f"agent/{tool_label.replace(' ', '-')}/{suffix}"

    try:
        ensure_branch(owner, repo, branch, token, from_ref=base_ref)
        existing_sha = None
        try:
            existing = get_path_contents(owner, repo, path, token, ref=branch)
            if isinstance(existing, dict) and existing.get("type") == "file":
                existing_sha = existing.get("sha")
        except GitHubError as exc:
            if exc.status != 404:
                raise

        result = create_or_update_file(
            owner,
            repo,
            path,
            str(content),
            message,
            token,
            branch=branch,
            sha=existing_sha,
        )
        commit = result.get("commit", {})
        return _text_response(
            {
                "tool": tool_label,
                "owner": owner,
                "repo": repo,
                "path": path,
                "branch": branch,
                "commit_sha": commit.get("sha"),
                "html_url": (result.get("content") or {}).get("html_url"),
            }
        )
    except GitHubError as exc:
        return _error_response(f"GitHub API error ({exc.status}): {exc.message}")


def update_documentation(event: dict[str, Any], context: Any) -> dict[str, Any]:
    return _write_file(
        event,
        context,
        allowed_check=is_documentation_path,
        tool_label="update_documentation",
    )


def modify_source_code(event: dict[str, Any], context: Any) -> dict[str, Any]:
    return _write_file(
        event,
        context,
        allowed_check=is_source_path,
        tool_label="modify_source_code",
    )


def create_pull_request(event: dict[str, Any], context: Any) -> dict[str, Any]:
    owner = (event.get("owner") or "").strip()
    repo = (event.get("repo") or "").strip()
    title = (event.get("title") or "").strip()
    head = (event.get("head") or event.get("branch") or "").strip()
    base = (event.get("base") or "").strip()
    body = event.get("body")
    draft = bool(event.get("draft", False))
    issue_number = event.get("issue_number")

    if not owner or not repo:
        return _error_response("owner and repo are required")
    if not title:
        return _error_response("title is required")
    if not head:
        return _error_response("head (branch with commits) is required")

    if issue_number is not None:
        try:
            issue_number = int(issue_number)
        except (TypeError, ValueError):
            return _error_response("issue_number must be an integer")

    token_or_err = _require_token(event, context)
    if isinstance(token_or_err, dict):
        return token_or_err
    token = token_or_err

    try:
        if not base:
            base = get_default_branch(owner, repo, token)
        pr = open_pull_request(
            owner,
            repo,
            title,
            head,
            base,
            token,
            body=build_pr_body(str(body) if body is not None else None, issue_number),
            draft=draft,
        )
        return _text_response(
            {
                "tool": "create_pull_request",
                "owner": owner,
                "repo": repo,
                "number": pr.get("number"),
                "title": pr.get("title"),
                "state": pr.get("state"),
                "draft": pr.get("draft"),
                "html_url": pr.get("html_url"),
                "head": (pr.get("head") or {}).get("ref"),
                "base": (pr.get("base") or {}).get("ref"),
            }
        )
    except GitHubError as exc:
        return _error_response(f"GitHub API error ({exc.status}): {exc.message}")


TOOL_HANDLERS: dict[str, Callable[[dict[str, Any], Any], dict[str, Any]]] = {
    "inspect_repository": inspect_repository,
    "update_documentation": update_documentation,
    "modify_source_code": modify_source_code,
    "create_pull_request": create_pull_request,
}


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------


def _parse_tool_name(context: Any) -> str:
    custom = getattr(getattr(context, "client_context", None), "custom", None) or {}
    raw = custom.get("bedrockAgentCoreToolName", "")
    if TOOL_DELIMITER in raw:
        return raw[raw.index(TOOL_DELIMITER) + len(TOOL_DELIMITER) :]
    return raw


def _custom_get(context: Any, key: str) -> str:
    custom = getattr(getattr(context, "client_context", None), "custom", None) or {}
    return str(custom.get(key, ""))


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    logger.info("Gateway invoke event=%s", json.dumps(_event_for_log(event)))

    try:
        tool_name = _parse_tool_name(context)
        if not tool_name:
            return {"error": "bedrockAgentCoreToolName missing from Lambda context"}

        handler = TOOL_HANDLERS.get(tool_name)
        if handler is None:
            return {
                "error": (
                    f"Unknown tool {tool_name!r}. "
                    f"Expected one of: {', '.join(sorted(TOOL_HANDLERS))}"
                )
            }

        logger.info(
            "Routing to tool=%s gateway_id=%s target_id=%s",
            tool_name,
            _custom_get(context, "bedrockAgentCoreGatewayId"),
            _custom_get(context, "bedrockAgentCoreTargetId"),
        )
        return handler(event, context)
    except Exception as exc:
        logger.exception("Unhandled error in lambda_handler")
        return {"error": f"Internal server error: {exc}"}
