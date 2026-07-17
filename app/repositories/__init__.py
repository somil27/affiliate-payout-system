"""Repository layer.

Repositories encapsulate query construction and DB-specific concerns.
They deliberately do NOT commit — that responsibility belongs to services
which own the unit-of-work boundary.
"""
