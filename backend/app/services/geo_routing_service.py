"""
Module 9 – Geospatial & Jurisdiction Department Routing Service
===============================================================
Computes the nearest authorized department for a detection camera using
geodetic (Haversine) distance and jurisdiction-based rule matching.

Safety Invariants:
    1. Only active, authorized departments with notification_enabled = True
       may receive alerts.
    2. Every routing decision generates an auditable, human-readable
       routing_reason.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.models.camera import Camera
from app.models.department import Department


@dataclass
class DepartmentRoutingResult:
    department: Optional[Department]
    distance_km: Optional[float]
    routing_reason: str


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates great-circle distance between two GPS coordinates in kilometers
    using the Haversine formula.
    """
    R = 6371.0  # Earth's radius in kilometers

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)


class GeoRoutingService:
    """
    Calculates the responsible or nearest authorized department for a camera detection.
    """

    @staticmethod
    def find_nearest_authorized_department(
        camera: Optional[Camera],
        db: Session,
        exclude_department_id: Optional[int] = None,
    ) -> DepartmentRoutingResult:
        """
        Determines the nearest authorized department to a camera location.

        Args:
            camera: Detected Camera DB model (or None)
            db: SQLAlchemy Session
            exclude_department_id: Optional department to exclude if matching only secondary
        """
        # 1. Fetch all active, notification-enabled authorized departments
        query = db.query(Department).filter(
            Department.is_active == True,  # noqa: E712
            Department.notification_enabled == True,  # noqa: E712
        )
        if exclude_department_id is not None:
            query = query.filter(Department.id != exclude_department_id)

        eligible_departments = query.all()

        if not eligible_departments:
            return DepartmentRoutingResult(
                department=None,
                distance_km=None,
                routing_reason="No eligible active and notification-enabled departments found in system.",
            )

        if not camera:
            # Fallback to the first central or general department
            dept = GeoRoutingService._find_central_or_first(eligible_departments)
            return DepartmentRoutingResult(
                department=dept,
                distance_km=None,
                routing_reason=(
                    f"Camera context unavailable. Assigned to {dept.department_name} "
                    f"({dept.department_code or 'ID:' + str(dept.id)}) via central fallback routing rule."
                ),
            )

        # 2. Check if camera coordinates are present and departments have coordinates
        has_camera_coords = camera.latitude is not None and camera.longitude is not None
        if has_camera_coords:
            closest_dept: Optional[Department] = None
            min_dist: float = float("inf")

            for dept in eligible_departments:
                if dept.latitude is not None and dept.longitude is not None:
                    dist = haversine_distance(
                        camera.latitude, camera.longitude, dept.latitude, dept.longitude
                    )
                    if dist < min_dist:
                        min_dist = dist
                        closest_dept = dept

            if closest_dept is not None and min_dist < float("inf"):
                cam_label = camera.camera_name or camera.camera_code or f"ID {camera.id}"
                loc_label = camera.location_name or f"lat={camera.latitude}, lon={camera.longitude}"
                return DepartmentRoutingResult(
                    department=closest_dept,
                    distance_km=min_dist,
                    routing_reason=(
                        f"Selected {closest_dept.department_name} ({closest_dept.department_code or closest_dept.id}) "
                        f"as nearest authorized facility at {min_dist:.2f} km from camera '{cam_label}' ({loc_label})."
                    ),
                )

        # 3. Fallback: match by jurisdiction if camera has jurisdiction
        if camera.jurisdiction:
            for dept in eligible_departments:
                if dept.jurisdiction and dept.jurisdiction.strip().lower() == camera.jurisdiction.strip().lower():
                    return DepartmentRoutingResult(
                        department=dept,
                        distance_km=None,
                        routing_reason=(
                            f"Selected {dept.department_name} based on matching jurisdiction '{camera.jurisdiction}' "
                            f"for camera '{camera.camera_name or camera.camera_code}'."
                        ),
                    )

        # 4. Fallback: camera's own assigned department if active and notification-enabled
        if camera.department_id:
            for dept in eligible_departments:
                if dept.id == camera.department_id:
                    return DepartmentRoutingResult(
                        department=dept,
                        distance_km=None,
                        routing_reason=(
                            f"Selected {dept.department_name} as the direct registered owner/maintainer "
                            f"of camera '{camera.camera_name or camera.camera_code}'."
                        ),
                    )

        # 5. General fallback: Central department or first eligible police department
        dept = GeoRoutingService._find_central_or_first(eligible_departments)
        return DepartmentRoutingResult(
            department=dept,
            distance_km=None,
            routing_reason=(
                f"Selected {dept.department_name} ({dept.department_code or dept.id}) "
                f"via default authorized agency assignment for camera '{camera.camera_name or camera.camera_code}'."
            ),
        )

    @staticmethod
    def _find_central_or_first(departments: list[Department]) -> Department:
        for d in departments:
            if d.department_type in ("CENTRAL_DEPARTMENT", "CENTRAL"):
                return d
        for d in departments:
            if d.department_type == "POLICE":
                return d
        return departments[0]


geo_routing_service = GeoRoutingService()
