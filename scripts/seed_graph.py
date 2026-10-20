"""Seed service dependency graph into Neo4j and verify traversal."""

import sys
from dotenv import load_dotenv

load_dotenv()

from incidentiq.graph.client import get_driver, close_driver
from incidentiq.graph.queries import (
    init_graph_schema,
    seed_service_topology,
    graph_repository,
)


def seed_and_verify():
    print("\n--- Seeding Neo4j Service Dependency Graph ---")
    driver = get_driver()
    try:
        with driver.session() as session:
            # 1. Apply constraints
            print("[1/3] Creating Neo4j uniqueness constraints...", end=" ")
            init_graph_schema(session)
            print("DONE")

            # 2. Seed services and relationships
            print("[2/3] Seeding services and CALLS/READS_FROM relationships...", end=" ")
            counts = seed_service_topology(session)
            print(f"DONE ({counts['services']} services, {counts['relationships']} relationships)")

        # 3. Test dependency traversal
        print("[3/3] Testing dependency traversal for service 'checkout' (depth=2)...")
        deps = graph_repository.get_dependencies(service_name="checkout", depth=2)
        print(f"  Root Service: {deps['root_service']}")
        print(f"  Discovered Dependencies ({deps['dependency_count']}):")
        for d in deps["dependencies"]:
            print(f"    - {d['name']} (tier: {d['tier']}, type: {d['type']})")

        # Verify that orders and orders-db or payments are traversed
        dep_names = [d["name"] for d in deps["dependencies"]]
        assert "orders" in dep_names, "Expected 'orders' in dependencies of 'checkout'"
        print("\nNeo4j graph seeding and traversal verification SUCCESSFUL!\n")
    except Exception as e:
        print(f"\nSeeding FAILED: {e}")
        sys.exit(1)
    finally:
        close_driver()


if __name__ == "__main__":
    seed_and_verify()
