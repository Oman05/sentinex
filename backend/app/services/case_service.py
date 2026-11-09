from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.case import Case, CaseCategory, CasePriority, CaseStatus
from app.models.department import Department
from app.models.user import User
from app.utils.case_number_generator import generate_case_number


VALID_STATUS_TRANSITIONS = {
    CaseStatus.DRAFT.value: {CaseStatus.ACTIVE.value, CaseStatus.UNDER_REVIEW.value, CaseStatus.INACTIVE.value},
    CaseStatus.ACTIVE.value: {
        CaseStatus.UNDER_REVIEW.value,
        CaseStatus.POSSIBLE_MATCH.value,
        CaseStatus.VERIFIED.value,
        CaseStatus.CLOSED.value,
        CaseStatus.INACTIVE.value,
    },
    CaseStatus.UNDER_REVIEW.value: {
        CaseStatus.ACTIVE.value,
        CaseStatus.POSSIBLE_MATCH.value,
        CaseStatus.VERIFIED.value,
        CaseStatus.CLOSED.value,
        CaseStatus.INACTIVE.value,
    },
    CaseStatus.POSSIBLE_MATCH.value: {
        CaseStatus.ACTIVE.value,
        CaseStatus.VERIFIED.value,
        CaseStatus.CLOSED.value,
        CaseStatus.INACTIVE.value,
    },
    CaseStatus.VERIFIED.value: {
        CaseStatus.ACTIVE.value,
        CaseStatus.CLOSED.value,
        CaseStatus.INACTIVE.value,
    },
    CaseStatus.CLOSED.value: {CaseStatus.INACTIVE.value},
    CaseStatus.INACTIVE.value: {CaseStatus.ACTIVE.value, CaseStatus.DRAFT.value},
}


