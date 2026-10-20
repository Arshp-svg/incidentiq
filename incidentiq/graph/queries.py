"""Graph schema constraints, seeding, and traversal queries."""

from typing import Any
from neo4j import Session
from incidentiq.graph.client import get_driver


def init_graph_schema(session: Session) -> None:
    """Create uniqueness constraints for Service, Incident, and Runbook nodes."""
    constraints = [
        "CREATE CONSTRAINT service_name IF NOT EXISTS FOR (s:Service) REQUIRE s.name IS UNIQUE;",
        "CREATE CONSTRAINT incident_id IF NOT EXISTS FOR (i:Incident) REQUIRE i.id IS UNIQUE;",
        "CREATE CONSTRAINT runbook_id IF NOT EXISTS FOR (r:Runbook) REQUIRE r.id IS UNIQUE;",
    ]
    for cypher in constraints:
        session.run(cypher)


def seed_service_topology(session: Session) -> dict[str, int]:
    """Seed the curated service dependency graph as specified in the blueprint."""
    seed_cypher = """
    // 1. Create Services and Data Stores
    MERGE (gateway:Service {name: "api-gateway", tier: "edge"})
    MERGE (checkout:Service {name: "checkout", tier: "frontend-api"})
    MERGE (orders:Service {name: "orders", tier: "backend-core"})
    MERGE (payments:Service {name: "payments", tier: "backend-core"})
    MERGE (inventory:Service {name: "inventory", tier: "backend-support"})
    MERGE (notifications:Service {name: "notifications", tier: "async-worker"})
    MERGE (orders_db:Service {name: "orders-db", type: "database"})
    MERGE (payment_gw:Service {name: "payment-gateway", type: "third-party"})

    // 2. Create Service Relationships
    MERGE (gateway)-[:CALLS]->(checkout)
    MERGE (checkout)-[:CALLS]->(orders)
    MERGE (orders)-[:CALLS]->(payments)
    MERGE (orders)-[:CALLS]->(inventory)
    MERGE (orders)-[:READS_FROM]->(orders_db)
    MERGE (orders)-[:CALLS]->(notifications)
    MERGE (payments)-[:CALLS]->(payment_gw)

    RETURN count(*) AS total;
    """
    session.run(seed_cypher)

    # Count nodes and edges
    node_count = session.run("MATCH (s:Service) RETURN count(s) AS count").single()["count"]
    rel_count = session.run("MATCH ()-[r]->() RETURN count(r) AS count").single()["count"]
    return {"services": node_count, "relationships": rel_count}


class GraphRepository:
    """Repository providing safe, parameterized graph traversals."""

    def __init__(self, session: Session | None = None) -> None:
        self._session = session

    def get_dependencies(self, service_name: str, depth: int = 2) -> dict[str, Any]:
        """Traverse upstream and downstream dependencies for a given service."""
        if depth < 1 or depth > 3:
            raise ValueError("depth must be between 1 and 3")

        cypher = f"""
        MATCH (target:Service {{name: $service_name}})
        OPTIONAL MATCH path = (target)-[r:CALLS|READS_FROM*1..{depth}]-(neighbor:Service)
        WITH target, collect(DISTINCT neighbor) AS neighbors, collect(DISTINCT r) AS rel_lists
        RETURN target.name AS root_service,
               [n IN neighbors | {{name: n.name, tier: coalesce(n.tier, 'unknown'), type: coalesce(n.type, 'service')}}] AS dependencies,
               size(neighbors) AS dependency_count
        """

        driver = get_driver()
        with (self._session if self._session else driver.session()) as session:
            result = session.run(cypher, service_name=service_name).single()
            if not result:
                return {"root_service": service_name, "dependencies": [], "dependency_count": 0}

            return {
                "root_service": result["root_service"],
                "dependencies": result["dependencies"],
                "dependency_count": result["dependency_count"],
            }


graph_repository = GraphRepository()
