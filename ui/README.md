# Demo UI (Streamlit) + Cognito custom login

```bash
cd ui
pip install -r requirements.txt
streamlit run app.py
```

Custom username/password form → Cognito `USER_PASSWORD_AUTH` → ID token verified via JWKS.

Requires `.env.shared` with pool/client. If the app client has a secret, set `COGNITO_APP_CLIENT_SECRET` (used for `SECRET_HASH`).
