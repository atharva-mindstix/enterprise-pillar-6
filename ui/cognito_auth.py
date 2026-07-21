"""Cognito username/password login + JWT verification (no Hosted UI)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import boto3
import jwt
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from jwt import PyJWKClient

# App client has a secret → Cognito requires SECRET_HASH. Load here so login
# never depends on app.py import order; override so an empty shell var can't win.
load_dotenv(Path(__file__).resolve().parents[1] / ".env.shared", override=True)


def _cfg() -> dict[str, str]:
    region = os.environ["AWS_REGION"]
    pool_id = os.environ["COGNITO_USER_POOL_ID"]
    return {
        "region": region,
        "pool_id": pool_id,
        "client_id": os.environ["COGNITO_APP_CLIENT_ID"],
        "client_secret": os.getenv("COGNITO_APP_CLIENT_SECRET", "").strip(),
        "issuer": f"https://cognito-idp.{region}.amazonaws.com/{pool_id}",
    }


def _secret_hash(username: str) -> str | None:
    """Required when the app client has a client secret."""
    c = _cfg()
    secret = c["client_secret"]
    if not secret:
        return None
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{username}{c['client_id']}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def cognito_login(username: str, password: str) -> dict[str, str]:
    """
    Authenticate against Cognito (USER_PASSWORD_AUTH).
    Returns AuthenticationResult dict with IdToken, AccessToken, RefreshToken.
    """
    c = _cfg()
    params = {"USERNAME": username, "PASSWORD": password}
    sh = _secret_hash(username)
    if sh:
        params["SECRET_HASH"] = sh

    client = boto3.client("cognito-idp", region_name=c["region"])
    try:
        resp = client.initiate_auth(
            ClientId=c["client_id"],
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters=params,
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "ClientError")
        msg = exc.response.get("Error", {}).get("Message", str(exc))
        if "SECRET_HASH" in msg and not c["client_secret"]:
            raise RuntimeError(
                f"{code}: {msg}. Set COGNITO_APP_CLIENT_SECRET in .env.shared "
                "and restart Streamlit."
            ) from exc
        raise RuntimeError(f"{code}: {msg}") from exc

    challenge = resp.get("ChallengeName")
    if challenge:
        # ponytail: NEW_PASSWORD_REQUIRED / MFA not implemented in POC UI
        raise RuntimeError(
            f"Cognito challenge `{challenge}` — complete it in AWS Console "
            "or use a user that does not require a challenge."
        )

    result = resp.get("AuthenticationResult")
    if not result or "IdToken" not in result:
        raise RuntimeError("Cognito returned no IdToken")
    return result


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    c = _cfg()
    return PyJWKClient(f"{c['issuer']}/.well-known/jwks.json")


def verify_id_token(id_token: str) -> dict[str, Any]:
    """Verify Cognito ID token signature + iss/aud/exp."""
    c = _cfg()
    key = _jwks_client().get_signing_key_from_jwt(id_token)
    return jwt.decode(
        id_token,
        key.key,
        algorithms=["RS256"],
        audience=c["client_id"],
        issuer=c["issuer"],
        options={"require": ["exp", "iss", "sub"]},
    )


def user_from_claims(claims: dict[str, Any]) -> dict[str, Any]:
    return {
        "sub": claims["sub"],
        "email": claims.get("email") or claims.get("cognito:username") or claims["sub"],
        "claims": claims,
    }
