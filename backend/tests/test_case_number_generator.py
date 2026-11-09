from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.case import Case
from app.utils.case_number_generator import generate_case_number


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:", echo=False, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_generate_case_number_initial_and_increment():
    db = setup_in_memory_db()

    # No cases yet, should return MP-<year>-0001 for MISSING
    year = datetime.utcnow().year
    num1 = generate_case_number(db, "MISSING", year=year)
    assert num1 == f"MP-{year}-0001"

    # Insert a case with that number
    c1 = Case(case_number=num1, category="MISSING", title="Test", person_identifier="pid1", description="desc", department_id=1, created_by=1, status="DRAFT", priority="MEDIUM")
    db.add(c1)
    db.commit()

    # Next number increments
    num2 = generate_case_number(db, "MISSING", year=year)
    assert num2 == f"MP-{year}-0002"

    # Wanted category should use WP prefix and independent counter
    wp1 = generate_case_number(db, "WANTED", year=year)
    assert wp1 == f"WP-{year}-0001"

    # Insert a wanted case and ensure increment
    c2 = Case(case_number=wp1, category="WANTED", title="Wanted", person_identifier="wid", description="desc", department_id=1, created_by=1, status="DRAFT", priority="MEDIUM")
    db.add(c2)
    db.commit()

    wp2 = generate_case_number(db, "WANTED", year=year)
    assert wp2 == f"WP-{year}-0002"
