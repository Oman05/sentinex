from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.case import Case, CaseCategory


def generate_case_number(db: Session, category: str, year: int | None = None) -> str:
    """Generate a unique case number for the supplied category."""
    normalized_category = category.upper()
    if normalized_category not in {CaseCategory.MISSING.value, CaseCategory.WANTED.value}:
        raise ValueError("Invalid case category")

    prefix = "MP" if normalized_category == CaseCategory.MISSING.value else "WP"
    target_year = year or datetime.utcnow().year
    pattern = f"{prefix}-{target_year}-%"

    last_case = (
        db.query(Case)
        .filter(Case.category == normalized_category)
        .filter(Case.case_number.like(pattern))
        .order_by(Case.case_number.desc())
        .first()
    )

    next_number = 1
    if last_case is not None:
        try:
            last_number = int(last_case.case_number.split("-")[-1])
            next_number = last_number + 1
        except (ValueError, IndexError):
            next_number = 1

    return f"{prefix}-{target_year}-{next_number:04d}"
