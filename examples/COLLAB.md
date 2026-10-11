# Fictional collaboration board

Project: sample calculator. This board describes responsibility; SQLite stores
current mail and leases. It is not authentication or an access control list.

| Participant | Bounded responsibility | Exact resources |
| --- | --- | --- |
| integrator | Review contributions, run tests, integrate sequentially | __commit__ |
| worker-a | Add calculator addition | src/add.py, tests/test_add.py |
| worker-b | Write user examples | examples/demo.txt |

Only the integrator performs integration. Workers claim each listed resource
separately before edits, send results with a unique idempotency key, then release
their leases. A claim for src does not cover src/add.py. Participants agree on
spelling in advance. A lease cannot stop a process that ignores this agreement.

Recovery: inspect inbox and leases, check files and running processes with the
team, and agree whether a predecessor has stopped before claiming an expired
resource. A crashed worker does not roll back edits. Never infer delivery from
an acknowledgement alone; review and test the contribution.
