"""
Module 9 – Notification Channel Adapters & Delivery Engine
==========================================================
Modular notification adapters for multi-channel dispatch:
    - IN-APP notification adapter
    - EMAIL notification adapter (development sandbox & safe mock)
    - SMS prototype adapter
    - PUSH notification prototype adapter
    - SECURE INTERNAL API prototype adapter

AI Safety Invariant:
    Notifications must NEVER contain raw CCTV image frames, facial crop vectors,
    or biometric embeddings.  Recipients receive operational metadata and
    a secure link back to the authorized dashboard.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from app.core.config import settings
from app.models.alert import (
    AlertDB,
    AlertNotificationDB,
    AlertRecipientDB,
    AlertStatus,
    DeliveryChannel,
)

logger = logging.getLogger(__name__)


@dataclass
class NotificationDeliveryResult:
    success: bool
    status: str
    delivered_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    message_payload: Optional[str] = None


def build_standard_alert_message(alert: AlertDB, recipient: AlertRecipientDB) -> str:
    """
    Standardized, sanitized notification message according to specification.
    Does NOT contain sensitive biometric data or raw CCTV frames.
    """
    created = alert.created_at or datetime.utcnow()
    det_time = created.strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        "NEW AUTHORIZED ALERT\n\n"
        f"Alert: {alert.alert_number}\n\n"
        f"Case: {alert.case_number}\n"
        f"Category: {alert.category}\n"
        f"Priority: {alert.priority}\n\n"
        "A reviewed event has been approved for operational follow-up.\n\n"
        f"Camera: {alert.detected_camera_code or 'CCTV-MONITORED'}\n"
        f"Location: {alert.detected_location or 'Authorized Monitored Zone'}\n"
        f"Detection Time: {det_time}\n"
        "Review Status: CONFIRMED FOR ACTION\n\n"
        f"Recipient Role: {recipient.recipient_type}\n\n"
        "Please open the secure SENTINEX investigation dashboard for authorized "
        "evidence and further operational information."
    )


class BaseNotificationAdapter(ABC):
    """Abstract interface that every notification channel must implement."""

    @abstractmethod
    async def send_notification(
        self,
        alert: AlertDB,
        recipient: AlertRecipientDB,
        notification: AlertNotificationDB,
    ) -> NotificationDeliveryResult:
        """Dispatches an alert notification to the target recipient."""
        raise NotImplementedError

    @abstractmethod
    async def get_delivery_status(self, notification_id: int) -> str:
        """Polls or queries current delivery status."""
        raise NotImplementedError

    @abstractmethod
    async def retry_notification(
        self,
        alert: AlertDB,
        recipient: AlertRecipientDB,
        notification: AlertNotificationDB,
    ) -> NotificationDeliveryResult:
        """Retries transmission of a failed notification."""
        raise NotImplementedError


class InAppNotificationAdapter(BaseNotificationAdapter):
    """
    Delivers notifications directly into the in-app officer alert center.
    """

    async def send_notification(
        self,
        alert: AlertDB,
        recipient: AlertRecipientDB,
        notification: AlertNotificationDB,
    ) -> NotificationDeliveryResult:
        payload = build_standard_alert_message(alert, recipient)
        now = datetime.utcnow()
        logger.info(
            "[InAppNotification] Delivered to dept_id=%d for alert=%s",
            recipient.department_id,
            alert.alert_number,
        )
        return NotificationDeliveryResult(
            success=True,
            status=AlertStatus.DELIVERED.value,
            delivered_at=now,
            message_payload=payload,
        )

    async def get_delivery_status(self, notification_id: int) -> str:
        return AlertStatus.DELIVERED.value

    async def retry_notification(
        self,
        alert: AlertDB,
        recipient: AlertRecipientDB,
        notification: AlertNotificationDB,
    ) -> NotificationDeliveryResult:
        return await self.send_notification(alert, recipient, notification)


class EmailNotificationAdapter(BaseNotificationAdapter):
    """
    Safely delivers emails in development / test environments without
    sending real emails to external mailboxes unless configured.
    """

    async def send_notification(
        self,
        alert: AlertDB,
        recipient: AlertRecipientDB,
        notification: AlertNotificationDB,
    ) -> NotificationDeliveryResult:
        payload = build_standard_alert_message(alert, recipient)
        dest = recipient.destination_reference or settings.ALERT_DEV_EMAIL_SINK

        # Simulation for test suite: explicit simulation of delivery failures
        if dest.startswith("fail@") or "invalid" in dest:
            logger.warning("[EmailNotification] Simulated delivery failure for %s", dest)
            return NotificationDeliveryResult(
                success=False,
                status=AlertStatus.FAILED.value,
                error_code="SMTP_RECIPIENT_REJECTED",
                error_message=f"Recipient mailbox '{dest}' rejected incoming message.",
                message_payload=payload,
            )

        now = datetime.utcnow()
        logger.info(
            "[EmailNotification (%s)] Dispatched to %s for alert=%s",
            settings.ALERT_EMAIL_MODE,
            dest,
            alert.alert_number,
        )
        return NotificationDeliveryResult(
            success=True,
            status=AlertStatus.DELIVERED.value,
            delivered_at=now,
            message_payload=payload,
        )

    async def get_delivery_status(self, notification_id: int) -> str:
        return AlertStatus.DELIVERED.value

    async def retry_notification(
        self,
        alert: AlertDB,
        recipient: AlertRecipientDB,
        notification: AlertNotificationDB,
    ) -> NotificationDeliveryResult:
        return await self.send_notification(alert, recipient, notification)


class SMSNotificationAdapter(BaseNotificationAdapter):
    """Prototype SMS adapter for telecom gateways."""

    async def send_notification(
        self,
        alert: AlertDB,
        recipient: AlertRecipientDB,
        notification: AlertNotificationDB,
    ) -> NotificationDeliveryResult:
        payload = f"SENTINEX ALERT {alert.alert_number}: Case {alert.case_number} ({alert.category}). Log in to dashboard."
        return NotificationDeliveryResult(
            success=True,
            status=AlertStatus.SENT.value,
            delivered_at=datetime.utcnow(),
            message_payload=payload,
        )

    async def get_delivery_status(self, notification_id: int) -> str:
        return AlertStatus.SENT.value

    async def retry_notification(
        self,
        alert: AlertDB,
        recipient: AlertRecipientDB,
        notification: AlertNotificationDB,
    ) -> NotificationDeliveryResult:
        return await self.send_notification(alert, recipient, notification)


class PushNotificationAdapter(BaseNotificationAdapter):
    """Prototype push notification adapter (FCM / APNs)."""

    async def send_notification(
        self,
        alert: AlertDB,
        recipient: AlertRecipientDB,
        notification: AlertNotificationDB,
    ) -> NotificationDeliveryResult:
        payload = f"SENTINEX Operational Alert {alert.alert_number} - {alert.case_number}"
        return NotificationDeliveryResult(
            success=True,
            status=AlertStatus.SENT.value,
            delivered_at=datetime.utcnow(),
            message_payload=payload,
        )

    async def get_delivery_status(self, notification_id: int) -> str:
        return AlertStatus.SENT.value

    async def retry_notification(
        self,
        alert: AlertDB,
        recipient: AlertRecipientDB,
        notification: AlertNotificationDB,
    ) -> NotificationDeliveryResult:
        return await self.send_notification(alert, recipient, notification)


class SecureApiAdapter(BaseNotificationAdapter):
    """Prototype adapter for dispatching alerts to external law enforcement APIs."""

    async def send_notification(
        self,
        alert: AlertDB,
        recipient: AlertRecipientDB,
        notification: AlertNotificationDB,
    ) -> NotificationDeliveryResult:
        payload = build_standard_alert_message(alert, recipient)
        return NotificationDeliveryResult(
            success=True,
            status=AlertStatus.DELIVERED.value,
            delivered_at=datetime.utcnow(),
            message_payload=payload,
        )

    async def get_delivery_status(self, notification_id: int) -> str:
        return AlertStatus.DELIVERED.value

    async def retry_notification(
        self,
        alert: AlertDB,
        recipient: AlertRecipientDB,
        notification: AlertNotificationDB,
    ) -> NotificationDeliveryResult:
        return await self.send_notification(alert, recipient, notification)


class NotificationDispatcher:
    """
    Central dispatcher that coordinates notification delivery across all registered adapters.
    """

    def __init__(self) -> None:
        self._adapters: Dict[str, BaseNotificationAdapter] = {
            DeliveryChannel.IN_APP.value: InAppNotificationAdapter(),
            DeliveryChannel.EMAIL.value: EmailNotificationAdapter(),
            DeliveryChannel.SMS.value: SMSNotificationAdapter(),
            DeliveryChannel.PUSH_NOTIFICATION.value: PushNotificationAdapter(),
            DeliveryChannel.SECURE_INTERNAL_API.value: SecureApiAdapter(),
        }

    def get_adapter(self, channel: str) -> BaseNotificationAdapter:
        return self._adapters.get(channel, self._adapters[DeliveryChannel.IN_APP.value])

    async def dispatch(
        self,
        alert: AlertDB,
        recipient: AlertRecipientDB,
        notification: AlertNotificationDB,
    ) -> NotificationDeliveryResult:
        adapter = self.get_adapter(notification.channel)
        notification.attempt_count += 1
        notification.sent_at = datetime.utcnow()

        result = await adapter.send_notification(alert, recipient, notification)
        notification.status = result.status
        notification.message_payload = result.message_payload

        if result.success:
            notification.delivered_at = result.delivered_at or datetime.utcnow()
            notification.failed_at = None
            notification.error_code = None
            notification.error_message = None
        else:
            notification.failed_at = datetime.utcnow()
            notification.error_code = result.error_code
            notification.error_message = result.error_message

        return result


notification_dispatcher = NotificationDispatcher()
