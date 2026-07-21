# Demo UI (Streamlit) + Cognito + GitHub OAuth

```bash
cd ui
pip install -r requirements.txt
streamlit run app.py
```

## Cognito

Custom username/password → `USER_PASSWORD_AUTH` → ID token verified via JWKS.

Requires `.env.shared` with pool/client. If the app client has a secret, set `COGNITO_APP_CLIENT_SECRET`.

## Connect GitHub (frontend OAuth)

1. GitHub → **Settings → Developer settings → OAuth Apps → New OAuth App**
   - Homepage URL: `http://localhost:8501/`
   - Authorization callback URL: `http://localhost:8501/` (must match `GITHUB_REDIRECT_URI`)
2. Put **Client ID** and **Client secret** in repo-root `.env.shared`:

```text
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
GITHUB_REDIRECT_URI=http://localhost:8501/
GITHUB_OAUTH_SCOPES=read:user repo
```

3. Restart Streamlit → Sign in with Cognito → **Connect GitHub** → approve → create a task (creates a real issue with label `agent-task`).

Access token stays in the Streamlit **server session** only; Cognito↔GitHub id mapping is stored under `.data/github_links.json` (gitignored). No long-lived GitHub token in the browser.

Upgrade path (later): AgentCore Identity `GetResourceOauth2Token` (`USER_FEDERATION`) instead of this direct OAuth App flow.
