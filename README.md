# Agent Collab Kit

A small Python 3.10+ standard-library tool for cooperative work on one trusted
machine: durable messages, explicit acknowledgements, and leases for exact
resource names. Inspired by operational patterns, this is an original standalone
implementation, not an export of a production system. It runs without a provider,
agent framework, cloud service, Git execution, or automatic orchestration.
It does not claim a new coordination model.

## Try it with an isolated database

Run from this directory on a local disk. The example uses a temporary directory
and fictitious participants; never point a demonstration at a live project DB.
Shell commands below use a POSIX shell:

```sh
DEMO_DIR=$(mktemp -d)
DB="$DEMO_DIR/demo.db"
python3 agent_collab.py --db "$DB" init
python3 agent_collab.py --db "$DB" send --sender worker-a --recipient integrator --key demo-result-1 --body 'Addition is ready for review'
python3 agent_collab.py --db "$DB" inbox --recipient integrator
# Copy the returned message id into MESSAGE_ID.
python3 agent_collab.py --db "$DB" ack --recipient integrator --id MESSAGE_ID
python3 agent_collab.py --db "$DB" claim --resource src/add.py --owner worker-a --ttl 300
# Copy the returned generation UUID into GENERATION.
python3 agent_collab.py --db "$DB" renew --resource src/add.py --owner worker-a --generation GENERATION --ttl 300
python3 agent_collab.py --db "$DB" leases
python3 agent_collab.py --db "$DB" release --resource src/add.py --owner worker-a --generation GENERATION
python3 -m unittest discover -s tests -v
```

All commands require `--db`. `init` is repeatable. Commands return JSON on success,
exit 0, or an error on stderr, exit 1 (invalid CLI syntax exits 2). An idempotency
key is unique across the database: repeating the same sender, recipient and body
returns the existing message, including its acknowledgement state. Reusing a key
for different content fails. `inbox` shows only pending mail for the named recipient.
`ack` requires that recipient name and is repeatable. Acknowledgement means the
caller marked the message received; it does not prove work was delivered or tested.

## Cooperative leases and recovery

Use the fictitious [collaboration board](examples/COLLAB.md) to agree on distinct
responsibilities and one integrator. Claim every exact resource before editing;
use a shared resource such as `__commit__` to serialize integration by agreement.
Resource names are opaque and case-sensitive. `src`, `src/a.py`, and `src/A.py`
are separate resources. Paths are not normalized, folders have no recursive
coverage, and aliases such as `./src/a.py` require a naming convention.

A claim creates a fresh generation UUID. An active claim conflicts even for the
same owner; renew using the current generation. TTL must be finite, positive and
at most 86400 seconds. Renew and release require the matching owner and generation
and an unexpired lease. At the exact expiration time, a new claim may take over.
An expired token cannot renew or release its successor, even with the same owner.
`leases` lists active leases only; expired rows remain until replaced.

After a crash, reopen the same database, inspect pending messages and leases,
check the actual work and running processes, then agree on a takeover. There is
no forced release. Lease expiry does not stop the previous worker or undo edits:
a paused worker may resume after takeover. Workers must check ownership and stop
on loss; this tool provides no filesystem fencing. The test suite demonstrates
expiry, stale tokens, persistence and two real processes racing for one claim.

Every mutation uses SQLite `BEGIN IMMEDIATE` and a 10-second busy timeout.
A timeout is an error, not a successful claim; inspect state before retrying.
The API accepts an injected clock for tests; normal operation trusts the wall
clock. Clock corrections can shorten or prolong leases. Close connections before
making a consistent backup, and retain SQLite sidecars if present. No background
service, watcher, automatic renewal, pruning or deletion is supplied.

## Trust and limits

Use a single trusted machine and a local disk. Network filesystems and separate
hosts are unsupported. Names and UUIDs are cooperative tokens, not authenticated
identities or security boundaries: anyone with database access can impersonate a
participant, read messages, or alter state. Use operating-system permissions and
keep secrets out of message bodies. Coordination does not guarantee exclusive
writes, safe Git operations, exactly-once external effects, or code quality.
The tool reads no production configuration and invokes no external commands.

Database files and common SQLite sidecars are ignored by Git; keep any custom
DB filename outside the repository or extend the ignore rules yourself.

## Help project agents improve

The [supervised improvement method](examples/AGENT_IMPROVEMENT.md) shows how
business agents can contribute evidence and proposals to development, with an
isolated reproduction, regression and counterfactual checks, cost/quality
measurement, an integrator's adoption or rejection decision, and learning saved
in artifacts the agent actually consumes. Its triage example is fictional.
The kit coordinates this loop through mail and exact-resource claims; it does
not train models or authorize operational actions automatically.

## Project context and license

Prepared by [Kanibal Studio](https://github.com/kanibal-studio), associated with
ALTA VISTA360, S.L.U. Our public sites are [K-Pulse](https://infos.kanibal-studio.com/),
[Altavista360](https://altavista360.com), and
[Altavista Conseil](https://altavista-conseil.com). These links provide context;
this local tool has no integration with those sites.

This package is released under the [MIT license](LICENSE).

**En français :** cet outil local facilite la coordination volontaire de plusieurs
agents : messages persistants, accusés de réception explicites et baux sur noms
exacts. Il ne contrôle ni les identités ni les fichiers. Un seul intégrateur
vérifie et intègre le travail. Les exemples et tests utilisent des données fictives.
