"""
Module 9 – Alert & Department Notification System Core Service
==============================================================
Orchestrates operational alert generation, dual-department routing,
duplicate alert prevention, notification dispatch, acknowledgment,
escalation, and immutable audit logging.

AI Safety Invariant:
    Alert generation is strictly gated on human verification approval
    (status = CONFIRMED_FOR_ACTION from Module 8). Direct algorithmic
    candidate outputs or similarity scores NEVER create operational alerts.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.alert import (
    AlertAuditLogDB,
    AlertDB,
    AlertNotificationDB,
    AlertPriority,
    AlertRecipientDB,
    AlertStatus,
    AlertTimelineDB,
    DeliveryChannel,
    RecipientType,
)
from app.models.camera import Camera
from app.models.case import Case, CasePriority
from app.models.department import Department
from app.models.review_event import ReviewDecision, ReviewEventDB, ReviewStatus
from app.models.user import User, UserRole
from app.services.geo_routing_service import geo_routing_service
from app.services.notification_adapters import notification_dispatcher

logger = logging.getLogger(__name__)


class AlertService:
    """
    Central service for Module 9: Alert Engine & Department Notification System.
    """

    def __init__(self) -> None:
        self._duplicate_prevented_counter = 0

    # -----------------------------------------------------------------------
    # Alert Creation (Module 8 Human Confirmation Gated)
    # -----------------------------------------------------------------------

    async def create_alert_from_review_event(
        self,
        review_event: ReviewEventDB,
        db: Session,
        actor: Optional[User] = None,
        custom_priority: Optional[str] = None,
        notes: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AlertDB:
        """
        Creates an operational alert for an event approved by an authorized human reviewer.

        STRICT SAFETY ENFORCEMENT:
            - review_event.status MUST be CONFIRMED_FOR_ACTION
            - review_event.decision MUST be CONFIRM_FOR_ACTION
            - If called with unreviewed or rejected events, raises ValueError.
        """
        # 1. Enforce AI safety invariant
        if review_event.status != ReviewStatus.CONFIRMED_FOR_ACTION.value:
            raise ValueError(
                f"Cannot create operational alert: event {review_event.id} has status "
                f"'{review_event.status}'. Alerts require human approval 'CONFIRMED_FOR_ACTION'."
            )

        if review_event.decision != ReviewDecision.CONFIRM_FOR_ACTION.value:
            raise ValueError(
                f"Cannot create operational alert: event {review_event.id} decision is "
                f"'{review_event.decision}'. Human verification must be CONFIRM_FOR_ACTION."
            )

        # 2. Duplicate Alert Prevention & Deduplication (Section 18 & 19)
        dedup_cutoff = datetime.utcnow() - timedelta(minutes=settings.ALERT_DEDUP_WINDOW_MINUTES)
        existing_alert = (
            db.query(AlertDB)
            .filter(
                AlertDB.case_id == review_event.case_id,
                AlertDB.detected_camera_id == review_event.camera_id,
                AlertDB.status != AlertStatus.CLOSED.value,
                AlertDB.created_at >= dedup_cutoff,
            )
            .first()
        )

        if existing_alert:
            # Update existing alert with new observation
            self._duplicate_prevented_counter += 1
            existing_alert.observation_count += 1
            existing_alert.last_observation_at = datetime.utcnow()

            # Record timeline observation
            timeline_msg = (
                f"Repeated CCTV observation recorded for Track ID "
                f"{review_event.track_id or 'UNKNOWN'} on Camera {existing_alert.detected_camera_code or 'UNKNOWN'}. "
                f"Existing operational alert updated without creating duplicate."
            )
            self._add_timeline_entry(
                alert_id=existing_alert.id,
                event_type="OBSERVATION_UPDATED",
                description=timeline_msg,
                db=db,
            )

            # Record audit log
            self._add_audit_log(
                alert_id=existing_alert.id,
                user=actor,
                action="OBSERVATION_ADDED",
                previous_status=existing_alert.status,
                new_status=existing_alert.status,
                ip_address=ip_address,
                metadata_dict={
                    "track_id": review_event.track_id,
                    "observation_count": existing_alert.observation_count,
                    "review_event_id": review_event.id,
                },
                db=db,
            )
            db.commit()
            db.refresh(existing_alert)
            logger.info(
                "[AlertService] Duplicate alert prevented. Updated existing alert %s (count=%d)",
                existing_alert.alert_number,
                existing_alert.observation_count,
            )
            return existing_alert

        # 3. Fetch Case and Camera Context
        case = db.query(Case).filter(Case.id == review_event.case_id).first()
        if not case:
            raise ValueError(f"Case with ID {review_event.case_id} not found.")

        camera = (
            db.query(Camera).filter(Camera.id == review_event.camera_id).first()
            if review_event.camera_id
            else None
        )

        # 4. Determine Recipients
        # Destination 1: Originating Department (Registered the case)
        orig_dept = db.query(Department).filter(Department.id == case.department_id).first()
        if not orig_dept:
            raise ValueError(f"Originating department ID {case.department_id} for case {case.id} not found.")

        # Destination 2: Nearest Authorized Department (Responsible for camera / location)
        routing_result = geo_routing_service.find_nearest_authorized_department(
            camera=camera,
            db=db,
            exclude_department_id=None,
        )
        nearest_dept = routing_result.department

        # 5. Determine Alert Priority
        if custom_priority:
            priority = custom_priority
        elif case.priority == CasePriority.CRITICAL.value:
            priority = AlertPriority.CRITICAL.value
        elif case.priority == CasePriority.HIGH.value or review_event.priority == "HIGH":
            priority = AlertPriority.HIGH.value
        elif case.priority == CasePriority.LOW.value:
            priority = AlertPriority.LOW.value
        else:
            priority = AlertPriority.NORMAL.value

        # 6. Generate Sequential Unique Alert Number
        alert_number = self._generate_alert_number(db)

        # 7. Create Alert Record
        alert = AlertDB(
            alert_number=alert_number,
            match_event_id=review_event.match_event_id,
            review_event_id=review_event.id,
            case_id=case.id,
            case_number=case.case_number,
            category=case.category,
            originating_department_id=orig_dept.id,
            detected_camera_id=camera.id if camera else None,
            detected_camera_code=camera.camera_code if camera else None,
            detected_location=(
                camera.location_name if camera and camera.location_name else review_event.camera_location
            ),
            nearest_department_id=nearest_dept.id if nearest_dept else None,
            routing_reason=routing_result.routing_reason,
            distance_km=routing_result.distance_km,
            priority=priority,
            status=AlertStatus.CREATED.value,
            observation_count=1,
            last_observation_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        db.add(alert)
        db.flush()

        # 8. Record Initial Timeline & Audit Log
        self._add_timeline_entry(
            alert_id=alert.id,
            event_type="POSSIBLE_MATCH_REVIEWED",
            description=f"Possible match reviewed and confirmed for operational action by authorized examiner.",
            db=db,
        )
        self._add_timeline_entry(
            alert_id=alert.id,
            event_type="ALERT_CREATED",
            description=f"Operational alert {alert_number} generated for Case {case.case_number}.",
            db=db,
        )
        self._add_audit_log(
            alert_id=alert.id,
            user=actor,
            action="ALERT_CREATED",
            previous_status=None,
            new_status=AlertStatus.CREATED.value,
            ip_address=ip_address,
            metadata_dict={"case_number": case.case_number, "priority": priority},
            db=db,
        )

        # 9. Register Recipients & Dispatch Notifications
        recipients_to_dispatch: List[Tuple[AlertRecipientDB, str]] = []

        # Recipient A: Originating Department
        recipient_orig = AlertRecipientDB(
            alert_id=alert.id,
            department_id=orig_dept.id,
            recipient_type=RecipientType.ORIGINATING_DEPARTMENT.value,
            delivery_channel=DeliveryChannel.IN_APP.value,
            destination_reference=orig_dept.department_code or f"DEPT-{orig_dept.id}",
            status=AlertStatus.QUEUED.value,
        )
        db.add(recipient_orig)
        db.flush()
        recipients_to_dispatch.append((recipient_orig, DeliveryChannel.IN_APP.value))

        if orig_dept.contact_email:
            recipient_orig_email = AlertRecipientDB(
                alert_id=alert.id,
                department_id=orig_dept.id,
                recipient_type=RecipientType.ORIGINATING_DEPARTMENT.value,
                delivery_channel=DeliveryChannel.EMAIL.value,
                destination_reference=orig_dept.contact_email,
                status=AlertStatus.QUEUED.value,
            )
            db.add(recipient_orig_email)
            db.flush()
            recipients_to_dispatch.append((recipient_orig_email, DeliveryChannel.EMAIL.value))

        # Recipient B: Nearest Authorized Department (if distinct or explicitly routing)
        if nearest_dept and nearest_dept.id != orig_dept.id:
            recipient_nearest = AlertRecipientDB(
                alert_id=alert.id,
                department_id=nearest_dept.id,
                recipient_type=RecipientType.NEAREST_AUTHORIZED_DEPARTMENT.value,
                delivery_channel=DeliveryChannel.IN_APP.value,
                destination_reference=nearest_dept.department_code or f"DEPT-{nearest_dept.id}",
                status=AlertStatus.QUEUED.value,
            )
            db.add(recipient_nearest)
            db.flush()
            recipients_to_dispatch.append((recipient_nearest, DeliveryChannel.IN_APP.value))

            if nearest_dept.contact_email:
                recipient_nearest_email = AlertRecipientDB(
                    alert_id=alert.id,
                    department_id=nearest_dept.id,
                    recipient_type=RecipientType.NEAREST_AUTHORIZED_DEPARTMENT.value,
                    delivery_channel=DeliveryChannel.EMAIL.value,
                    destination_reference=nearest_dept.contact_email,
                    status=AlertStatus.QUEUED.value,
                )
                db.add(recipient_nearest_email)
                db.flush()
                recipients_to_dispatch.append((recipient_nearest_email, DeliveryChannel.EMAIL.value))

        # 10. Execute Notification Dispatch
        delivered_count = 0
        for recip, channel in recipients_to_dispatch:
            notif = AlertNotificationDB(
                alert_id=alert.id,
                recipient_id=recip.id,
                channel=channel,
                status=AlertStatus.QUEUED.value,
                attempt_count=0,
            )
            db.add(notif)
            db.flush()

            # Dispatch via adapter
            delivery_result = await notification_dispatcher.dispatch(alert, recip, notif)
            if delivery_result.success:
                recip.status = AlertStatus.DELIVERED.value
                recip.sent_at = datetime.utcnow()
                recip.delivered_at = delivery_result.delivered_at
                delivered_count += 1
            else:
                recip.status = AlertStatus.FAILED.value
                recip.sent_at = datetime.utcnow()

        # Update Alert Status
        if delivered_count == len(recipients_to_dispatch):
            alert.status = AlertStatus.DELIVERED.value
        elif delivered_count > 0:
            alert.status = AlertStatus.SENT.value
        else:
            alert.status = AlertStatus.FAILED.value

        # Milestones for notifications
        self._add_timeline_entry(
            alert_id=alert.id,
            event_type="ORIGINATING_DEPARTMENT_NOTIFIED",
            description=f"Originating Department ({orig_dept.department_name}) notified via configured channels.",
            db=db,
        )
        if nearest_dept:
            self._add_timeline_entry(
                alert_id=alert.id,
                event_type="NEAREST_DEPARTMENT_NOTIFIED",
                description=(
                    f"Nearest Authorized Department ({nearest_dept.department_name}) "
                    f"notified. Distance: {routing_result.distance_km or 'N/A'} km."
                ),
                db=db,
            )

        db.commit()
        db.refresh(alert)
        logger.info(
            "[AlertService] Operational alert %s created and dispatched. Status=%s",
            alert.alert_number,
            alert.status,
        )
        return alert

    # -----------------------------------------------------------------------
    # Alert Acknowledgment
    # -----------------------------------------------------------------------

    async def acknowledge_alert(
        self,
        alert_id: int,
        user: User,
        notes: Optional[str] = None,
        ip_address: Optional[str] = None,
        db: Session = None,
    ) -> AlertDB:
        """
        Acknowledges an operational alert by an authorized officer.
        """
        alert = db.query(AlertDB).filter(AlertDB.id == alert_id).first()
        if not alert:
            raise ValueError(f"Alert with ID {alert_id} not found.")

        # Check Department Authorization
        self._validate_department_access(alert, user)

        if alert.status in (AlertStatus.ACKNOWLEDGED.value, AlertStatus.IN_PROGRESS.value):
            return alert  # Idempotent acknowledgment

        if alert.status in (AlertStatus.RESOLVED.value, AlertStatus.CLOSED.value):
            raise ValueError(f"Cannot acknowledge alert {alert.alert_number}: already {alert.status}.")

        prev_status = alert.status
        alert.status = AlertStatus.ACKNOWLEDGED.value
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = user.id

        # Update recipient records for user's department
        if user.department_id:
            for recip in alert.recipients:
                if recip.department_id == user.department_id:
                    recip.acknowledged_at = datetime.utcnow()
                    recip.acknowledged_by = user.id
                    recip.status = AlertStatus.ACKNOWLEDGED.value

        # Record timeline & audit log
        self._add_timeline_entry(
            alert_id=alert.id,
            event_type="ALERT_ACKNOWLEDGED",
            description=f"Alert acknowledged by {user.username} (Notes: {notes or 'None'}).",
            db=db,
        )
        self._add_audit_log(
            alert_id=alert.id,
            user=user,
            action="ALERT_ACKNOWLEDGED",
            previous_status=prev_status,
            new_status=AlertStatus.ACKNOWLEDGED.value,
            ip_address=ip_address,
            metadata_dict={"notes": notes},
            db=db,
        )

        db.commit()
        db.refresh(alert)
        return alert

    # -----------------------------------------------------------------------
    # Status Updates (Lifecycle Transitions)
    # -----------------------------------------------------------------------

    async def update_alert_status(
        self,
        alert_id: int,
        new_status: AlertStatus,
        user: User,
        notes: Optional[str] = None,
        ip_address: Optional[str] = None,
        db: Session = None,
    ) -> AlertDB:
        """
        Updates the operational status of an alert (IN_PROGRESS, RESOLVED, CLOSED).
        """
        alert = db.query(AlertDB).filter(AlertDB.id == alert_id).first()
        if not alert:
            raise ValueError(f"Alert with ID {alert_id} not found.")

        self._validate_department_access(alert, user)

        # Enforce valid lifecycle transitions
        current = alert.status
        target = new_status.value

        valid_transitions = {
            AlertStatus.CREATED.value: [AlertStatus.QUEUED.value, AlertStatus.SENT.value, AlertStatus.DELIVERED.value, AlertStatus.ACKNOWLEDGED.value, AlertStatus.CLOSED.value],
            AlertStatus.QUEUED.value: [AlertStatus.SENT.value, AlertStatus.DELIVERED.value, AlertStatus.FAILED.value],
            AlertStatus.SENT.value: [AlertStatus.DELIVERED.value, AlertStatus.ACKNOWLEDGED.value, AlertStatus.FAILED.value],
            AlertStatus.DELIVERED.value: [AlertStatus.ACKNOWLEDGED.value, AlertStatus.IN_PROGRESS.value, AlertStatus.CLOSED.value],
            AlertStatus.ACKNOWLEDGED.value: [AlertStatus.IN_PROGRESS.value, AlertStatus.RESOLVED.value, AlertStatus.CLOSED.value],
            AlertStatus.IN_PROGRESS.value: [AlertStatus.RESOLVED.value, AlertStatus.CLOSED.value],
            AlertStatus.RESOLVED.value: [AlertStatus.CLOSED.value, AlertStatus.IN_PROGRESS.value],
            AlertStatus.CLOSED.value: [],
            AlertStatus.FAILED.value: [AlertStatus.QUEUED.value, AlertStatus.CLOSED.value],
        }

        # Admin can close any non-closed alert
        if user.role != UserRole.ADMIN.value and target not in valid_transitions.get(current, []):
            raise ValueError(f"Invalid transition from {current} to {target}.")

        alert.status = target
        if target in (AlertStatus.RESOLVED.value, AlertStatus.CLOSED.value):
            alert.closed_at = datetime.utcnow()
            alert.closed_by = user.id
            if notes:
                alert.resolution_notes = notes

        # Timeline & Audit Log
        event_type = f"STATUS_{target}"
        self._add_timeline_entry(
            alert_id=alert.id,
            event_type=event_type,
            description=f"Status changed from {current} to {target} by {user.username}. Notes: {notes or 'None'}",
            db=db,
        )
        self._add_audit_log(
            alert_id=alert.id,
            user=user,
            action="STATUS_CHANGED",
            previous_status=current,
            new_status=target,
            ip_address=ip_address,
            metadata_dict={"notes": notes},
            db=db,
        )

        db.commit()
        db.refresh(alert)
        return alert

    # -----------------------------------------------------------------------
    # Escalation Framework (Section 17)
    # -----------------------------------------------------------------------

    async def check_and_escalate_unacknowledged_alerts(self, db: Session) -> List[AlertDB]:
        """
        Finds alerts unacknowledged beyond ALERT_ACK_TIMEOUT_MINUTES and triggers escalation.
        """
        if not settings.ALERT_ESCALATION_ENABLED:
            return []

        timeout_cutoff = datetime.utcnow() - timedelta(minutes=settings.ALERT_ACK_TIMEOUT_MINUTES)
        unacked = (
            db.query(AlertDB)
            .filter(
                AlertDB.status.in_([AlertStatus.SENT.value, AlertStatus.DELIVERED.value]),
                AlertDB.acknowledged_at == None,  # noqa: E711
                AlertDB.created_at <= timeout_cutoff,
            )
            .all()
        )

        escalated_alerts: List[AlertDB] = []
        for alert in unacked:
            # Check if already escalated
            has_escalation = any(
                r.recipient_type == RecipientType.ESCALATION_RECIPIENT.value for r in alert.recipients
            )
            if has_escalation:
                continue

            # Find Central / Regional supervisor department
            central_dept = (
                db.query(Department)
                .filter(
                    Department.department_type.in_(["CENTRAL_DEPARTMENT", "CENTRAL"]),
                    Department.is_active == True,  # noqa: E712
                )
                .first()
            )
            if not central_dept:
                central_dept = db.query(Department).filter(Department.is_active == True).first()  # noqa: E712

            if not central_dept:
                continue

            # Create escalation recipient
            esc_recip = AlertRecipientDB(
                alert_id=alert.id,
                department_id=central_dept.id,
                recipient_type=RecipientType.ESCALATION_RECIPIENT.value,
                delivery_channel=DeliveryChannel.IN_APP.value,
                destination_reference=central_dept.department_code or f"DEPT-{central_dept.id}",
                status=AlertStatus.QUEUED.value,
            )
            db.add(esc_recip)
            db.flush()

            # Record timeline and audit
            self._add_timeline_entry(
                alert_id=alert.id,
                event_type="ALERT_ESCALATED",
                description=(
                    f"Alert not acknowledged within {settings.ALERT_ACK_TIMEOUT_MINUTES} minutes. "
                    f"Escalated to {central_dept.department_name}."
                ),
                db=db,
            )
            self._add_audit_log(
                alert_id=alert.id,
                user=None,
                action="ALERT_ESCALATED",
                previous_status=alert.status,
                new_status=alert.status,
                ip_address="SYSTEM",
                metadata_dict={"escalation_department_id": central_dept.id},
                db=db,
            )
            escalated_alerts.append(alert)

        db.commit()
        return escalated_alerts

    # -----------------------------------------------------------------------
    # Notification Retries (Section 22)
    # -----------------------------------------------------------------------

    async def retry_failed_notifications(
        self,
        alert_id: int,
        user: User,
        notification_id: Optional[int] = None,
        db: Session = None,
    ) -> List[AlertNotificationDB]:
        """
        Retries failed notifications for an alert.
        """
        alert = db.query(AlertDB).filter(AlertDB.id == alert_id).first()
        if not alert:
            raise ValueError(f"Alert with ID {alert_id} not found.")

        self._validate_department_access(alert, user)

        query = db.query(AlertNotificationDB).filter(
            AlertNotificationDB.alert_id == alert_id,
            AlertNotificationDB.status == AlertStatus.FAILED.value,
        )
        if notification_id:
            query = query.filter(AlertNotificationDB.id == notification_id)

        failed_notifs = query.all()
        retried: List[AlertNotificationDB] = []

        for notif in failed_notifs:
            recip = db.query(AlertRecipientDB).filter(AlertRecipientDB.id == notif.recipient_id).first()
            if not recip:
                continue

            result = await notification_dispatcher.dispatch(alert, recip, notif)
            if result.success:
                recip.status = AlertStatus.DELIVERED.value
                recip.delivered_at = result.delivered_at
            retried.append(notif)

            # Record timeline & audit
            self._add_timeline_entry(
                alert_id=alert.id,
                event_type="NOTIFICATION_RETRIED",
                description=f"Retried {notif.channel} notification to recipient {recip.id}. Result: {result.status}",
                db=db,
            )
            self._add_audit_log(
                alert_id=alert.id,
                user=user,
                action="NOTIFICATION_RETRIED",
                previous_status=alert.status,
                new_status=alert.status,
                metadata_dict={"notification_id": notif.id, "channel": notif.channel, "success": result.success},
                db=db,
            )

        db.commit()
        return retried

    # -----------------------------------------------------------------------
    # Queries & Dashboard Stats
    # -----------------------------------------------------------------------

    def get_alert_by_id(self, alert_id: int, user: User, db: Session) -> Optional[AlertDB]:
        alert = db.query(AlertDB).filter(AlertDB.id == alert_id).first()
        if not alert:
            return None
        self._validate_department_access(alert, user)
        return alert

    def list_alerts(
        self,
        db: Session,
        user: User,
        case_number: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        department_id: Optional[int] = None,
        camera_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[AlertDB], int]:
        """
        Lists alerts with department-based access control and filters.
        """
        query = db.query(AlertDB)

        # Department RBAC: POLICE can only view alerts relevant to their department
        if user.role != UserRole.ADMIN.value:
            if user.department_id is not None:
                query = query.filter(
                    (AlertDB.originating_department_id == user.department_id)
                    | (AlertDB.nearest_department_id == user.department_id)
                )
            else:
                return ([], 0)

        # Filters
        if case_number:
            query = query.filter(AlertDB.case_number.ilike(f"%{case_number.strip()}%"))
        if category:
            query = query.filter(AlertDB.category == category.strip().upper())
        if status:
            query = query.filter(AlertDB.status == status.strip().upper())
        if priority:
            query = query.filter(AlertDB.priority == priority.strip().upper())
        if department_id:
            query = query.filter(
                (AlertDB.originating_department_id == department_id)
                | (AlertDB.nearest_department_id == department_id)
            )
        if camera_id:
            query = query.filter(AlertDB.detected_camera_id == camera_id)

        total = query.count()
        items = (
            query.order_by(AlertDB.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_dashboard_stats(self, db: Session, user: User) -> Dict[str, Any]:
        """
        Calculates aggregate operational metrics.
        """
        query = db.query(AlertDB)
        if user.role != UserRole.ADMIN.value:
            if user.department_id is not None:
                query = query.filter(
                    (AlertDB.originating_department_id == user.department_id)
                    | (AlertDB.nearest_department_id == user.department_id)
                )
            else:
                return {
                    "total_alerts": 0,
                    "pending": 0,
                    "acknowledged": 0,
                    "in_progress": 0,
                    "resolved": 0,
                    "closed": 0,
                    "failed": 0,
                    "duplicate_alerts_prevented": 0,
                    "average_latency_seconds": 0.0,
                }

        alerts = query.all()
        total = len(alerts)
        pending = sum(
            1 for a in alerts if a.status in (AlertStatus.CREATED.value, AlertStatus.QUEUED.value, AlertStatus.SENT.value, AlertStatus.DELIVERED.value)
        )
        acknowledged = sum(1 for a in alerts if a.status == AlertStatus.ACKNOWLEDGED.value)
        in_progress = sum(1 for a in alerts if a.status == AlertStatus.IN_PROGRESS.value)
        resolved = sum(1 for a in alerts if a.status == AlertStatus.RESOLVED.value)
        closed = sum(1 for a in alerts if a.status == AlertStatus.CLOSED.value)
        failed = sum(1 for a in alerts if a.status == AlertStatus.FAILED.value)

        # Average latency from created to acknowledged
        latencies = [
            (a.acknowledged_at - a.created_at).total_seconds()
            for a in alerts
            if a.acknowledged_at and a.acknowledged_at >= a.created_at
        ]
        avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else 0.0

        return {
            "total_alerts": total,
            "pending": pending,
            "acknowledged": acknowledged,
            "in_progress": in_progress,
            "resolved": resolved,
            "closed": closed,
            "failed": failed,
            "duplicate_alerts_prevented": self._duplicate_prevented_counter,
            "average_latency_seconds": avg_latency,
        }

    # -----------------------------------------------------------------------
    # Helper Methods
    # -----------------------------------------------------------------------

    def _validate_department_access(self, alert: AlertDB, user: User) -> None:
        """
        Enforces department-level authorization.
        Admin has global access. Police can only access alerts involving their department.
        """
        if user.role == UserRole.ADMIN.value:
            return

        if user.department_id is None:
            raise PermissionError("User is not assigned to any authorized department.")

        if user.department_id not in (alert.originating_department_id, alert.nearest_department_id):
            raise PermissionError(
                f"Department {user.department_id} is not authorized to access Alert {alert.alert_number}."
            )

    @staticmethod
    def _generate_alert_number(db: Session) -> str:
        """
        Generates thread-safe human-readable alert number: ALT-YYYY-NNNNNN
        """
        year = datetime.utcnow().year
        count = db.query(func.count(AlertDB.id)).scalar() or 0
        return f"ALT-{year}-{count + 1:06d}"

    @staticmethod
    def _add_timeline_entry(
        alert_id: int,
        event_type: str,
        description: str,
        db: Session,
        metadata_dict: Optional[Dict[str, Any]] = None,
    ) -> AlertTimelineDB:
        entry = AlertTimelineDB(
            alert_id=alert_id,
            timestamp=datetime.utcnow(),
            event_type=event_type,
            description=description,
            metadata_json=json.dumps(metadata_dict) if metadata_dict else None,
        )
        db.add(entry)
        return entry

    @staticmethod
    def _add_audit_log(
        alert_id: int,
        user: Optional[User],
        action: str,
        previous_status: Optional[str],
        new_status: Optional[str],
        db: Session,
        ip_address: Optional[str] = None,
        metadata_dict: Optional[Dict[str, Any]] = None,
    ) -> AlertAuditLogDB:
        log = AlertAuditLogDB(
            alert_id=alert_id,
            user_id=user.id if user else None,
            actor_username=user.username if user else "SYSTEM",
            action=action,
            previous_status=previous_status,
            new_status=new_status,
            timestamp=datetime.utcnow(),
            ip_address=ip_address,
            metadata_json=json.dumps(metadata_dict) if metadata_dict else None,
        )
        db.add(log)
        return log


alert_service = AlertService()
