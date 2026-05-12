# Dataset Guideline v2.1
## 1. Dataset Purpose
This dataset is built to support research on structured requirements and use case modeling.
It provides the following materials for modeling analysis and evaluation tasks:
- Structured functional requirements
- Use case diagrams
- Use case specifications
- Requirement-to-model traceability links

---

## 2. Dataset Scope
This dataset focuses on **interaction-driven software systems** that can be modeled using use case–based requirements methods.
Sample suitable systems include:
- ATM systems
- E-commerce systems
- Booking systems
- Library systems
- Hospital management systems

### 2.1 Dataset Assumptions
This dataset models **observable and reproducible functional behaviors** from available project artifacts.
Modeling artifacts are derived from:
- Project documentation
- User-visible behavior
- Interaction logic
- Validation behavior
- Runtime execution behavior

The dataset does **not** assume that original projects have complete or formally written requirements.

---

## 3. Dataset Structure
```
/dataset_repo
├── guidelines/
├── schema/
└── projects/
    └── <project_name>/
        ├── project_info.json
        ├── functional_requirements.json
        ├── use_case_diagram.puml
        ├── use_case_specs.json
        ├── traceability.json
        └── extraction_notes.md
```

---

## 4. Artifact Definitions
### 4.1 Functional Requirement
A functional requirement describes a system function, interaction behavior, validation rule, or behavioral constraint related to user–system interaction.
Requirements may exist at multiple levels of abstraction.

#### 4.1.1 Goal‑Level Requirement
Goal-level requirements express **high-level user goals** or core system capabilities.
**Example**
```
The system shall allow customers to withdraw cash.
```
Main uses:
- Actor identification
- Use case identification
- Goal abstraction

#### 4.1.2 Interaction‑Level Requirement
Interaction-level requirements describe detailed interaction steps, validation logic, exception handling, or behavioral constraints.
**Example**
```
The system shall validate account balance before dispensing cash.
```
Main uses:
- Building interaction flows
- Ordering behavioral steps
- Creating alternative flows
- Checking behavioral consistency

### 4.2 Use Case
A use case defines a sequence of interactions between an actor and the system to **accomplish a user goal** or support reusable system behavior.
A function should be captured as a use case if it meets one or more of these conditions:
- It represents a complete user goal
- It represents reusable interaction behavior
- It represents optional or specialized behavior
- It participates in include or extend relationships

### 4.3 Use Case Diagram
The use case diagram models:
- Actors
- User goals
- Relationships between use cases
- Overall system interaction structure

It provides a high-level abstraction of interactions and shows **what interaction goals the system supports**.

### 4.4 Use Case Specification
The use case specification models:
- Main interaction flow
- Step ordering
- Alternative flows
- Exception handling
- Preconditions
- Postconditions

Specifications are created by organizing interaction-level requirements into structured behavioral flows.
Additional details may be inferred from user-visible behavior and system interaction logic when needed.

### 4.5 Traceability
Traceability defines **semantic connections** between requirements and use case model artifacts.
The dataset supports:
- Goal Requirement → Use Case
- Interaction Requirement → Flow Step

Alternative flow steps should also be traced to interaction-level requirements whenever possible.
Traceability relationships are **many‑to‑many**.

### 4.6 Project Information
Project information stores project-level metadata.
Typical fields:
- Project name
- Source repository
- Programming language
- Application domain
- Project version

This artifact provides context for dataset analysis and traceability.

### 4.7 Extraction Notes
Extraction notes document modeling assumptions, ambiguity resolutions, and analyst decisions made during dataset creation.
Typical content:
- Ambiguity explanations
- Inferred behaviors
- How missing information is handled
- Modeling assumptions
- Analyst comments

This improves transparency and consistent interpretation.

---

## 5. Artifact Construction
### 5.1 Data Sources
Requirements and modeling artifacts can be extracted or built from these sources:

| Source                 | Purpose                      |
| ---------------------- | ---------------------------- |
| README                 | Functional overview          |
| GUI                    | User-visible functions       |
| UI menu items          | Candidate use cases          |
| Class names            | Functional modules           |
| Method names           | Business operations          |
| Conditional statements | Validation logic             |
| Error messages         | Alternative flows            |
| SQL operations         | Persistence-related behavior |
| Source comments        | Functional descriptions      |
| Event handling logic   | Interaction behavior         |

### 5.2 Artifact Construction Sources
| Artifact                | Possible Sources                                             |
| ----------------------- | ------------------------------------------------------------ |
| Requirements            | README, GUI, comments, source code behavior                  |
| Use Cases               | User-visible functions, menu items, interaction flows        |
| Use Case Specifications | Interaction-level requirements, UI logic, validation logic, exception handling |
| Traceability            | Semantic mapping between requirements and use cases          |

