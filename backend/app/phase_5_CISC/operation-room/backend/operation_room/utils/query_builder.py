"""
SQL Query Builder for DuckDB filtering.
Converts a JSON Filter DSL into safe, parameterized WHERE clauses.
"""
from typing import Any

OPERATORS = {
    "eq": "=",
    "neq": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "like": "LIKE",
    "ilike": "ILIKE",
    "not_like": "NOT LIKE",
    "contains": "ILIKE",
    "not_contains": "NOT ILIKE",
    "starts_with": "ILIKE",
    "ends_with": "ILIKE",
    "is_null": "IS NULL",
    "is_not_null": "IS NOT NULL",
    "in": "IN",
    "not_in": "NOT IN",
    "between": "BETWEEN"
}

def build_where_clause(filters: dict, allowed_fields: set[str] | None = None) -> tuple[str, list[Any]]:
    """
    Parses a MongoDB-style / GraphQL-style JSON filter dict into a SQL WHERE clause and parameters.
    
    Example input:
    {
      "AND": [
         {"field": "severity", "operator": "eq", "value": "HIGH"},
         {"OR": [
            {"field": "actor", "operator": "contains", "value": "admin"},
            {"field": "actor", "operator": "is_null"}
         ]}
      ]
    }
    """
    if not filters:
        return "", []

    def parse_node(node: dict) -> tuple[str, list[Any]]:
        if "AND" in node:
            clauses = []
            params = []
            for sub_node in node["AND"]:
                c, p = parse_node(sub_node)
                if c:
                    clauses.append(c)
                    params.extend(p)
            if not clauses:
                return "", []
            return "(" + " AND ".join(clauses) + ")", params
            
        elif "OR" in node:
            clauses = []
            params = []
            for sub_node in node["OR"]:
                c, p = parse_node(sub_node)
                if c:
                    clauses.append(c)
                    params.extend(p)
            if not clauses:
                return "", []
            return "(" + " OR ".join(clauses) + ")", params
            
        elif "NOT" in node:
            c, p = parse_node(node["NOT"])
            if not c:
                return "", []
            return f"(NOT {c})", p
            
        else:
            # Field operation
            field = node.get("field")
            op = node.get("operator", "eq").lower()
            val = node.get("value")
            
            if not field or op not in OPERATORS:
                return "", []
                
            # Prevent SQL injection by validating fields if a whitelist is provided
            if allowed_fields is not None and field not in allowed_fields:
                raise ValueError(f"Field '{field}' is not allowed for filtering.")
                
            sql_op = OPERATORS[op]
            
            if op in ("is_null", "is_not_null"):
                return f"{field} {sql_op}", []
                
            elif op in ("in", "not_in"):
                if not isinstance(val, (list, tuple)) or not val:
                    return "", []
                placeholders = ", ".join(["?" for _ in val])
                return f"{field} {sql_op} ({placeholders})", list(val)
                
            elif op == "between":
                if not isinstance(val, (list, tuple)) or len(val) != 2:
                    return "", []
                return f"{field} BETWEEN ? AND ?", list(val)
                
            elif op == "contains":
                return f"{field} {sql_op} ?", [f"%{val}%"]
                
            elif op == "not_contains":
                return f"{field} {sql_op} ?", [f"%{val}%"]
                
            elif op == "starts_with":
                return f"{field} {sql_op} ?", [f"{val}%"]
                
            elif op == "ends_with":
                return f"{field} {sql_op} ?", [f"%{val}"]
            
            else:
                return f"{field} {sql_op} ?", [val]

    sql, params = parse_node(filters)
    return sql, params
