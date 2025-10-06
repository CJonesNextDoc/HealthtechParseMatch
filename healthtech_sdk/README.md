# HealthtechParseMatch Python SDK

A simple Python client for the HealthtechParseMatch API.

## Installation

```bash
pip install -e ./healthtech_sdk
```

## Usage

```python
from healthtech_sdk import HealthtechClient

# Initialize the client
client = HealthtechClient(
    base_url="http://localhost:8000",
    user_email="partner@example.com",
    role="user"
)

# Check API health
health = client.health_check()
print(health)

# Match patients
patient_data = {
    "dob": "1980-01-01",
    "zip": "12345",
    "last4_phone": "1234",
    "last_name_prefix": "Smi",
    "first_initial": "J"
}
matches = client.match_patients(patient_data)
print(matches)

# Get employee by ID
employee = client.get_employee(1)
print(employee)

# Create a new employee
new_employee = client.create_employee({
    "name": "Jane Smith",
    "email": "jane@example.com",
    "department": "Engineering"
})
print(new_employee)

# Get visible projects
projects = client.get_projects_visible(limit=10)
print(projects)

# Get project by ID
project = client.get_project(1)
print(project)
```

## API Methods

- `health_check()` - Check API health status
- `match_patients(patient_data)` - Match patients using DOB, ZIP, and phone data
- `get_employee(employee_id)` - Get employee details by ID
- `create_employee(employee_data)` - Create a new employee
- `get_projects_visible(limit=100, offset=0)` - Get visible projects with pagination
- `get_project(project_id)` - Get project details by ID
- `create_project(project_data)` - Create a new project

## Authentication

The client automatically handles authentication by setting the required headers:
- `X-User-Email`: Your user email
- `X-Role`: Your role (e.g., "admin", "user", "vendor_app")
