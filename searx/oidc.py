# SPDX-License-Identifier: AGPL-3.0-or-later
"""OIDC / OAuth2 single sign-on via Authlib.

Configure the provider in ``settings.yml`` under the ``oidc:`` key.  Example
for Authentik::

    oidc:
      enable: true
      discovery_url: "https://auth.example.com/application/o/searxng/.well-known/openid-configuration"
      client_id: "searxng"
      client_secret: "changeme"
      userdb_path: "/var/lib/searxng/users.db"
"""

from flask import session, url_for
from authlib.integrations.flask_client import OAuth

from searx import logger, get_setting

logger = logger.getChild("oidc")

oauth = OAuth()
_enabled: bool = False


def init_oidc(app) -> None:
    """Register the OIDC provider with the Flask app.  No-op when disabled."""
    global _enabled
    if not get_setting("oidc.enable", False):
        logger.debug("OIDC disabled (oidc.enable = false)")
        return

    oauth.init_app(app)
    oauth.register(
        name="oidc",
        server_metadata_url=get_setting("oidc.discovery_url"),
        client_id=get_setting("oidc.client_id"),
        client_secret=get_setting("oidc.client_secret"),
        client_kwargs={"scope": "openid email profile"},
    )
    _enabled = True
    logger.info("OIDC enabled, discovery: %s", get_setting("oidc.discovery_url"))


def is_enabled() -> bool:
    return _enabled


def get_current_user() -> "dict | None":
    """Return the user dict stored in the session, or ``None``."""
    return session.get("oidc_user")


def begin_login(redirect_uri: str):
    """Initiate the authorization-code flow; returns a redirect response."""
    return oauth.oidc.authorize_redirect(redirect_uri)


def complete_login() -> dict:
    """Exchange the authorization code for tokens and return a user dict."""
    token = oauth.oidc.authorize_access_token()
    user_info = token.get("userinfo") or oauth.oidc.userinfo(token=token)
    return {
        "sub": user_info["sub"],
        "email": user_info.get("email", ""),
        "name": (
            user_info.get("name")
            or user_info.get("preferred_username")
            or user_info["sub"]
        ),
    }
