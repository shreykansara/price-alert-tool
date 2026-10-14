# Prompts Log & Assistant Usage Summary
## Wissen Technology: Price Alert Tool

> **Context:** This document maintains an ongoing, chronological record of all prompts provided by the user during the development of the Price Alert Tool. It directly supports the assessment submission requirement:
> *"Include a README of at most one page: how to run it, how you used the assistant (the prompts in brief), what the assistant got wrong, and what you changed and why."*

---

### Prompt History & Audit Log

#### Prompt #1: Problem Interpretation & Agent Guidelines
- **Timestamp:** 2026-10-14 14:50 IST
- **User Prompt (Summary):**
  Analyze the attached assessment brief PDF ("Wissen Technology Campus Assessment – Price Alert Tool") and generate two comprehensive documentation files: [Problem.md](file:///c:/Users/Shrey/Projects/Wissen%20Technology/Problem.md) and [agents.md](file:///c:/Users/Shrey/Projects/Wissen%20Technology/agents.md) containing all relevant specifications, technical interpretations, architecture, and edge cases.
- **Key Deliverables Produced:**
  1. `Problem.md`: Full decomposition of inputs (CSV/JSON), mathematical crossing definitions (Level and MA Cross), output format specifications, and a catalog of unseen edge cases.
  2. `agents.md`: Architectural blueprint (Standard Library, zero-dependency), known AI traps/hallucinations (e.g., false MA crosses on Day $L$), test matrix, and the 6-minute presentation script.
- **Review & Validation Notes:**
  - Verified exact match of alert format strings with the brief sample.
  - Highlighted critical mathematical boundary definitions (e.g. Day $L$ vs Day $L+1$ for MA cross).

---

#### Prompt #2: Prompt Summary Logging Protocol
- **Timestamp:** 2026-10-14 15:06 IST
- **User Prompt (Summary):**
  Create a dedicated Markdown file to store summaries of all prompts given to the assistant by the user, and maintain/update this file continuously after each subsequent prompt.
- **Key Deliverables Produced:**
  - Created [prompts.md](file:///c:/Users/Shrey/Projects/Wissen%20Technology/prompts.md) to serve as the live audit log for prompts, assistant outputs, and evaluation notes.
- **Review & Validation Notes:**
  - Logged Prompts #1 and #2.
  - Established rule to append to this document on all future user turns.

---
