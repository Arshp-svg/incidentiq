"""Kafka event producer for publishing incident work notifications."""

import json
from kafka import KafkaProducer
from incidentiq.config import settings
from incidentiq.events.schemas import IncidentNotification


class IncidentEventProducer:
    def __init__(self) -> None:
        self.bootstrap_servers = settings.KAFKA_BOOTSTRAP_SERVERS
        self.topic = settings.KAFKA_TOPIC_INCIDENT_EVENTS
        self._producer: KafkaProducer | None = None

    def _get_producer(self) -> KafkaProducer:
        if self._producer is None:
            self._producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                retries=3,
                acks="all",
            )
        return self._producer

    def publish_incident_notification(self, notification: IncidentNotification) -> None:
        """Publish an incident notification to the Kafka topic."""
        producer = self._get_producer()
        key = str(notification.incident_id)
        future = producer.send(
            self.topic,
            key=key,
            value=notification.model_dump(mode="json"),
        )
        producer.flush()
        # Ensure message was acknowledged
        future.get(timeout=10)

    def close(self) -> None:
        if self._producer is not None:
            self._producer.close()
            self._producer = None


event_producer = IncidentEventProducer()
