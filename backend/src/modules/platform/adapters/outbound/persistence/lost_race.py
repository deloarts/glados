"""
Tells whether a database error lost a race with a concurrent transaction,
which a fresh attempt on the current state can win: a deadlock, a
serialization failure or a row lock wait that hit `lock_timeout`. A statement
that hit `statement_timeout` is not one, because running it again costs the
same time again.
"""

_LOST_RACE_SQLSTATES = frozenset({"40P01", "40001", "55P03"})


def lost_race(exc: BaseException) -> bool:
    """Whether `exc` is a driver error with one of the lost race SQLSTATEs."""
    orig = getattr(exc, "orig", None)
    sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    return sqlstate in _LOST_RACE_SQLSTATES
