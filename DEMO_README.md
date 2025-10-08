# HealthtechParseMatch Demo

This demo showcases a comprehensive healthcare workflow that demonstrates all the features implemented in the HealthtechParseMatch project.

## What the Demo Shows

The demo simulates a realistic patient interaction workflow:

1. **Patient Data Seeding** - Populates the system with sample patient data via simulated Redox integration
2. **Voice AI Call Simulation** - Demonstrates how a voice AI agent extracts patient information
3. **Patient Identity Verification** - Shows secure patient matching using DOB, ZIP, phone, and name
4. **Healthcare Information Retrieval** - Presents appointments, medications, and test results
5. **Call Recording & Notes** - Records the interaction and stores notes back to the system
6. **Feature Integration** - Demonstrates how all system features work together

## Features Demonstrated

- **🔐 Security**: Rate limiting, authentication headers, PHI protection
- **📊 Observability**: Prometheus metrics generation, structured logging
- **📨 Message Bus**: Event publishing to Kafka/Redpanda
- **🛡️ Self-Healing**: Circuit breaker and retry logic
- **📋 Logging**: PHI-safe logging with correlation IDs
- **🩺 Healthcare Integration**: Redox/FHIR data handling

## Prerequisites

1. **Docker Compose** running with all services:
   ```bash
   docker-compose up -d
   ```

2. **API Server** running on localhost:8000:
   ```bash
   python -m app.main
   ```

## Running the Demo

```bash
python demo_workflow.py
```

The demo will:
- Check if the API server is running
- Seed sample patient data
- Simulate a voice AI call
- Verify patient identity
- Retrieve and display healthcare information
- Record the call and store notes
- Show feature integration
- Provide a complete summary

## Sample Output

```
🏥 HealthtechParseMatch Comprehensive Demo
Demonstrating integrated healthcare workflow with all features
===============================================================

🚀 STEP 1: Seeding Patient Data via Redox Integration
===============================================================

📋 Seeding patient: Sarah Johnson
📞 [2025-10-07T10:30:15] patient_data_seeded: {"patient_id": "demo-patient-001", "name": "Sarah Johnson", "data_type": "PatientAdmin", "record_count": 4}

🤖 STEP 2: Voice AI Call Simulation
===============================================================

📞 Simulating call from patient: Sarah Johnson
🎯 Session ID: call_1234567890

🤖 Voice AI: 'Hello! I'd like to help you with your healthcare needs.'
🤖 Voice AI: 'Could you please provide your date of birth?'
         Extracted DOB: 1985-03-15
📞 [2025-10-07T10:30:15] voice_extraction_dob: {"extracted_dob": "1985-03-15", "confidence": 0.95}

🔍 STEP 3: Patient Identity Verification
===============================================================

🔍 Matching patient with criteria: DOB=1985-03-15, ZIP=10001, Phone ending in 0101, Last name starting with Joh
✅ Patient verification successful!
   Status: success
   Processing Time: 125.50ms
   Matches found: 0
📞 [2025-10-07T10:30:15] patient_verification_success: {"match_criteria": {"dob": "1985-03-15", "zip": "10001", "last4_phone": "0101", "last_name_prefix": "Joh"}, "processing_time_ms": 125.5, "matches_found": 0}

📋 STEP 4: Retrieving Patient Information
===============================================================

📋 Retrieving information for: Sarah Johnson

🤖 Voice AI: 'Thank you for verifying your identity. Here's your information:'

📅 Upcoming Appointments:
   • 2025-10-15 at 14:30 - Annual Physical with Dr. Emily Chen
     Location: Main Campus - Suite 200

💊 Current Medications:
   • Lisinopril 10mg - Once daily
     Prescribed by: Dr. Emily Chen on 2025-08-01

🧪 Recent Test Results:
   • Lipid Panel (2025-09-15) - Total Cholesterol: 185 mg/dL (Normal)
     Ordered by: Dr. Emily Chen

🤖 Voice AI: 'Is there anything specific you'd like to know more about?'

📝 STEP 5: Recording Call and Storing Notes
===============================================================

📝 Recording call for patient Sarah Johnson
   Session ID: call_1234567890
   Call Duration: 245 seconds
   Topics: appointment_reminder, medication_review, test_results
   Outcome: information_provided
✅ Call recorded and notes stored in patient record

🔗 STEP 6: Feature Integration Demonstration
===============================================================

🎯 Demonstrating integrated features:
   • Security: Rate limiting and authentication headers used
   • Observability: Metrics generated for each API call
   • Message Bus: Events published to Kafka/Redpanda
   • Self-Healing: Circuit breaker and retry logic active
   • Structured Logging: PHI-safe logging with correlation IDs
   • Healthcare Integration: Redox/FHIR data handling

✅ Health Check:
   Status: healthy
   Timestamp: 2025-10-07T10:30:15Z
   Version: 0.2.0

📊 Metrics Available:
   Prometheus metrics endpoint responding
   Redox metrics: 12 lines generated

📊 STEP 7: Complete Call Summary
===============================================================

🎯 Call Summary for Sarah Johnson:
   Session ID: call_1234567890
   Total Events Logged: 15

📈 Event Breakdown:
   • appointment_retrieved: 2
   • call_started: 1
   • diagnostic_retrieved: 1
   • health_check_performed: 1
   • medication_retrieved: 1
   • metrics_collected: 1
   • patient_data_seeded: 3
   • patient_verification_success: 1
   • voice_extraction_dob: 1
   • voice_extraction_last_name: 1
   • voice_extraction_phone: 1
   • voice_extraction_zip: 1

🔒 PHI Protection:
   • PHI-safe events: 12
   • PHI-containing events: 3 (masked in logs)

✅ Demo completed successfully!
   All features integrated and working together:
   ✅ Patient data seeding via Redox
   ✅ Voice AI information extraction
   ✅ Patient identity verification
   ✅ Healthcare information retrieval
   ✅ Call recording and note storage
   ✅ Security, observability, and monitoring
```