### 5.3 Constructed Artifacts
Constructed artifacts are modeling items **not explicitly present** in original project sources, but created through structured analysis and standardization.
These typically include:
- Use case diagrams
- Use case specifications
- Traceability mappings
- Structured requirements

### 5.4 Recommended Extraction Workflow
```
Open‑source Project
        ↓
README / GUI / Source Analysis
        ↓
Requirement Extraction
        ↓
Use Case Identification
        ↓
Use Case Diagram Construction
        ↓
Use Case Specification Construction
        ↓
Traceability Construction
        ↓
Validation
        ↓
Dataset Entry
```

### 5.5 Existing Artifact Handling
If a project already contains modeling artifacts, they are treated as **candidate sources**, not final dataset artifacts.
Existing artifacts may be:
- Reused directly
- Normalized
- Refined
- Completed
- Reconstructed

based on quality, completeness, and consistency with these guidelines.

---

## 6. Extraction Rules
### 6.1 Requirement Writing Rule
Requirements should follow a clear, consistent behavior-oriented pattern.
Recommended style:
```
The system shall ...
```

### 6.2 Requirement Granularity
Each requirement must describe **one single functional capability or constraint**.

### 6.3 Requirement Identifier Rule
Goal-level requirements:
```
FR-01, FR-02
```
Interaction-level requirements (hierarchical):
```
FR-01-1, FR-01-2
```

### 6.4 Requirement Source Rule
Use standard source labels such as:
README, GUI, SourceCode, Comment, DatabaseOperation, InferredFromBehavior

### 6.5 Requirement Normalization Rule
Original descriptions may be rewritten into standard requirement statements **while preserving meaning**.

### 6.6 Implementation Independence
Requirements should **avoid implementation details**.

### 6.7 Ambiguity Handling
When behavior is unclear:
- Prioritize user-visible behavior
- Do not guess unobserved functions
- Record assumptions in extraction_notes.md

### 6.8 Inference Constraint Rule
Inferred behaviors must be supported directly by observable interactions.
All inferences must be documented.

### 6.9 Actor Identification
Actors are external entities that interact with the system.
Valid: Customer, Admin, External Payment System
Invalid: Database, Java Class, SQL Table

### 6.10 Use Case Identification
A behavior is a use case if it:
- Serves a clear user purpose
- Is reusable
- Is optional or specialized
- Uses include/extend

### 6.11 Use Case Boundary Rule
Use cases represent meaningful user goals, not low-level implementation or UI details.

### 6.12 Use Case Naming Rule
Use **Verb + Object** format.
Examples: Withdraw Cash, Deposit Money, Change PIN

### 6.13 Diagram Construction Rule
- Every use case spec has a matching diagram use case
- Actor links are shown clearly
- Include/extend are used properly
- System boundaries are defined

### 6.14 Diagram‑Spec Consistency Rule
Names, actors, and relationships must match between diagrams and specs.

### 6.15 Include Relationship
Use `<<include>>` for **shared, mandatory behavior**.

### 6.16 Extend Relationship
Use `<<extend>>` for **optional or additional behavior**.

### 6.17 Main Flow Rules
Steps must be observable, explicit, ordered, and clear.
Each step identifies actor or system action.

### 6.18 Step Identifier Rule
Main Flow Step: MF-01
Alternative Flow Step: AF-01

### 6.19 Alternative Flow Rules
Extract alternative flows for failures, invalid input, errors, or rule violations.
May include `return_to_step`.

### 6.20 Preconditions
Required system state before use case starts.

### 6.21 Postconditions
System state after successful completion.

### 6.22 Extraction Notes Rule
All key modeling decisions go into `extraction_notes.md`.

### 6.23 Traceability Relation Rule
Use standardized types:
goal_to_use_case, requirement_to_main_flow, etc.

### 6.24 Requirement‑to‑Spec Mapping Rule
Requirements do not need sentence-by-sentence matching.
One requirement may map to one step, multiple steps, a flow, or a condition.

---

## 7. Validation Rules
### 7.1 Completeness Validation
All major user-visible functions are represented as use cases.

### 7.2 Traceability Validation
Every requirement is linked to at least one model element.

### 7.3 Naming Consistency
Naming rules are followed consistently.

### 7.4 Granularity Consistency
Requirements and use cases stay at similar abstraction levels.

### 7.5 Interpretation Consistency
Analysts follow the same rules to reduce inconsistency.

---

## 8. Schema Reference
Detailed artifact schemas are located in:
```
/schema
```