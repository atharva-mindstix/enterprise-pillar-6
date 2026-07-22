# Demo UI (Streamlit) + Cognito + AgentCore Identity GitHub (D1-B/C)

```bash
cd ui
pip install -r requirements.txt
streamlit run app.py
```

## Cognito

Custom username/password → `USER_PASSWORD_AUTH` → ID token verified via JWKS.

Requires `.env.shared` with pool/client. If the app client has a secret, set `COGNITO_APP_CLIENT_SECRET`.

## AgentCore JWT + workload token (D1-B)

After Cognito login the UI calls `GetWorkloadAccessTokenForJWT` with the Cognito **AccessToken** against workload `AGENTCORE_WORKLOAD_NAME` (default `githubWorkflowUi`).

| Piece | What |
| --- | --- |
| Inbound JWT authorizer | On `githubWorkflow` in `githubpoc/agentcore/agentcore.json` (`CUSTOM_JWT` + Cognito discovery / `allowedAudience`) |
| Deploy | `agentcore deploy` applies authorizer with the runtime |
| Workload exchange | `ui/agentcore_identity.py` → `get_workload_access_token_for_jwt` |
| Self-check | `python check_workload_token.py` (set `COGNITO_TEST_USERNAME` / `COGNITO_TEST_PASSWORD` for good-JWT path) |

### Invoke headers (for UI → deployed Runtime)

```http
POST https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{url-encoded-arn}/invocations?qualifier=DEFAULT
Authorization: Bearer <Cognito IdToken>
Content-Type: application/json
X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: <session-id>
```

Body example: `{"prompt": "hello", "session": {"sub": "...", "email": "..."}}`

Notes:

- Prefer **IdToken** when `allowedAudience` is the app client id (AccessToken often fails with aud mismatch).
- Do not put the workload token in the browser; keep it server-side (Streamlit session).
- Runtime service-linked workloads cannot be exchanged via the data-plane API by the caller — AgentCore exchanges on Bearer invoke. The standalone workload `githubWorkflowUi` is for the UI path (JWT exchange + GitHub `USER_FEDERATION`).

## Connect GitHub via AgentCore Identity (D1-C)

Flow: workload token → `GetResourceOauth2Token` (`USER_FEDERATION`, provider `pilllar-6-github`) → user opens `authorizationUrl` → AgentCore redirects to `AGENTCORE_OAUTH2_RETURN_URL` with `session_id` → UI calls `CompleteResourceTokenAuth` → vaulted token via `GetResourceOauth2Token` again for GitHub API.

### One-time GitHub OAuth App setup

1. GitHub → **Settings → Developer settings → OAuth Apps**
2. Authorization callback URL **must** be exactly the AgentCore Identity callback
   (replace any `http://localhost:8501/` callback — GitHub OAuth Apps use one URL;
   localhost is only AgentCore’s *return* URL after GitHub finishes, not GitHub’s redirect):

```text
https://bedrock-agentcore.us-west-2.amazonaws.com/identities/oauth2/callback/632c2a61-cbc6-4102-9b1e-17d47f886676
```

If GitHub shows **“redirect_uri is not associated with this application”**, the OAuth App
still has the wrong Authorization callback URL.

3. Client ID/secret are already stored on outbound identity `pilllar-6-github` (Secrets Manager). Keep the same values in `.env.shared` only if you still need them for local debugging; Connect GitHub no longer exchanges codes against GitHub directly.

### Env

```text
AGENTCORE_WORKLOAD_NAME=githubWorkflowUi
AGENTCORE_GITHUB_PROVIDER=pilllar-6-github
AGENTCORE_OAUTH2_RETURN_URL=http://localhost:8501/
AGENTCORE_GITHUB_CALLBACK_URL=https://bedrock-agentcore.us-west-2.amazonaws.com/identities/oauth2/callback/632c2a61-cbc6-4102-9b1e-17d47f886676
GITHUB_OAUTH_SCOPES=read:user repo
```

Workload `githubWorkflowUi` has `allowedResourceOauth2ReturnUrls` = `http://localhost:8501/` (required for 3LO session binding).

### Verify

1. Restart Streamlit → Cognito sign-in → workload token ready  
2. **Connect GitHub** → **Authorize on GitHub** → return to UI connected  
3. Create Agent Task → issue created; UI does **not** keep a long-lived GitHub token (fetched from AgentCore vault at use time)  
4. Cognito↔GitHub id map under `.data/github_links.json` (gitignored)
