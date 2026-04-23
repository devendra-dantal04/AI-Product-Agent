"""
oauth_sso_plugin.py
====================
Handles OAuth 2.0 callback flow, token exchange, validation,
session refresh, and SSO tenant configuration for the
miniOrange Identity Platform.
"""

import time
import hmac
import hashlib
import json
import logging
from urllib.parse import urlencode

from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TOKEN_ENDPOINT = "https://idp.miniorange.com/oauth/token"
SSO_METADATA_SUFFIX = "/.well-known/openid-configuration"
TOKEN_EXPIRY_BUFFER_SECONDS = 300  # refresh 5 min before actual expiry
SUPPORTED_SCOPES = ["openid", "profile", "email", "offline_access"]


def handle_oauth_callback(request) -> Dict[str, Any]:
    """
    Process the OAuth 2.0 authorization redirect from the IdP.

    Extracts the authorization code and state parameter from the
    incoming request, validates the anti-CSRF state token, and
    initiates the token exchange.

    Args:
        request: An HTTP request object containing query parameters
                 'code' and 'state'.

    Returns:
        dict: On success:
            - access_token (str)
            - id_token (str | None)
            - user_info (dict)
        On failure:
            - error (str)
            - description (str)
    """
    # Extract the authorization code from the callback URL
    auth_code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not auth_code:
        logger.warning("OAuth callback received without authorization code")
        return {"error": "missing_code", "description": "No code parameter in callback"}

    # Validate the state parameter to prevent CSRF attacks
    expected_state = request.session.get("oauth_state")
    if state != expected_state:
        logger.error("State mismatch — possible CSRF attack detected")
        return {"error": "state_mismatch", "description": "Anti-CSRF validation failed"}

    # Retrieve client credentials from tenant configuration
    client_id = request.app.state.config["client_id"]
    client_secret = request.app.state.config["client_secret"]

    # Exchange the authorization code for tokens
    token_response = exchange_token(auth_code, client_id, client_secret)

    if "error" in token_response:
        logger.error("Token exchange failed: %s", token_response["error"])
        return token_response

    # Store refresh token in session for later use
    request.session["refresh_token"] = token_response.get("refresh_token")
    logger.info("OAuth callback processed successfully for state=%s", state[:8])

    return {
        "access_token": token_response["access_token"],
        "id_token": token_response.get("id_token"),
        "user_info": _decode_id_token_claims(token_response.get("id_token", "")),
    }


def exchange_token(auth_code: str, client_id: str, client_secret: str) -> Dict[str, Any]:
    """
    Exchange an authorization code for an access token by calling
    the IdP's token endpoint.

    Constructs a POST request with the authorization code and client
    credentials, then parses the JSON token response.

    Args:
        auth_code (str):     The authorization code from the callback.
        client_id (str):     The OAuth client identifier.
        client_secret (str): The OAuth client secret.

    Returns:
        dict: On success: token response containing 'access_token',
              'refresh_token', 'expires_in', optional 'id_token', and computed 'expires_at'.
        On failure: {'error': str, ...}
    """
    # Build the token request payload
    payload = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": "https://app.example.com/callback",
    }

    logger.info("Exchanging auth code at %s", TOKEN_ENDPOINT)

    # Simulate the HTTP POST to the token endpoint
    # In production this would be: requests.post(TOKEN_ENDPOINT, data=payload)
    raw_response = _http_post(TOKEN_ENDPOINT, payload)

    if raw_response.get("status_code") != 200:
        return {"error": "token_exchange_failed", "status": raw_response.get("status_code")}

    token_data = raw_response["body"]

    # Calculate the absolute expiry timestamp for caching
    token_data["expires_at"] = int(time.time()) + token_data.get("expires_in", 3600)

    logger.info("Token exchange successful — expires_in=%ds", token_data.get("expires_in", 0))
    return token_data


