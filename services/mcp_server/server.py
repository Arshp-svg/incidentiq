"""IncidentIQ FastMCP Server exposing read-only investigation tools."""

from typing import Any
from mcp.server.fastmcp import FastMCP
from services.mcp_server.tools.dependencies import get_service_dependencies_impl

# Create FastMCP server instance
mcp = FastMCP("IncidentIQ Tools")


@mcp.tool(name="get_service_dependencies", description="Return known upstream and downstream dependencies for an application service from Neo4j.")
def get_service_dependencies(
    service_name: str,
    depth: int = 2,
) -> dict[str, Any]:
    """Return known dependencies for an application service.
    
    Args:
        service_name: The microservice name to inspect (e.g. 'checkout', 'orders').
        depth: Traversal depth in the dependency graph (1 to 3).
    """
    return get_service_dependencies_impl(service_name=service_name, depth=depth)


if __name__ == "__main__":
    mcp.run()
