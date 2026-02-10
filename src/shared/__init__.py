"""
Shared Module

Contains code that is used by TWO OR MORE features/capabilities.

SCOPE RULE:
- Code used by exactly ONE feature MUST remain local to that feature
- Code used by TWO OR MORE features gets extracted here
- NEVER create speculative abstractions "just in case"
- Wait for actual duplication before moving code here
"""
