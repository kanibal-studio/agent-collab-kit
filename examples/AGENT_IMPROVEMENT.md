# Improving project agents through supervised participation

This is a portable working method, not an automatic training engine. A business
agent performs an operational task (for example issue triage); a development
agent investigates and implements changes. Either can contribute a proposal,
but participation does not expand its permissions. First establish the tools,
inputs, instructions, models and actions each agent can actually use. Keep one
integrator responsible for adoption and for checking evidence.

## A bounded improvement loop

1. Observe a concrete signal: preserve a sanitized input, expected result, actual
   result, and the effect on users. An unverified complaint is a hypothesis.
2. Ask the relevant business agent for a proposal with evidence and uncertainty.
   Send it to the integrator through the mailbox; an acknowledgement records
   receipt, not acceptance. Rejected proposals remain useful learning signals.
3. Reproduce the case in an isolated environment with fictitious data and no
   production writes, real calls, paid actions or outgoing messages. Compare
   input quality, instructions, tool coverage, permissions and model behavior
   before deciding what to change.
4. Assign development work on disjoint exact resources. Workers claim files;
   the integrator coordinates shared changes. Fix the demonstrated mechanism,
   then test the reproduction and related behavior. Include a counterfactual:
   show the old mechanism fails the targeted case while the corrected one passes,
   using restored source and clean bytecode where applicable.
5. Measure quality and cost against the same representative cases. Account for
   latency, uncertainty, false positives and false negatives. A passing synthetic
   case does not prove operational success or economic benefit.
6. The integrator adopts or rejects the change using those results. Deployment
   and activation are separate decisions. Changes involving money, identity or
   external effects require the project's applicable review and authorization.
7. Persist the lesson where the agent actually consumes it: an instruction,
   tool contract, checked input, or regression test. Verify the consumer uses
   that artifact; a note nobody reads is not durable improvement. Observe the
   next authorized operation and record the result without overstating it.

## Fictional example: an issue triage agent

A fixture says `payment is pending; no duplicate charge`. The triage agent
incorrectly labels it `duplicate charge` because a tool exposes keywords without
negation context. The agent proposes a larger model but supplies no comparison
or reproduction. The integrator rejects that unsupported proposal and retains
the evidence requirement in the agent's consumed proposal instructions.

A development worker reproduces the error with the fixture, checks the tool's
input contract, and adds contextual text plus an explicit uncertainty response
for ambiguous statements. The fixture fails with the old contract and passes
with the corrected one; companion cases cover a genuine duplicate charge and
an ambiguous report. The integrator compares classification errors and measured
local execution cost, reviews the diff, and records an adoption decision. A
regression fixture is wired into the project's usual test command, and the
business agent's actual input adapter uses the revised contract.

This example demonstrates a method only. No model was trained, no production
triage occurred, and no customer or payment was contacted. Fine-tuning or model
replacement would require a demonstrated need, representative evaluation data,
a budget and the relevant authorization; they are not automatic next steps.

## Connect the method to this kit

Use an explicitly initialized temporary DB as in the README. Send the sanitized
signal and proposal with separate keys, such as `fixture-17-signal` and
`fixture-17-proposal-v1`. Reusing the same key with changed text is an error:
new revisions need new keys. The integrator reads its inbox and acknowledges the
message with its explicit recipient name.

```sh
python3 agent_collab.py --db "$DB" send --sender triage-agent --recipient integrator --key fixture-17-proposal-v1 --body 'Fictional proposal: reproduce negation error before choosing a model change'
python3 agent_collab.py --db "$DB" claim --resource src/triage_input.py --owner worker-a --ttl 300
python3 agent_collab.py --db "$DB" claim --resource tests/test_triage_input.py --owner worker-a --ttl 300
```

Retain each returned generation and use it for renewal or release. Each claim is
independent: if the second fails, release the first before selecting another
assignment. There is no atomic multi-resource claim. Put the evidence and final
decision in the project's existing consumed supports; the mailbox coordinates
handoffs but does not evaluate proposals, execute tests or change agents itself.
