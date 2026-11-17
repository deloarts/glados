"""Per-user rate limit on user-composed mail, so a compromised account cannot
become an open relay.

It reuses the login attempt tracker: every send increments a counter and
the scope locks once it crosses the configured limit. "Per hour" is the
lock duration, not a sliding window, so a slow burst below the threshold is
not throttled; that imprecision is accepted.
"""


def mail_rate_exceeded(sent_in_window: int, limit: int) -> bool:
    """True once the count, which includes this send, crosses `limit`, so
    the crossing send itself is rejected."""
    return sent_in_window > limit
