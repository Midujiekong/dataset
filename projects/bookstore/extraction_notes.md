# Extraction Notes for BookStore Project

## 1. Project Source

- Repository: https://github.com/matheusforlan/BookStore
- Status: Fully public, complete source code, README, and configuration files
- Last Commit: 2026-03-30 (main branch)

## 2. Extraction Method
- Full source code review: Controller/Service/Repository/Entity layers
- README.md API documentation: All endpoints, request/response examples, role permissions
- Configuration files: application.properties (H2 DB), pom.xml (tech stack)

## 3. Traceability Guarantee
- Every requirement maps to at least one source (README, SourceCode, Comment)
- Every use case maps to exactly one API endpoint/controller method
- Every flow step maps to specific code logic (validation, query, computation)
- No inferred functionality: All artifacts are 100% derived from visible project content

## 4. Key Observations
- Dual roles: ADMIN (full book management) / CUSTOMER (cart & orders only)
- Stateless auth: JWT-based, no session management
- In-memory DB: H2, reset on restart, console available at /h2-db
- RESTful design: All endpoints follow standard HTTP methods and status codes

## 5. No Ambiguities
- All endpoints, roles, and data models are explicitly defined in README and code
- No missing or undocumented features in the main branch
- All alternative flows are derived from actual error handling in the code
