# miniOrange OAuth / SSO Plugin — Setup Guide

**Last updated:** April 2026 · **Owner:** Identity Platform Team · **Status:** Published

---

## 1. Prerequisites

Before configuring the OAuth / SSO plugin, ensure the following requirements are met:

- **Python 3.10+** is installed on the application server. Run `python --version` to confirm.
- **Network access** to the Identity Provider (IdP) endpoints — the server must be able to reach `https://idp.miniorange.com` over HTTPS (port 443). Verify with `curl -I https://idp.miniorange.com/.well-known/openid-configuration`.
- **Client credentials** (Client ID and Client Secret) have been provisioned by the IdP administrator. These are issued through the miniOrange Admin Console under **Apps → OAuth/OIDC → Add Application**.
- **A registered Redirect URI** has been configured in the IdP to match your application's callback endpoint (e.g., `https://app.example.com/callback`). Mismatched URIs will cause `redirect_uri_mismatch` errors during the authorization flow.

---

## 2. OAuth Configuration Steps

Follow these steps to configure the OAuth 2.0 integration end-to-end:

1. **Register your application** in the miniOrange Admin Console. Navigate to **Identity → Applications → Add New** and select the "OAuth 2.0 / OIDC" template. Note down the generated `Client ID` and `Client Secret`.

2. **Set the Redirect URI.** In the application settings, add your callback URL under **Authorized Redirect URIs**. For local development, use `http://localhost:8000/callback`. For production, use the HTTPS variant of your domain. Multiple URIs can be registered, separated by newlines.

3. **Configure scopes.** Under the **Permissions** tab, enable the scopes your application requires. The recommended minimum set is `openid`, `profile`, and `email`. Add `offline_access` if you need refresh-token support for long-lived sessions.

4. **Add environment variables.** Copy the `.env.template` file to `.env` in the project root and fill in the values:
   ```
   GEMINI_API_KEY=AIza... (or set GOOGLE_API_KEY)
   GEMINI_MODEL=gemini-3.1-flash-lite-preview
   CHROMA_PERSIST_DIR=./chroma_db
   COLLECTION_CODE=code_collection
   COLLECTION_DOCS=docs_collection
   ```
   Ensure your Gemini API key has sufficient quota for `generateContent` calls.

5. **Run the ingestion pipeline** to index the codebase and documentation:
   ```bash
   python backend/ingest.py
   ```
   A successful run will output `Ingestion complete — X code chunks, Y doc chunks indexed.` Verify by checking that the `chroma_db/` directory has been created and is non-empty.

---

## 3. Common Errors and Fixes

### Error: `redirect_uri_mismatch`

**Cause:** The Redirect URI sent during the authorization request does not exactly match any URI registered in the IdP application settings. Trailing slashes, port numbers, and protocol (`http` vs `https`) are all significant.

**Fix:** Open the miniOrange Admin Console → **Applications → Your App → Redirect URIs** and ensure the URI matches your application's callback path character-for-character. For local development, explicitly add `http://localhost:8000/callback`.

---

### Error: `invalid_grant — authorization code expired`

**Cause:** The authorization code returned in the callback was not exchanged for a token within the IdP's validity window (typically 60 seconds). This often happens during debugging when the developer pauses execution between the redirect and the token exchange.

**Fix:** Ensure the `exchange_token()` function is called immediately upon receiving the callback. Avoid breakpoints between the callback handler and the token-exchange HTTP request. If running behind a slow reverse proxy, check for upstream timeouts.

---

### Error: `NOT_FOUND` when calling Gemini model

**Cause:** The configured model name is not available for your API key/project, or the model does not support `generateContent`.

**Fix:** Set `GEMINI_MODEL` in `.env` to a supported model ID for your project. If unsure, list available models using your SDK and pick one that supports text generation.

---

### Error: `token_signature_verification_failed`

**Cause:** The token's HMAC signature does not match the expected value. This can occur if the signing secret has been rotated on the IdP side but the application is still using the old secret, or if the token was tampered with in transit.

**Fix:** Verify that the signing secret in your application matches the one configured in the IdP. Navigate to **Admin Console → Security → Signing Keys** and copy the latest HMAC key. Update the `mo-signing-secret-2026` value in `validate_token()` accordingly. If keys rotate automatically, implement a JWKS-based validation flow instead of static secrets.

---

## 4. Token Configuration

### Redirect URI Setup

The Redirect URI is the endpoint the IdP redirects the user to after authentication. It must be registered **exactly** in both the IdP and your application:

| Environment   | Redirect URI                              |
|---------------|-------------------------------------------|
| Local Dev     | `http://localhost:8000/callback`          |
| Staging       | `https://staging.example.com/callback`    |
| Production    | `https://app.example.com/callback`        |

### Scopes

Scopes control what data the access token grants permission to read:

| Scope            | Description                                      |
|------------------|--------------------------------------------------|
| `openid`         | Required — enables the OIDC flow and issues an ID token. |
| `profile`        | Returns the user's display name and profile picture.     |
| `email`          | Returns the user's verified email address.               |
| `offline_access` | Issues a refresh token for long-lived sessions.          |

### Client ID and Secret Setup

1. **Client ID** is a public identifier safe to include in front-end redirect URLs. It is not secret.
2. **Client Secret** must be stored securely on the server side (e.g., in `.env` or a secrets manager). **Never expose it in client-side code or commit it to version control.**
3. Rotate the Client Secret every 90 days via **Admin Console → Applications → Your App → Credentials → Regenerate Secret**. Update your `.env` file and restart the backend server after rotation.
