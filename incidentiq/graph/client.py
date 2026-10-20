"""Neo4j graph database client management."""

from typing import Generator
from neo4j import GraphDatabase, Driver, Session
from incidentiq.config import settings

_driver: Driver | None = None


def get_driver() -> Driver:
    """Return a singleton Neo4j driver instance."""
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
    return _driver


def close_driver() -> None:
    """Close the singleton Neo4j driver if active."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def get_graph_session() -> Generator[Session, None, None]:
    """Dependency / context helper for obtaining a Neo4j session."""
    driver = get_driver()
    with driver.session() as session:
        yield session
