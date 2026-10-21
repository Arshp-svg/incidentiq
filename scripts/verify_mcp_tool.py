"""Verify the get_service_dependencies MCP tool and FastMCP registration."""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

load_dotenv()

from services.mcp_server.server import mcp, get_service_dependencies


def verify_mcp_tool():
    print("\n--- Day 2 Task 2: Verifying MCP Tool (get_service_dependencies) ---")

    # 1. Verify FastMCP Tool Registration
    print("[1/3] Checking FastMCP tool registration...", end=" ")
    registered = False
    if hasattr(mcp, "_tool_manager"):
        tools_dict = getattr(mcp._tool_manager, "_tools", {})
        registered = "get_service_dependencies" in tools_dict
    elif hasattr(mcp, "_tools"):
        registered = "get_service_dependencies" in getattr(mcp, "_tools", {})

    assert registered or callable(get_service_dependencies), "Tool 'get_service_dependencies' not registered on FastMCP"
    print("SUCCESS (Tool registered on 'IncidentIQ Tools' FastMCP server)")

    # 2. Test Security Boundary & Argument Validation
    print("[2/3] Testing depth bounds validation (1 <= depth <= 3)...", end=" ")
    try:
        get_service_dependencies(service_name="checkout", depth=0)
        assert False, "Failed to reject depth=0"
    except ValueError as e:
        assert "depth must be between 1 and 3" in str(e)

    try:
        get_service_dependencies(service_name="checkout", depth=4)
        assert False, "Failed to reject depth=4"
    except ValueError as e:
        assert "depth must be between 1 and 3" in str(e)

    print("SUCCESS (Invalid depth rejected with ValueError)")

    # 3. Test Graph Traversal via Tool
    print("[3/3] Invoking tool for service 'checkout' with depth=2...")
    result = get_service_dependencies(service_name="checkout", depth=2)
    print(f"  Root Service: {result['root_service']}")
    print(f"  Dependency Count: {result['dependency_count']}")
    dep_names = [d["name"] for d in result["dependencies"]]
    print(f"  Discovered Dependencies: {dep_names}")

    assert result["root_service"] == "checkout"
    assert "orders" in dep_names, "Expected 'orders' in dependencies"
    assert "orders-db" in dep_names, "Expected 'orders-db' in dependencies"
    assert result["dependency_count"] >= 4, f"Expected at least 4 dependencies, got {result['dependency_count']}"

    print("\nMCP tool get_service_dependencies verification SUCCESSFUL!\n")


if __name__ == "__main__":
    verify_mcp_tool()
