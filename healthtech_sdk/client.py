"""
HealthtechParseMatch API Client

A simple Python client for interacting with the HealthtechParseMatch API.
"""

from typing import Any, Dict, List, Optional

import requests


class HealthtechClient:
    """
    Client for the HealthtechParseMatch API.

    Args:
        base_url (str): Base URL of the API (e.g., "http://localhost:8000")
        user_email (str): User email for authentication
        role (str): User role (e.g., "admin", "user")
    """

    def __init__(self, base_url: str, user_email: str, role: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"X-User-Email": user_email, "X-Role": role, "Content-Type": "application/json"})

    def _get(self, endpoint: str) -> Any:
        """Make a GET request to the API."""
        response = self.session.get(f"{self.base_url}{endpoint}")
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a POST request to the API."""
        response = self.session.post(f"{self.base_url}{endpoint}", json=data)
        response.raise_for_status()
        return response.json()

    def health_check(self) -> Dict[str, Any]:
        """Check API health status."""
        return self._get("/health")

    def match_patients(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Match patients using the API."""
        return self._post("/patient/match", patient_data)

    def get_employee(self, employee_id: int) -> Dict[str, Any]:
        """Get employee details by ID."""
        return self._get(f"/employees/{employee_id}")

    def create_employee(self, employee_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new employee."""
        return self._post("/employees/create", employee_data)

    def get_projects_visible(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get visible projects with pagination."""
        return self._get(f"/projects/visible?limit={limit}&offset={offset}")

    def get_project(self, project_id: int) -> Dict[str, Any]:
        """Get project details by ID."""
        return self._get(f"/projects/{project_id}")

    def create_project(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new project."""
        return self._post("/projects/create", project_data)
