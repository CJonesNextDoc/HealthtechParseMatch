# Partner Integration Guide

Welcome to the HealthtechParseMatch API! This guide will help you integrate with our healthcare data parsing and matching service.

## Table of Contents
- [Authentication](#authentication)
- [API Endpoints](#api-endpoints)
- [Patient Matching](#patient-matching)
- [Employee Management](#employee-management)
- [Project Management](#project-management)
- [Health Checks](#health-checks)
- [Rate Limiting](#rate-limiting)
- [Error Handling](#error-handling)

## Authentication

All API requests require authentication via HTTP headers:

### Required Headers
```
X-User-Email: your-email@company.com
X-Role: vendor_app
```

### Roles
- `vendor_app`: External partner applications
- `user`: Basic user access
- `manager`: Management access
- `admin`: Full administrative access

### Example Request
```bash
curl -X GET "https://api.healthtechparsematch.com/health/check" \
  -H "X-User-Email: partner@company.com" \
  -H "X-Role: vendor_app"
```

## API Endpoints

Base URL: `https://api.healthtechparsematch.com`

### Health & Monitoring
- `GET /health/check` - Basic health check (no auth required)
- `GET /health/db` - Database health check
- `GET /health/metrics` - Prometheus metrics

### Core Functionality
- `POST /patient/match` - Patient matching using DOB, ZIP, and phone
- `GET /employees/{id}` - Get employee details
- `GET /projects` - List available projects
- `POST /assignments` - Create project assignments

## Patient Matching

The patient matching endpoint allows you to find patients using minimal identifying information.

### Endpoint
```
POST /patient/match
```

### Request Body
```json
{
  "dob": "1990-05-15",
  "zip": "12345",
  "last4_phone": "1234",
  "last_name_prefix": "Smi",
  "first_initial": "J"
}
```

### Parameters
- `dob` (required): Date of birth in YYYY-MM-DD format
- `zip` (required): 5-digit ZIP code
- `last4_phone` (optional): Last 4 digits of phone number
- `last_name_prefix` (optional): First 3+ characters of last name
- `first_initial` (optional): First initial of first name

### Response
```json
{
  "patient_id": "12345",
  "confidence_score": 0.95,
  "matched_fields": ["dob", "zip", "last4_phone"],
  "patient_data": {
    "name": "John Smith",
    "dob": "1990-05-15",
    "address": "123 Main St, Anytown, USA 12345"
  }
}
```

### Example
```bash
curl -X POST "https://api.healthtechparsematch.com/patient/match" \
  -H "Content-Type: application/json" \
  -H "X-User-Email: partner@company.com" \
  -H "X-Role: vendor_app" \
  -d '{
    "dob": "1990-05-15",
    "zip": "12345",
    "last4_phone": "1234"
  }'
```

## Employee Management

### Get Employee Details
```
GET /employees/{employee_id}
```

**Authorization:** Requires `admin`, `manager`, or `user` role

**Response:**
```json
{
  "id": 123,
  "name": "Jane Doe",
  "email": "jane.doe@company.com",
  "department": "Engineering",
  "role": "Senior Developer"
}
```

## Project Management

### List Projects
```
GET /projects
```

**Authorization:** Requires authentication

**Response:**
```json
[
  {
    "id": 1,
    "name": "Patient Data Migration",
    "description": "Migrating legacy patient records",
    "status": "active"
  }
]
```

### Get Project Details
```
GET /projects/{project_id}
```

**Authorization:** Requires `admin`, `manager`, or `user` role

## Health Checks

### Basic Health Check
```
GET /health/check
```

**No authentication required**

**Response:**
```json
{
  "status": "healthy"
}
```

### Database Health Check
```
GET /health/db
```

**Requires authentication**

**Response:**
```json
{
  "status": "healthy",
  "database": "connected"
}
```

### Metrics Endpoint
```
GET /health/metrics
```

**Response:** Prometheus-formatted metrics for monitoring

## Rate Limiting

API requests are rate limited based on user role:

- `user`: 100 requests per minute
- `manager`: 300 requests per minute
- `admin`: 1000 requests per minute
- `vendor_app`: 5000 requests per minute

### Rate Limit Headers
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 99
X-RateLimit-Reset: 1640995200
```

### Rate Limit Exceeded Response
```json
{
  "detail": "Rate limit exceeded"
}
```
**Status Code:** 429

## Error Handling

### Common HTTP Status Codes
- `200`: Success
- `400`: Bad Request - Invalid parameters
- `401`: Unauthorized - Missing or invalid authentication
- `403`: Forbidden - Insufficient permissions
- `404`: Not Found - Resource doesn't exist
- `429`: Too Many Requests - Rate limit exceeded
- `500`: Internal Server Error - Server error

### Error Response Format
```json
{
  "detail": "Error description",
  "type": "ErrorType"
}
```

## SDK and Tools

### Python SDK
A simple Python SDK is available for easy integration:

```python
from healthtech_sdk import HealthtechClient

client = HealthtechClient(
    base_url="https://api.healthtechparsematch.com",
    email="partner@company.com",
    role="vendor_app"
)

# Match a patient
result = client.match_patient(
    dob="1990-05-15",
    zip="12345",
    last4_phone="1234"
)
print(result)
```

### Postman Collection
Import the provided Postman collection (`postman_collection.json`) for easy API testing.

## Support

For integration support or questions:
- Email: support@healthtechparsematch.com
- Documentation: https://docs.healthtechparsematch.com
- API Reference: https://api.healthtechparsematch.com/docs

## Version History

- **v0.2.0**: Added patient matching, employee management, project management
- **v0.1.0**: Initial release with basic health checks
