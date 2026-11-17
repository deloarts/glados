"""
tests/integration/repository_reads

Guards every repository read path against missing load options. Every
relationship on the ORM models is `lazy="raise_on_sql"`, so a query that
feeds a mapper without the repository's load-options function raises at
runtime the first time the mapper touches an unloaded relationship. Unit
tests use in-memory fakes and never see this; only a real session does.

Each covered repository has one scenario in one of the `test_*` modules.
The scenario seeds a fully linked row graph (`_graph.py`) through the real
repositories, then calls every public read method through `Reader`
(`_harness.py`). The reader detaches everything from the session before
each call, so no relationship can be satisfied from the identity map of an
earlier call, and it fails on an empty result, so the mapper really ran.

Coverage is enforced rather than hoped for. A scenario fails when a read
method of its repository was neither called nor exempted with a reason,
and `test_coverage.py` fails when a repository class has no scenario and
no exemption, or when a method name matches neither the read nor the write
naming rule.

Write methods are out of scope. `save*` methods reload through the same
load options with `populate_existing`, and every scenario seeds through
them, so the common write path is exercised implicitly.
"""
