"""
Which credential store answers "is this the right password" for a user.

LOCAL, the bcrypt hash in user_table.
LDAP, a bind against the configured directory, and nothing else. The stored
        hash is an unusable sentinel (infrastructure/security/hashing), so no
        copy of a directory password lives here and there is no local
        credential to fall back to, not even while the directory is down.
"""


class AuthProvider:
    LOCAL = "local"
    LDAP = "ldap"

    ALL = (LOCAL, LDAP)
