"""
tests/integration/production_lot_repository

DB-backed coverage for SqlAlchemyProductionLotRepository. Like
test_production_order_repository.py, these tests drive the repository
directly against the throwaway SQLite database rather than through HTTP,
because what they cover only exists in SQL: a constraint interaction and
the filters that get_multi turns into queries.
"""
