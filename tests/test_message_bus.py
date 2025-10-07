"""
Tests for Message Bus Service

Tests the aiokafka producer/consumer functionality with Redpanda.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.message_bus import MessageBusService


class TestMessageBusService:
    """Test cases for MessageBusService."""

    @pytest.fixture
    def message_bus_service(self):
        """Create a fresh message bus service for testing."""
        service = MessageBusService()
        # Override settings for testing
        service.bootstrap_servers = "localhost:9092"
        service.outbound_topic = "test.outbound"
        service.dlq_topic = "test.dlq"
        service.consumer_group = "test-group"
        return service

    @pytest.mark.asyncio
    async def test_send_outbound_message_success(self, message_bus_service):
        """Test successful sending of outbound message."""
        with patch("app.services.message_bus.AIOKafkaProducer") as mock_producer_class:
            mock_producer = AsyncMock()
            mock_producer_class.return_value = mock_producer

            # Manually set the producer instead of starting the service
            message_bus_service.producer = mock_producer

            # Test sending a message
            test_message = {"test": "data", "operation": "test_op"}
            result = await message_bus_service.send_outbound_message(test_message, "test_key")

            assert result is True
            mock_producer.send_and_wait.assert_called_once()
            call_args = mock_producer.send_and_wait.call_args

            # Verify the message was enriched with metadata
            sent_message = call_args[1]["value"]
            assert sent_message["test"] == "data"
            assert sent_message["operation"] == "test_op"
            assert "_metadata" in sent_message
            assert sent_message["_metadata"]["source"] == "redox_gateway"

    @pytest.mark.asyncio
    async def test_send_outbound_message_failure(self, message_bus_service):
        """Test handling of failed message sending."""
        with patch("app.services.message_bus.AIOKafkaProducer") as mock_producer_class:
            mock_producer = AsyncMock()
            mock_producer.send_and_wait.side_effect = Exception("Kafka error")
            mock_producer_class.return_value = mock_producer

            # Manually set the producer
            message_bus_service.producer = mock_producer

            # Mock the DLQ method
            with patch.object(message_bus_service, "_send_to_dlq") as mock_dlq:
                # Test sending a message that fails
                test_message = {"test": "data"}
                result = await message_bus_service.send_outbound_message(test_message, "test_key")

                assert result is False
                mock_dlq.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_to_dlq(self, message_bus_service):
        """Test sending messages to dead letter queue."""
        with patch("app.services.message_bus.AIOKafkaProducer") as mock_producer_class:
            mock_producer = AsyncMock()
            mock_producer_class.return_value = mock_producer

            # Manually set the producer
            message_bus_service.producer = mock_producer

            # Test sending to DLQ
            test_message = {"failed": "message"}
            await message_bus_service._send_to_dlq(test_message, "dlq_key", "test error")

            mock_producer.send_and_wait.assert_called_once()
            call_args = mock_producer.send_and_wait.call_args

            # Verify DLQ message structure
            dlq_message = call_args[1]["value"]
            assert dlq_message["original_message"] == test_message
            assert dlq_message["error"] == "test error"
            assert dlq_message["original_key"] == "dlq_key"
            assert dlq_message["topic"] == "test.outbound"  # Original topic

    @pytest.mark.asyncio
    async def test_get_topic_info(self, message_bus_service):
        """Test getting topic information."""
        # Test without starting the service
        info = await message_bus_service.get_topic_info()

        expected_info = {
            "bootstrap_servers": "localhost:9092",
            "topics": {"outbound": "test.outbound", "dlq": "test.dlq"},
            "consumer_group": "test-group",
            "status": "stopped",
        }

        assert info == expected_info

    @pytest.mark.asyncio
    async def test_service_lifecycle(self, message_bus_service):
        """Test starting and stopping the service."""
        with (
            patch("app.services.message_bus.AIOKafkaProducer") as mock_producer_class,
            patch("app.services.message_bus.AIOKafkaConsumer") as mock_consumer_class,
        ):

            mock_producer = AsyncMock()
            mock_consumer = AsyncMock()
            mock_producer_class.return_value = mock_producer
            mock_consumer_class.return_value = mock_consumer

            # Test startup
            await message_bus_service.start()
            assert message_bus_service.running is True
            assert message_bus_service.producer is not None
            assert message_bus_service.consumer is not None

            # Test shutdown
            await message_bus_service.stop()
            assert message_bus_service.running is False
            mock_producer.stop.assert_called_once()
            mock_consumer.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_message_processing(self, message_bus_service):
        """Test message processing from consumer."""
        with patch("app.services.message_bus.AIOKafkaConsumer") as mock_consumer_class:
            mock_consumer = AsyncMock()
            mock_consumer_class.return_value = mock_consumer

            # Mock a message
            mock_message = MagicMock()
            mock_message.key = b"test_key"
            mock_message.offset = 123
            mock_message.value = {"test": "processed_message"}

            # Set up consumer to yield one message then stop
            async def mock_iter():
                yield mock_message
                # Simulate stopping after one message
                raise KeyboardInterrupt()

            mock_consumer.__aiter__ = mock_iter

            # Start the service
            await message_bus_service.start()

            # Process messages (should handle one message then exit)
            try:
                await asyncio.wait_for(message_bus_service.process_messages(), timeout=1.0)
            except asyncio.TimeoutError:
                pass  # Expected due to our mock

            # Cleanup
            await message_bus_service.stop()


class TestMessageBusIntegration:
    """Integration tests for message bus with Redox gateway."""

    @pytest.mark.asyncio
    async def test_redox_gateway_message_bus_integration(self):
        """Test that Redox gateway sends messages to message bus on success."""
        # This would be an integration test that requires Kafka to be running
        # For now, we'll test the integration points

        with patch("app.services.message_bus.message_bus") as mock_bus:
            mock_bus.send_outbound_message = AsyncMock(return_value=True)

            # Import here to avoid circular imports in tests
            from app.integrations.redox_gateway import RedoxIntegrationGateway

            gateway = RedoxIntegrationGateway()

            # Mock the client method to simulate success
            with patch.object(gateway.client, "send_patient_admin_message") as mock_send:
                mock_send.return_value = {"status": "success"}

                # This should trigger message bus sending
                await gateway.send_patient_message({"patient": "data"})

                # Verify message bus was called
                mock_bus.send_outbound_message.assert_called_once()
                call_args = mock_bus.send_outbound_message.call_args

                message = call_args[0][0]  # First positional argument
                assert message["operation"] == "send patient NewPatient message"
                assert message["function"] == "send_patient_admin_message"
                assert message["result"] == {"status": "success"}

    @pytest.mark.asyncio
    async def test_redox_gateway_dlq_integration(self):
        """Test that Redox gateway sends failures to DLQ."""
        with patch("app.services.message_bus.message_bus") as mock_bus:
            mock_bus._send_to_dlq = AsyncMock()

            from app.integrations.redox_gateway import RedoxIntegrationGateway

            gateway = RedoxIntegrationGateway()

            # Mock the client method to simulate failure
            with patch.object(gateway.client, "send_patient_admin_message") as mock_send:
                mock_send.side_effect = Exception("API Error")

                # This should trigger DLQ sending
                with pytest.raises(Exception):
                    await gateway.send_patient_message({"patient": "data"})

                # Verify DLQ was called
                mock_bus._send_to_dlq.assert_called_once()
                call_args = mock_bus._send_to_dlq.call_args

                dlq_message = call_args[0][0]  # First positional argument
                assert dlq_message["operation"] == "send patient NewPatient message"
                assert dlq_message["function"] == "send_patient_admin_message"
                assert dlq_message["error_type"] == "Exception"
                assert "API Error" in dlq_message["error_message"]
