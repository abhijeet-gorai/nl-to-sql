"""
SQL Query Validation Utilities
Uses sqlglot for robust SQL parsing and validation
"""

import sqlglot
from sqlglot import exp

# Expressions that modify data or schema
WRITE_EXPRESSIONS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.Grant,
    exp.Revoke,
)


def is_read_only_sql(query: str, dialect: str | None = None) -> bool:
    """
    Check if a SQL query is read-only (SELECT only).
    
    Args:
        query: The SQL query string to validate
        dialect: Optional sqlglot dialect (e.g., 'postgres', 'mysql', 'db2')
    
    Returns:
        True if the query is read-only, False otherwise
    """
    try:
        expressions = sqlglot.parse(query, read=dialect)
    except sqlglot.errors.ParseError:
        return False  # Invalid SQL is not allowed

    # Reject multiple statements (prevents SQL injection with semicolons)
    if len(expressions) != 1:
        return False

    tree = expressions[0]
    
    if tree is None:
        return False

    # Reject any write operation anywhere in the AST
    for node in tree.walk():
        if isinstance(node, WRITE_EXPRESSIONS):
            return False

    # Ensure top-level statement is SELECT or WITH (CTE)
    return isinstance(tree, (exp.Select, exp.With))
