# Request: Milestone 1.1 - Database Connection & Schema Setup

## 🎯 **Goal**
Establish secure database connection to external caller data source and create de-identified data models for DOB training pipeline, ensuring complete data isolation between DOB, ZIP, and phone data silos.

## 📋 **Context**
We need to access tens of thousands of real phone call metadata containing spoken DOB inputs and existing system conversions. The data must remain strictly de-identified with separate silos for DOB/ZIP/phone data. This is the foundation for the entire DOB improvement pipeline.

## 🔧 **Technical Details**
- **Framework/Tech Stack**: FastAPI, SQLAlchemy (async), Pydantic, PostgreSQL
- **External Data Source**: PostgreSQL database (connection via `CALLER_SOURCE_DATA` env var)
- **Local Storage**: Existing project PostgreSQL database for pipeline data
- **Privacy Requirements**: Hash-based de-identification, no cross-silo data mixing
- **Existing Code**: `app/core/config.py` (settings), `app/models/modelbase.py` (base models)

## Table in Fields I supply:
- Table in source: voice
- Fields in query below:
id (int) (Voice PK)
dob_value (date) (this is the existing_conversion)
patient_id (str or null)
dob_input (str) (this is the spoken input)
attempt_num (int)
input_type (str)
classification (str)

- SQL query of Postgresql that works:
WITH dob_attempts AS (
  SELECT
    v.id,
    v.caller_responses,
    (v.caller_responses -> 'dob' ->> 'value') AS dob_value,
    (v.caller_responses -> 'patient' ->> 'id') AS patient_id,
    jsonb_array_elements(v.caller_responses -> 'dob' -> 'attempts') AS attempt
  FROM voice v
  WHERE v.caller_responses ? 'dob'
    AND EXISTS (
      SELECT 1
      FROM jsonb_array_elements(v.caller_responses -> 'dob' -> 'attempts') a
      WHERE a ->> 'input' ~ '[A-Za-z]'
    )
    AND call_start_time >= '2025-08-01'
    AND call_end_time <= '2025-08-08'
	AND (v.caller_responses -> 'patient' ->> 'id') IS NULL
)
SELECT
  da.id,
  da.dob_value,
  da.patient_id,
  da.attempt ->> 'input'   AS dob_input,
  (da.attempt ->> 'attempt')::int AS attempt_num,
  CASE
    WHEN da.attempt ->> 'input' ~ '[A-Za-z]' THEN 'spoken'
    ELSE 'dtmf'
  END AS input_type,
  CASE
    WHEN jsonb_array_length(da.caller_responses -> 'dob' -> 'attempts') > 1 THEN 'multiple_attempts'
    WHEN (da.attempt ->> 'input' ~ '[A-Za-z]') AND ((da.attempt ->> 'input') != da.dob_value) THEN 'spoken_candidate'
    WHEN da.dob_value IS NULL THEN 'failure'
    ELSE 'clean'
  END AS classification
FROM dob_attempts da
ORDER BY da.id, attempt_num DESC;
- [ ] Parameterize call_start_time and call_end_time
- [ ] Start with a 7 day window and reduce down if we need to (return set too bulky).


## 📝 **Acceptance Criteria**
- [ ] External database connection established using `CALLER_SOURCE_DATA` env var
- [ ] Pydantic models created for DOB training data (spoken_input, existing_conversion, metadata)
- [ ] Database schema created for isolated DOB data storage (no ZIP/phone/name fields)
- [ ] Hash-based de-identification implemented for record IDs
- [ ] Async database operations following DEVELOPMENT.md patterns
- [ ] Connection health checks and error handling
- [ ] Migration scripts for pipeline data tables
- [ ] Unit tests for data models and connection logic

## 🚫 **Constraints & Preferences**
- [Follow DEVELOPMENT.md standards](#development-standards)
- [Async patterns required](#async-patterns)
- [Pydantic models for validation](#pydantic-usage)
- [SQLAlchemy async patterns](#database-patterns)
- **STRICT**: No ZIP, phone, or name data in DOB silo
- **STRICT**: Hash-based IDs only (no sequential IDs that could be correlated)
- **STRICT**: External data access must be read-only
- Use existing project database for pipeline storage (not external source)

## 📚 **References**
- DEVELOPMENT.md sections: [Async Patterns](#async-patterns), [Database Patterns](#database-patterns), [Pydantic Usage](#pydantic-usage)
- Existing similar code: `app/core/config.py` (settings pattern), `app/models/modelbase.py` (SQLAlchemy base)
- External docs/APIs: PostgreSQL async driver documentation
- Data structure: spoken_word_input (text), existing_dob_conversion (date or NULL), call_timestamp (datetime), call_id (for hashing)</content>
<parameter name="filePath">c:\repo\HealthtechParseMatch\request-milestone-1.1.md
