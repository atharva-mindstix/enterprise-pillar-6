"""Self-check for create_pull_request helpers (no network)."""

from app import build_pr_body, create_pull_request


def test_build_pr_body() -> None:
    assert build_pr_body(None, None) == ""
    assert build_pr_body("Docs update", None) == "Docs update"
    assert build_pr_body(None, 24) == "Fixes #24"
    assert build_pr_body("Docs update", 24) == "Docs update\n\nFixes #24"
    assert build_pr_body("Closes #24 already", 24) == "Closes #24 already"


def test_create_pull_request_validates() -> None:
    err = create_pull_request({"owner": "o", "repo": "r", "title": "t"}, None)
    assert "head" in err["error"]
    err = create_pull_request(
        {"owner": "o", "repo": "r", "title": "t", "head": "b", "issue_number": "x"},
        None,
    )
    assert "issue_number" in err["error"]


if __name__ == "__main__":
    test_build_pr_body()
    test_create_pull_request_validates()
    print("ok")
