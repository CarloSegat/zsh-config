---
paths:
  - "**/*.tex"
  - "**/*.md"
---

# Prose: write on point

Examples of the rule in ~/.claude/CLAUDE.md.

Bad: The filter is public, since it resides on the ledger.
Good: The filter publicly resides on the ledger.

Bad: An enrolled controller is never denied, but a controller that was never enrolled is accepted with the filter's false-positive probability, which in an access-control setting means an authorization granted to a non-member.
Good: A false positive grants authorization to a controller that was never enrolled.

Bad: The filter publicly resides on the ledger, and an adversary may therefore search for a colliding identifier that the filter accepts, at an expected cost inversely proportional to the false-positive probability, and may repeat the search to obtain as many accepted identifiers as a threshold rule requires.
Good: The filter publicly resides on the ledger, and an adversary may therefore search for colliding identifiers without incurring any transaction cost.

Bad: The exposure is then the validity plus one coordination deadline, and the authorizer charges both against the same budget. A process with no deadline ends only when a vote is decisive, leaving an adversary unbounded time to search, so a governance group authorized by a filter is refused unless it is time limited.
Good: Finally, to deny an adversary unbounded time to search for collisions, a proposal from a filter-authorized group must be time-limited.
