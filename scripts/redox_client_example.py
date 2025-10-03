#!/usr/bin/env python3
"""
Example usage of the RedoxClient for sending PatientAdmin messages.
"""

import asyncio

from dotenv import load_dotenv

from app.clients.redox_client import RedoxClient

# Load environment variables
load_dotenv()


async def main():
    # Initialize client (reads config from environment variables)
    client = RedoxClient()

    # Example patient data
    patient_data = {
        "Patient": {
            "Identifiers": [{"ID": "MRN123456", "IDType": "MRN"}],
            "Demographics": {
                "FirstName": "Jane",
                "LastName": "Doe",
                "DOB": "1984-07-13",
                "Sex": "F",
                "Address": {"StreetAddress": "123 Main St", "City": "Madison", "State": "WI", "ZIP": "53703"},
            },
        },
        "Visit": {
            "VisitNumber": "A01-20251003-001",
            "AttendingProvider": {"ID": "12345", "IDType": "NPI", "FirstName": "Alex", "LastName": "Smith"},
            "Location": {"Facility": "Main Hospital", "Department": "ED", "Room": "12A"},
        },
    }

    try:
        # Send patient admin message (automatically handles token management)
        response = await client.send_patient_admin_message(patient_data, event_type="NewPatient")
        print("Patient message sent successfully!")
        print(f"Response: {response}")

    except Exception as e:
        print(f"Error sending patient message: {e}")


if __name__ == "__main__":
    asyncio.run(main())
