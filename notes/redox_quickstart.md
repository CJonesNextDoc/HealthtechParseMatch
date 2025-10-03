# Redox Quickstart (Hands-on Notes)

## Auth
- Token URL: https://api.redoxengine.com/v2/auth/token
- Grant: client_credentials with private_key_jwt (alg: RS384 or ES384)
- Client: <from .env>
- JWK: stored locally (not committed)

## Endpoints
- FHIR base: https://api.redoxengine.com/fhir/R4/evening-earth/Development
- JSON message: https://evening-earth.redoxengine.com/endpoint/message
- Destination ID: 1e4bb53b-234a-4ca2-b206-14c36ca4efa7
- Source ID (if needed): 66975839-e331-43a1-be57-f07fe14e62ed

## Calls exercised
- FHIR: GET /Patient?_count=1
- JSON: PatientAdmin.NewPatient (success)
- JSON: PatientAdmin.NewPatient (validation error: missing DOB)

## Observations
- Token TTL ~3600s. Re-mint works reliably with private_key_jwt.
- FHIR returns Bundle with Patient; standard R4 fields (identifier, name, birthDate).
- JSON validation errors are explicit with path and issue; easy to debug via dashboard logs.

## Next ideas
- Add retry + idempotency key to JSON send.
- Optional: FHIR POST /Patient if sandbox allows writes.
- Wrap into small "integration gateway" helper with logging and metrics hooks.
