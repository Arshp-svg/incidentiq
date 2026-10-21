"""MCP tool definition for service dependency traversal."""

from typing import Any
from incidentiq.graph.queries import graph_repository


def get_service_dependencies_impl(
    service_name: str,
    depth: int = 2,
) -> dict[str, Any]:
    """Return known dependencies for an application service from Neo4j.
    
    Security constraints:
    - Bounded depth (1 <= depth <= 3) to prevent runaway graph traversals.
    - Parameterized Cypher to prevent Cypher injection.
    """
    if depth < 1 or depth > 3:
        raise ValueError("depth must be between 1 and 3")

    return graph_repository.get_dependencies(
        service_name=service_name,
        depth=depth,
    )