## Architecture Overview

The demo illustrates how the following components work together:

### Data Flow
```
Voice AI → Patient Verification → Healthcare Data Retrieval → Call Recording
     ↓            ↓                        ↓                    ↓
  Security     Message Bus              Metrics              Logs
  Headers      (Kafka)                 (Prometheus)         (PHI-safe)
```

### Key Integration Points

1. **Patient Verification API** (`/patient/match`)
   - Uses Redox integration for metrics
   - Implements rate limiting and authentication
   - Generates structured logs with correlation IDs

2. **Message Bus** (Kafka/Redpanda)
   - Publishes events for successful operations
   - Handles failed requests via Dead Letter Queue
   - Async processing without blocking API responses

3. **Metrics & Monitoring** (Prometheus/Grafana)
   - Tracks API performance and success rates
   - SLO monitoring with circuit breaker integration
   - Real-time dashboards for operational visibility

4. **Security & Compliance**
   - HIPAA-compliant PHI handling
   - Rate limiting and authentication
   - Structured logging with PII masking

## Demo Data

The demo uses synthetic patient data that mimics real healthcare scenarios:

- **Sarah Johnson**: Annual physical, hypertension management
- **Robert Williams**: Diabetes management, dermatology consultation
- **Maria Garcia**: Women's health, routine screenings

All data is fictional and contains no real patient information.

## Troubleshooting

### API Server Not Running
```bash
# Start the API server
python -m app.main

# Or with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker Services Not Running
```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f api
```

### Metrics Not Available
The demo will still work if metrics endpoints are unavailable - it gracefully handles API failures and continues the demonstration.

## Next Steps

After running the demo, you can:

1. **View Metrics**: Open Grafana at http://localhost:3000
2. **Check Logs**: Review application logs for structured events
3. **Explore API**: Use the interactive API docs at http://localhost:8000/docs
4. **Monitor Health**: Check system health at http://localhost:8000/health

This demo provides a comprehensive view of how all the implemented features work together in a realistic healthcare workflow scenario.
