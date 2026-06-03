# Model-Authored Scratchpad

## Document Control
- Version: 0.1
- Status: Draft
- Last updated: 2026-06-02

## What It Is

The scratchpad is a continuity mechanism for the mission planner. After each decision, the model may write two free-text fields into its JSON response:

```json
{
  "command": "goto_pixel",
  "reasoning": "...",
  "params": {"x": 320, "y": 50},
  "progress": "I have flown to the eastern edge and found the prominent north-south road. I am now flying south along it.",
  "next_intent": "Continue south to the southern map edge, then begin Phase 4 northbound."
}
```

The system stores the most recent non-empty values of these fields and surfaces them back to the model at the top of the next decision prompt:

```
Your notes from your last decision:
progress: "I have flown to the eastern edge and found the prominent north-south road. I am now flying south along it."
next_intent: "Continue south to the southern map edge, then begin Phase 4 northbound."
```

Both fields are optional. If the model omits them, or writes empty strings, the previously-stored values are preserved. The scratchpad is never blanked by the system — it persists across `stuck` re-prompts as well as normal `waypoint_reached` events.

## Why It Exists

Three consecutive runs of the boundary survey mission all failed in the same way: the model correctly executed multi-phase navigation for several decisions, then the `no_progress` / `stuck` event fired, the model was re-prompted, and it regressed to Phase 1 — undoing all prior progress. The model had no working memory. It re-derived its phase from current position alone, identified the first phase instruction, and started over.

The scratchpad gives the model a place to record its own beliefs about completed phases and current intent, without the system injecting that state.

## Design Philosophy

The critical constraint is that the system **must not** interpret, validate, or modify the scratchpad contents. The model's notes are stored verbatim and surfaced verbatim. This is intentional:

- **Preserved autonomy**: the model's beliefs are derived from its own perception (the map image and telemetry) and persisted as its own record. System-injected phase state would be a structured answer key returning by a different door — the same problem that was deliberately stripped from the prompts earlier.
- **Observable failure**: if the model writes an incorrect belief (e.g., claims to have completed Phase 3 when it has not), that claim propagates. This is not a bug. The scorer measures how often the scratchpad content is consistent with actual position, giving a quantitative view of model self-awareness. Wrong beliefs are the signal, not noise.
- **Minimal surface area**: the system stores two strings and echoes them. No parsing, no validation, no structured fields. Adding `current_phase: int` would reintroduce the answer key.

## Storage and Logging

`MissionContext` holds `last_progress` and `last_next_intent` in memory. Every decision is appended to `decisions.jsonl` in the mission archive directory, including the `progress` and `next_intent` fields (null if the model did not write them that turn). This log is the primary artifact for post-hoc scratchpad analysis.

## Known Failure Mode

Wrong beliefs persist. If the model confabulates — reporting visual features it didn't see, or claiming to have completed a phase it hasn't — those claims will be fed back to it on the next turn and may compound. This is characterised by looking at the scratchpad trace in `decisions.jsonl` alongside the debug maps. See [troubleshooting.md](troubleshooting.md).

## Schema Reference

| Field | Type | Behaviour if absent |
|---|---|---|
| `progress` | string | Previous value preserved |
| `next_intent` | string | Previous value preserved |

Both fields may be present in any response that includes any valid command. The system does not require them.