class CaseService:
    @staticmethod
    def _normalize_enum(value: str | Enum) -> str:
        return value.value if isinstance(value, Enum) else str(value)

    @staticmethod
    def validate_category(category: str | CaseCategory) -> str:
        normalized = CaseService._normalize_enum(category).upper()
        if normalized not in {CaseCategory.MISSING.value, CaseCategory.WANTED.value}:
            raise ValueError("Invalid category. Supported values are MISSING and WANTED")
        return normalized

    @staticmethod
    def validate_priority(priority: str | CasePriority) -> str:
        normalized = CaseService._normalize_enum(priority).upper()
        if normalized not in {CasePriority.LOW.value, CasePriority.MEDIUM.value, CasePriority.HIGH.value, CasePriority.CRITICAL.value}:
            raise ValueError("Invalid priority. Supported values are LOW, MEDIUM, HIGH, and CRITICAL")
        return normalized

    @staticmethod
    def validate_status(status: str | CaseStatus) -> str:
        normalized = CaseService._normalize_enum(status).upper()
        if normalized not in {member.value for member in CaseStatus}:
            raise ValueError("Invalid status value")
        return normalized

    @staticmethod
    def validate_status_transition(current_status: str, new_status: str) -> None:
        allowed = VALID_STATUS_TRANSITIONS.get(current_status.upper(), set())
        if new_status.upper() not in allowed:
            raise ValueError(
                f"Invalid status transition from {current_status} to {new_status}. Allowed: {sorted(allowed)}"
            )

    @staticmethod
    def ensure_department_exists(db: Session, department_id: int | None) -> None:
        if department_id is None:
            raise ValueError("Department is required")
        department = db.query(Department).filter(Department.id == department_id).first()
        if department is None:
            raise ValueError("Department not found")

    @staticmethod
    def get_case_or_404(db: Session, case_id: int) -> Case:
        case = db.query(Case).filter(Case.id == case_id).first()
        if case is None:
            raise ValueError("Case not found")
        return case

    @staticmethod
    def user_can_access_case(user: User, case: Case) -> bool:
        if user.role == "ADMIN":
            return True
        if user.department_id is None:
            return case.created_by == user.id
        return case.department_id == user.department_id or case.created_by == user.id

    @staticmethod
    def build_access_query(db: Session, user: User, include_inactive: bool = False):
        query = db.query(Case)
        if not include_inactive:
            query = query.filter(Case.is_active.is_(True))
        if user.role != "ADMIN":
            if user.department_id is not None:
                query = query.filter(or_(Case.department_id == user.department_id, Case.created_by == user.id))
            else:
                query = query.filter(Case.created_by == user.id)
        return query

    @staticmethod
    def apply_filters(
        query,
        *,
        category: str | None = None,
        status: str | None = None,
        department_id: int | None = None,
        priority: str | None = None,
        search: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ):
        if category:
            query = query.filter(Case.category == CaseService.validate_category(category))
        if status:
            query = query.filter(Case.status == CaseService.validate_status(status))
        if department_id is not None:
            query = query.filter(Case.department_id == department_id)
        if priority:
            query = query.filter(Case.priority == CaseService.validate_priority(priority))
        if search:
            search_term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Case.case_number.ilike(search_term),
                    Case.person_identifier.ilike(search_term),
                    Case.title.ilike(search_term),
                    Case.description.ilike(search_term),
                    Case.last_known_location.ilike(search_term),
                    Case.category.ilike(search_term),
                    Case.status.ilike(search_term),
                )
            )
        if start_date:
            query = query.filter(Case.created_at >= start_date)
        if end_date:
            query = query.filter(Case.created_at <= end_date)
        return query

    @staticmethod
    def create_case(db: Session, user: User, payload) -> Case:
        category = CaseService.validate_category(payload.category)
        priority = CaseService.validate_priority(payload.priority)

        department_id = payload.department_id or user.department_id
        CaseService.ensure_department_exists(db, department_id)

        if user.role != "ADMIN":
            if user.department_id is not None and department_id != user.department_id:
                raise PermissionError("You cannot create cases for another department")
            if user.department_id is None and payload.department_id is not None:
                raise PermissionError("Department assignment is not allowed for this user")

        case_number = generate_case_number(db, category)
        while db.query(Case).filter(Case.case_number == case_number).first():
            case_number = generate_case_number(db, category)

        case_status = CaseService.validate_status(payload.status) if payload.status else CaseStatus.DRAFT.value
        if case_status == CaseStatus.CLOSED.value:
            raise ValueError("A case cannot be created in a closed status")

        case = Case(
            case_number=case_number,
            category=category,
            title=payload.title.strip(),
            person_identifier=payload.person_identifier.strip(),
            description=payload.description.strip(),
            department_id=department_id,
            created_by=user.id,
            status=case_status,
            priority=priority,
            last_known_location=payload.last_known_location.strip() if payload.last_known_location else None,
            is_active=True,
            closed_at=None,
        )
        db.add(case)
        db.commit()
        db.refresh(case)
        CaseService.log_case_action(db, user.id, case.id, "CASE_CREATED", f"Created {category} case {case_number}")
        return case

    @staticmethod
    def update_case(db: Session, user: User, case: Case, payload) -> Case:
        if user.role != "ADMIN" and not CaseService.user_can_access_case(user, case):
            raise PermissionError("You do not have permission to update this case")

        if payload.title is not None:
            case.title = payload.title.strip()
        if payload.person_identifier is not None:
            case.person_identifier = payload.person_identifier.strip()
        if payload.description is not None:
            case.description = payload.description.strip()
        if payload.department_id is not None:
            if user.role != "ADMIN" and user.department_id is not None and payload.department_id != user.department_id:
                raise PermissionError("You cannot assign this case to a different department")
            CaseService.ensure_department_exists(db, payload.department_id)
            case.department_id = payload.department_id
        if payload.priority is not None:
            case.priority = CaseService.validate_priority(payload.priority)
        if payload.last_known_location is not None:
            case.last_known_location = payload.last_known_location.strip()
        if payload.category is not None:
            case.category = CaseService.validate_category(payload.category)
            if case.case_number.startswith("MP") and case.category == CaseCategory.WANTED.value:
                case.case_number = generate_case_number(db, case.category)
            if case.case_number.startswith("WP") and case.category == CaseCategory.MISSING.value:
                case.case_number = generate_case_number(db, case.category)
        case.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(case)
        CaseService.log_case_action(db, user.id, case.id, "CASE_UPDATED", "Updated case details")
        return case

    @staticmethod
    def update_case_status(db: Session, user: User, case: Case, new_status: str) -> Case:
        if user.role != "ADMIN" and not CaseService.user_can_access_case(user, case):
            raise PermissionError("You do not have permission to update this case")

        target_status = CaseService.validate_status(new_status)
        CaseService.validate_status_transition(case.status, target_status)

        case.status = target_status
        if target_status == CaseStatus.CLOSED.value:
            case.closed_at = datetime.utcnow()
        elif target_status != CaseStatus.CLOSED.value:
            case.closed_at = None
        if target_status == CaseStatus.INACTIVE.value:
            case.is_active = False
        elif target_status == CaseStatus.ACTIVE.value:
            case.is_active = True
        case.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(case)
        CaseService.log_case_action(db, user.id, case.id, "CASE_STATUS_CHANGED", f"Status changed to {target_status}")
        return case

    @staticmethod
    def deactivate_case(db: Session, user: User, case: Case) -> Case:
        if user.role != "ADMIN" and not CaseService.user_can_access_case(user, case):
            raise PermissionError("You do not have permission to deactivate this case")

        case.is_active = False
        case.status = CaseStatus.INACTIVE.value
        case.closed_at = datetime.utcnow()
        case.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(case)
        CaseService.log_case_action(db, user.id, case.id, "CASE_DEACTIVATED", "Soft-deleted case by marking inactive")
        return case

    @staticmethod
    def log_case_action(db: Session, user_id: int, case_id: int, action: str, details: str | None = None) -> None:
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type="CASE",
            resource_id=case_id,
            details=details,
        )
        db.add(audit_log)
        db.commit()
