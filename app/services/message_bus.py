"""
Message Bus Service using aiokafka for Redpanda integration.

This service provides:
- Producer for sending outbound messages to Kafka topics
- Consumer for processing messages and handling failures
- Dead Letter Queue (DLQ) for failed message processing
- Integration with Redox gateway for message echoing
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer  # type: ignore
from aiokafka.errors import KafkaError  # type: ignore

from ..core.config import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class MessageBusService:
    """Message bus service for handling Kafka messaging with Redpanda."""

    def __init__(self):
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.running = False

        # Get settings
        settings = get_settings()

        # Kafka configuration
        self.bootstrap_servers = settings.kafka_bootstrap_servers
        self.outbound_topic = settings.kafka_outbound_topic
        self.dlq_topic = settings.kafka_dlq_topic
        self.consumer_group = settings.kafka_consumer_group

    async def start(self):
        """Start the message bus service."""
        try:
            # Start producer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: str(k).encode("utf-8") if k else None,
                acks="all",  # Wait for all replicas to acknowledge
                retry_backoff_ms=1000,
            )
            await self.producer.start()
            logger.info(f"Message bus producer started on {self.bootstrap_servers}")

            # Start consumer for DLQ processing
            self.consumer = AIOKafkaConsumer(
                self.outbound_topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.consumer_group,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                key_deserializer=lambda k: k.decode("utf-8") if k else None,
                auto_offset_reset="earliest",
                enable_auto_commit=False,  # Manual commit for reliability
            )
            await self.consumer.start()
            logger.info(f"Message bus consumer started for topic: {self.outbound_topic}")

            self.running = True

        except Exception as e:
            logger.error(f"Failed to start message bus service: {e}")
            await self.stop()
            raise

    async def stop(self):
        """Stop the message bus service."""
        self.running = False

        if self.producer:
            await self.producer.stop()
            logger.info("Message bus producer stopped")

        if self.consumer:
            await self.consumer.stop()
            logger.info("Message bus consumer stopped")

    async def send_outbound_message(self, message: Dict[str, Any], key: Optional[str] = None) -> bool:
        """
        Send an outbound message to the Kafka topic.

        Args:
            message: The message payload to send
            key: Optional message key for partitioning

        Returns:
            bool: True if message was sent successfully
        """
        if not self.producer:
            logger.error("Message bus producer not initialized")
            return False

        try:
            # Add metadata to the message
            enriched_message = {
                **message,
                "_metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "redox_gateway",
                    "version": "1.0",
                },
            }

            await self.producer.send_and_wait(self.outbound_topic, value=enriched_message, key=key)

            logger.info(f"Sent outbound message to topic {self.outbound_topic}: {key or 'no-key'}")
            return True

        except KafkaError as e:
            logger.error(f"Failed to send message to Kafka: {e}")
            # Send to DLQ on failure
            await self._send_to_dlq(message, key, str(e))
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending message: {e}")
            await self._send_to_dlq(message, key, str(e))
            return False

    async def _send_to_dlq(self, message: Dict[str, Any], key: Optional[str], error: str):
        """Send a failed message to the Dead Letter Queue."""
        if not self.producer:
            logger.error("Cannot send to DLQ: producer not initialized")
            return

        try:
            dlq_message = {
                "original_message": message,
                "error": error,
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "original_key": key,
                "topic": self.outbound_topic,
            }

            await self.producer.send_and_wait(self.dlq_topic, value=dlq_message, key=key)

            logger.warning(f"Sent failed message to DLQ {self.dlq_topic}: {error}")

        except Exception as e:
            logger.error(f"Failed to send message to DLQ: {e}")

    async def process_messages(self):
        """Process messages from the outbound topic (for monitoring/echoing)."""
        if not self.consumer:
            logger.error("Message bus consumer not initialized")
            return

        try:
            async for message in self.consumer:
                try:
                    # Echo the message for monitoring/logging
                    logger.info(f"Echoed message from {self.outbound_topic}: key={message.key}, offset={message.offset}")

                    # Here you could add additional processing logic:
                    # - Message validation
                    # - Metrics collection
                    # - Content filtering
                    # - Archival to external systems

                    # Manually commit the message
                    await self.consumer.commit()

                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Send problematic message to DLQ
                    await self._send_to_dlq(message.value, message.key, f"Processing error: {str(e)}")

        except Exception as e:
            logger.error(f"Error in message processing loop: {e}")

    async def get_topic_info(self) -> Dict[str, Any]:
        """Get information about Kafka topics for monitoring."""
        # This is a simplified version - in production you'd use rpk or kafka admin client
        return {
            "bootstrap_servers": self.bootstrap_servers,
            "topics": {"outbound": self.outbound_topic, "dlq": self.dlq_topic},
            "consumer_group": self.consumer_group,
            "status": "running" if self.running else "stopped",
        }


# Global message bus instance
message_bus = MessageBusService()


async def get_message_bus() -> MessageBusService:
    """Dependency injection for message bus service."""
    return message_bus


async def start_message_bus():
    """Start the global message bus service."""
    await message_bus.start()


async def stop_message_bus():
    """Stop the global message bus service."""
    await message_bus.stop()
