"""
Scopes carried on a web JWT.

A full session token has **no** scope. Every named scope here is a
deliberately crippled token issued mid-authentication, valid only for the
handful of endpoints that finish the flow it belongs to.

ValidateWebToken allowlists scopes rather than blocklisting them, so a
scope added here is rejected everywhere until some endpoint explicitly
opts in. The reverse, remembering to blocklist a new scope on every
existing route, is the kind of thing that gets missed once and turns a
half-authenticated token into a full session.
"""

from typing import Final

# Password accepted, awaiting the 2FA code. Cannot do anything else.
TOTP_PENDING: Final = "totp_pending"

# Password accepted, but 2FA is mandatory and this user has not enrolled.
# Valid only for the enrolment endpoints, so the user can be walked
# through setup instead of being locked out.
TOTP_SETUP: Final = "totp_setup"

# Carries a passkey challenge from the options request to the verify
# request of a passkey login or registration. Never accepted as a session.
PASSKEY_LOGIN: Final = "passkey_login"
PASSKEY_REGISTRATION: Final = "passkey_registration"

# A full, unrestricted session carries no scope at all.
SESSION: Final = None
