# Request Template for AI Assistant

Use this template when requesting help from AI coding assistants to ensure clear, actionable requests that align with project standards.

## Template Structure

```
## 🎯 **Goal**
[What you want to achieve - be specific and measurable]

## 📋 **Context**
[Current situation, relevant background, constraints]

## 🔧 **Technical Details**
- **Framework/Tech Stack**: [FastAPI, SQLAlchemy, Redis, etc.]
- **Architecture**: [Async patterns, database patterns, etc.]
- **Existing Code**: [Reference specific files/classes/functions]
- **Requirements**: [Functional and non-functional requirements]

## 📝 **Acceptance Criteria**
- [ ] Specific deliverables (files, functions, tests)
- [ ] Code quality standards (async patterns, error handling, etc.)
- [ ] Testing requirements
- [ ] Documentation needs

## 🚫 **Constraints & Preferences**
- [Follow DEVELOPMENT.md standards](#development-standards)
- [Async patterns required](#async-patterns)
- [Testing conventions](#testing-conventions)
- [Error handling patterns](#error-handling)

## 📚 **References**
- DEVELOPMENT.md sections: [list relevant sections]
- Existing similar code: [file/function references]
- External docs/APIs: [links or specifications]
```

## Quick Reference Examples

### For New Features
```
## 🎯 **Goal**
Add user authentication with JWT tokens and Redis session storage

## 📋 **Context**
Users need secure login/logout with session persistence across app restarts

## 🔧 **Technical Details**
- Framework: FastAPI with OAuth2
- Database: Redis for session storage
- Security: JWT with configurable expiration
- Existing: `app/core/auth.py` has basic auth structure

## 📝 **Acceptance Criteria**
- [ ] JWT token generation and validation
- [ ] Redis-backed session storage
- [ ] Login/logout endpoints
- [ ] Session cleanup on logout
- [ ] Comprehensive test coverage
```

### For Bug Fixes
```
## 🎯 **Goal**
Fix async database connection timeout in user service

## 📋 **Context**
Users experiencing intermittent connection failures during peak hours

## 🔧 **Technical Details**
- File: `app/services/user_service.py`
- Error: "Connection timeout after 30s"
- Pattern: Occurs during high concurrent load
- Database: Async PostgreSQL with SQLAlchemy

## 📝 **Acceptance Criteria**
- [ ] Connection pooling optimization
- [ ] Timeout configuration review
- [ ] Error handling improvements
- [ ] Load testing validation
```

### For Code Reviews/Refactoring
```
## 🎯 **Goal**
Refactor user validation logic to follow async patterns

## 📋 **Context**
Current sync validation blocks event loop during user registration

## 🔧 **Technical Details**
- File: `app/routers/users.py`
- Function: `validate_user_data()`
- Issue: Uses synchronous email validation
- Impact: Blocks concurrent requests

## 📝 **Acceptance Criteria**
- [ ] Convert to async validation
- [ ] Maintain validation rules
- [ ] Add proper error handling
- [ ] Update tests for async behavior
```

## Key Principles

### 🎯 **Be Specific**
- Instead of "Add authentication" → "Add JWT-based authentication with Redis sessions"
- Instead of "Fix the bug" → "Fix async database timeout in user service"

### 📋 **Provide Context**
- What led to this request?
- What's the current state?
- What constraints exist?

### 🔧 **Include Technical Details**
- Reference existing code patterns
- Specify frameworks/libraries to use
- Mention performance/security requirements

### 📝 **Define Success Criteria**
- What files should be created/modified?
- What tests should pass?
- What documentation is needed?

### 🚫 **State Constraints**
- Reference DEVELOPMENT.md standards
- Specify what NOT to do
- Mention preferred patterns

## DEVELOPMENT.md Integration

Always reference these key sections from DEVELOPMENT.md:

- **[Async Patterns](#async-patterns)**: Always use async/await for I/O
- **[HTTP Client Usage](#http-client-usage)**: httpx.AsyncClient configuration
- **[Testing Conventions](#testing-conventions)**: pytest-asyncio, mocking patterns
- **[Error Handling](#error-handling)**: Proper exception handling and logging
- **[Database Patterns](#database-patterns)**: Async SQLAlchemy usage
- **[Pydantic Usage](#pydantic-usage)**: Model validation and Field usage

## Common Pitfalls to Avoid

❌ **Vague requests**: "Make it better" or "Add feature X"
❌ **Missing context**: Not explaining why or current state
❌ **No acceptance criteria**: Unclear when task is complete
❌ **Ignoring standards**: Not referencing DEVELOPMENT.md
❌ **Tech stack assumptions**: Not specifying frameworks/libraries

✅ **Clear goals**: Specific, measurable outcomes
✅ **Complete context**: Background, constraints, current state
✅ **Technical details**: Files, patterns, requirements
✅ **Success criteria**: Deliverables, tests, documentation
✅ **Standards compliance**: Follow established patterns

## Quick Checklist

- [ ] **Goal**: Specific and measurable?
- [ ] **Context**: Current situation explained?
- [ ] **Technical Details**: Frameworks, files, requirements listed?
- [ ] **Acceptance Criteria**: Clear deliverables defined?
- [ ] **Constraints**: DEVELOPMENT.md standards referenced?
- [ ] **References**: Existing code and docs linked?

Use this template to get more precise, faster, and higher-quality assistance!</content>
<parameter name="filePath">c:\repo\HealthtechParseMatch\REQUEST_TEMPLATE.md
