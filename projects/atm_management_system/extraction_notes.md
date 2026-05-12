## Reverse Engineering Strategy

The original GitHub repository does not provide formal software requirements documentation.

Therefore, the dataset was reconstructed through systematic reverse engineering using:

- Repository structure analysis
- Java source code inspection
- Swing GUI workflow observation
- Database interaction analysis
- SQL schema inspection
- Transaction processing behavior inference

------

# Modeling Decisions

## Functional Requirement Abstraction

Requirements were normalized into two abstraction levels:

### 1. Goal‑Level Requirements

Represent high‑level business capabilities:

- Account Registration
- Login
- Withdrawal
- Deposit
- Fast Cash
- PIN Change
- Balance Enquiry
- Mini Statement

These are implementation‑independent business goals.

### 2. Interaction‑Level Requirements

Represent observable system‑user interactions derived from GUI logic and source code behavior.

Examples:

- Credential validation
- Balance verification
- Transaction persistence
- PIN consistency checking

These requirements are finer‑grained and suitable for traceability learning tasks.

------

# Use Case Construction

Use cases were reconstructed from observable ATM workflows.

## Reconstruction Principles

### Authentication‑First Constraint

All banking operations require successful authentication beforehand.

### Persistence Visibility

Any operation modifying financial data must persist transaction records.

### Validation Isolation

Validation failures are modeled separately in alternative flows.

Examples:

- Invalid login
- Insufficient balance
- PIN mismatch

------

# Traceability Construction

Traceability links were reconstructed between:

- High‑level goals and use cases
- Detailed requirements and flow steps
- Validation requirements and alternative flows

This supports downstream tasks such as:

- Requirement coverage analysis
- Requirement consistency checking
- Reverse engineering benchmarks
- Automated traceability generation
- Requirements engineering fine‑tuning datasets

------

# Ambiguities and Assumptions

## Database Schema Ambiguity

The repository exposes database information partially through:

- SQL initialization scripts
- JDBC statements

Exact normalization rules were inferred conservatively.

## Security Limitations

The original project implements only basic ATM security:

- Card number authentication
- PIN validation

Enterprise banking mechanisms were intentionally excluded.

Examples excluded:

- Encryption
- Session expiration
- Multi‑factor authentication

## Fast Cash Modeling

Fast Cash was modeled as a specialization of standard withdrawal behavior because both operations share:

- Balance validation
- Transaction persistence
- Balance deduction logic

Fast Cash provides predefined quick amounts and reuses core withdrawal rules without redundant modeling.

------

# Excluded Implementation Details

The following implementation‑level elements were intentionally excluded:

- Swing layout coordinates
- Pixel‑level UI rendering
- JDBC boilerplate code
- Java exception stack traces
- SQL optimization logic

The dataset focuses on implementation‑independent requirements knowledge.

------

# Dataset Quality Improvements

Compared with ordinary reverse‑engineering datasets, this version improves:

表格







|         Aspect          | Ordinary Dataset | High‑Quality Dataset |
| :---------------------: | :--------------: | :------------------: |
| Requirement Granularity |      Coarse      |     Multi‑layer      |
|        Use Cases        |  Main flow only  |  Main + Alternative  |
|      Traceability       |     Partial      |      Step‑level      |
|      NFR Coverage       |       Weak       |       Explicit       |
|       Consistency       |     Weak IDs     |    Full‑chain IDs    |
|    Benchmark Utility    |       Low        |         High         |
|    RE Explainability    |     Missing      |  Explicit strategy   |

------

# Recommended Future Extensions

Possible future dataset extensions include:

1. UML Class Diagram Reconstruction
2. Sequence Diagram Extraction
3. Entity Relationship Reconstruction
4. GUI Event Flow Mining
5. Requirement‑to‑Code Mapping
6. AST‑Level Structural Extraction
7. PlantUML Auto‑generation
8. Cross‑project Unified Schema
9. Benchmark Packaging
10. LLM Fine‑tuning Dataset Expansion