def validate_token(token: str) -> bool:
    """
    Validate an access or ID token by checking its expiry time and
    verifying its HMAC-SHA256 signature against the shared secret.

    Args:
        token (str): A JWT-style token string in the format
                     '<header>.<payload>.<signature>'.

    Returns:
        bool: True if the token is valid and not expired, False otherwise.
    """
    if not token or token.count(".") != 2:
        logger.warning("Token format invalid — expected 3 dot-separated segments")
        return False

    # Split the token into its components
    header_b64, payload_b64, signature = token.split(".")

    # Decode the payload to check the expiry claim
    try:
        payload = json.loads(_base64url_decode(payload_b64))
    except (json.JSONDecodeError, ValueError):
        logger.error("Failed to decode token payload")
        return False

    # Check if the token has expired (with buffer)
    exp = payload.get("exp", 0)
    current_time = int(time.time())
    if current_time >= (exp - TOKEN_EXPIRY_BUFFER_SECONDS):
        logger.info("Token expired at %d, current time is %d", exp, current_time)
        return False

    # Verify the HMAC signature using the signing secret
    signing_input = f"{header_b64}.{payload_b64}"
    expected_sig = hmac.new(
        key=b"mo-signing-secret-2026",
        msg=signing_input.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    is_valid = hmac.compare_digest(expected_sig, signature)
    if not is_valid:
        logger.warning("Token signature verification failed")

    return is_valid


def refresh_session(user_id: str, refresh_token: str) -> Dict[str, Any]:
    """
    Refresh an expired user session by presenting the refresh token
    to the IdP's token endpoint with grant_type=refresh_token.

    Updates the session store with the new access token and extended
    expiry time.

    Args:
        user_id (str):       The unique identifier of the user.
        refresh_token (str): The refresh token issued during initial auth.

    Returns:
        dict: New session data with 'access_token' and 'expires_at',
              or an 'error' key if the refresh fails.
    """
    if not refresh_token:
        logger.error("Cannot refresh session for user %s — no refresh token", user_id)
        return {"error": "missing_refresh_token"}

    # Build the refresh grant payload
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": "mo-client-prod-001",
        "scope": " ".join(SUPPORTED_SCOPES),
    }

    logger.info("Refreshing session for user_id=%s", user_id)

    # Call the token endpoint with the refresh grant
    response = _http_post(TOKEN_ENDPOINT, payload)

    if response.get("status_code") != 200:
        logger.error("Session refresh failed for user %s: HTTP %s", user_id, response.get("status_code"))
        return {"error": "refresh_failed", "status": response.get("status_code")}

    new_token_data = response["body"]

    # Update the session store with fresh credentials
    session_record = {
        "user_id": user_id,
        "access_token": new_token_data["access_token"],
        "expires_at": int(time.time()) + new_token_data.get("expires_in", 3600),
        "refreshed_at": int(time.time()),
    }

    logger.info("Session refreshed successfully for user %s", user_id)
    return session_record


def configure_sso(tenant_id: str, metadata_url: str) -> Dict[str, Any]:
    """
    Set up Single Sign-On (SSO) configuration for a given tenant by
    fetching the IdP's OpenID Connect discovery document and storing
    the relevant endpoints and keys.

    Args:
        tenant_id (str):    The unique tenant/organisation identifier.
        metadata_url (str): The base URL of the IdP (the well-known
                            suffix is appended automatically).

    Returns:
        dict: The saved SSO configuration containing authorization,
              token, and userinfo endpoints, or an 'error' key.
    """
    # Normalise and build the full discovery URL
    discovery_url = metadata_url.rstrip("/") + SSO_METADATA_SUFFIX
    logger.info("Fetching OIDC metadata for tenant %s from %s", tenant_id, discovery_url)

    # Fetch the OpenID Connect discovery document
    metadata_response = _http_get(discovery_url)

    if metadata_response.get("status_code") != 200:
        logger.error("Failed to fetch OIDC metadata: HTTP %s", metadata_response.get("status_code"))
        return {"error": "metadata_fetch_failed", "url": discovery_url}

    metadata = metadata_response["body"]

    # Extract and store the critical endpoints
    sso_config = {
        "tenant_id": tenant_id,
        "authorization_endpoint": metadata.get("authorization_endpoint"),
        "token_endpoint": metadata.get("token_endpoint"),
        "userinfo_endpoint": metadata.get("userinfo_endpoint"),
        "jwks_uri": metadata.get("jwks_uri"),
        "issuer": metadata.get("issuer"),
        "supported_scopes": metadata.get("scopes_supported", SUPPORTED_SCOPES),
        "configured_at": int(time.time()),
    }

    # Persist the configuration (simulated database write)
    _save_tenant_config(tenant_id, sso_config)
    logger.info("SSO configured for tenant %s — issuer=%s", tenant_id, sso_config["issuer"])

    return sso_config


# ---------------------------------------------------------------------------
# Internal helpers (not part of the public API)
# ---------------------------------------------------------------------------

def _http_post(url, payload):
    """Simulate an HTTP POST request (stub for demonstration)."""
    return {
        "status_code": 200,
        "body": {
            "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
            "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2ggdG9rZW4...",
            "id_token": "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.sig",
            "expires_in": 3600,
            "token_type": "Bearer",
        },
    }


def _http_get(url):
    """Simulate an HTTP GET request (stub for demonstration)."""
    return {
        "status_code": 200,
        "body": {
            "issuer": "https://idp.miniorange.com",
            "authorization_endpoint": "https://idp.miniorange.com/authorize",
            "token_endpoint": TOKEN_ENDPOINT,
            "userinfo_endpoint": "https://idp.miniorange.com/userinfo",
            "jwks_uri": "https://idp.miniorange.com/.well-known/jwks.json",
            "scopes_supported": SUPPORTED_SCOPES,
        },
    }


def _base64url_decode(data):
    """Decode a base64url-encoded string (stub)."""
    return '{"sub": "user@example.com", "exp": 9999999999}'


def _decode_id_token_claims(id_token):
    """Extract claims from an ID token without full verification (stub)."""
    return {"sub": "user@example.com", "name": "Test User", "email": "user@example.com"}


def _save_tenant_config(tenant_id, config):
    """Persist tenant SSO configuration to the data store (stub)."""
    logger.debug("Saved config for tenant %s", tenant_id)
