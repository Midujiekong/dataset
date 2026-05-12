# Extraction Notes

This dataset was reverse engineered from the ATM Management System project.

## Reverse Engineering Strategy

The following sources were used:

- GUI interaction flows
- Java Swing event handlers
- Database transaction logic
- JDBC persistence operations
- ATM transaction workflows

## Source Mapping

| Java Class | Derived Requirement |
|---|---|
| LoginPage.java | Login |
| withdraw.java | Withdraw Cash |
| deposit.java | Deposit Cash |
| FastCash.java | Fast Cash |
| PinChange.java | Change PIN |
| MiniStatement.java | Mini Statement |

## Requirement Extraction Categories

- Input Requirements
- Validation Requirements
- Presentation Requirements
- Persistence Requirements
- Computation Requirements

## Dataset Compliance

This dataset follows guideline v2.1 for:

- Interaction-driven software systems
- Use case oriented modeling
- Traceability-aware requirements engineering
- Reverse engineered requirement datasets