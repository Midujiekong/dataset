# Extraction Notes for ATM-Management-System

## 1. Ambiguity Explanations

- **PIN Validation Logic**: The original source code does not explicitly define PIN attempt limits or account locking behavior. We added NFR-02 (3 incorrect PIN attempts = account lock) as a standard banking security practice, consistent with real-world ATM systems.
- **Transaction History**: The original project has basic transaction tracking but no explicit limit on mini statement entries. We defined "recent 5 transactions" as a standard mini statement format (inferred from banking industry norms).
- **Data Persistence**: The original project uses MySQL database for storage. We noted this in project_info.json and assumed runtime data integrity (NFR-04) as a critical non-functional requirement.

## 2. Inferred Behaviors

- **PIN Format**: Inferred that PIN must be 4 digits (standard ATM PIN format) since the original code does not specify, but validates numeric input.
- **Deposit Amount Validation**: Inferred that deposit amounts must be positive (AF-03 in UC-02) as negative deposits are logically invalid for banking systems.
- **Transaction Recording**: Inferred that all core transactions (withdrawal/deposit/PIN change) must be recorded in history (postconditions in use case specs) to support mini statement generation.

## 3. Missing Information Handling

- **No Admin Actor/Functionality**: The original project only supports customer-facing features (no admin functions like account unlock). We excluded admin-related use cases/requirements since they are not present in the source code.
- **No Currency/Amount Limits**: The original code has no withdrawal/deposit limits. We did not add limits (per guideline rule 6.7: do not guess unobserved functions) but ensured balance validation (FR-01-2) for withdrawals.
- **No Fast Cash Dedicated Flow**: The original project has a FastCash.java file but no distinct fast cash workflow. We merged fast cash functionality into the general "Withdraw Cash" use case as a predefined amount option.

## 4. Modeling Assumptions

- **Actor Definition**: Only "Customer" is a valid actor (per rule 6.9: actors are external entities; database/classes are excluded).
- **Use Case Boundaries**: All use cases represent meaningful user goals (per rule 6.11) – no low-level UI/implementation details (e.g., "Insert Card" is a precondition, not a use case).
- **Include Relationship**: "Verify PIN" is a shared mandatory behavior (per rule 6.15) included by all transactional use cases.
- **Sign Up Process**: The original project includes sign up functionality but it is treated as a pre-system setup step, not a core ATM transaction use case.

## 5. Analyst Comments

- The original project is a GUI-based ATM system implemented in Java using Swing and AWT libraries.
- All functional requirements are derived directly from source code behavior and README documentation.
- Naming conventions strictly follow guideline rules: use cases (Verb + Object), requirement IDs (FR-XX/FR-XX-XX), flow steps (MF-AF-XX).
- Traceability relationships are mapped to the most granular level possible (interaction requirements → flow steps; goal requirements → use cases).
- All non-functional requirements align with standard banking ATM system expectations and are prioritized based on criticality.
