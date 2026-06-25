# L0 System Requirements — V2.0 ("Sight" Increment)

## Document Control
- Version: 0.1
- Status: Draft
- Applies to: V2.0 increment, SITL + Gazebo simulation phase only
- Last updated: 2026-05-08

> Second left-arm artifact of the V2.0 increment, derived from the ConOps ([conops.md](conops.md)).
> **L0** requirements address the system as a whole. They are used to define the system
> architecture and to derive lower-level (L1+) requirements. Each requirement traces to the
> ConOps section(s) it satisfies (the `Trace` column refers to `conops.md` section numbers).

## Conventions
- "SHALL" denotes a binding requirement.
- "The system" means the autonomy stack as defined in the ConOps (the Mission Manager,
  perception, and reasoning together — everything that is neither the autopilot nor the
  simulated world).
- IDs are stable: `L0-<CAT>-NN`. Retired IDs are not reused.

---

## 1. Mission & Reasoning (MIS)

| ID | Requirement | Trace |
|---|---|---|
| L0-MIS-01 | The system SHALL execute missions defined by a natural-language objective. | §12, §11 |
| L0-MIS-02 | The system SHALL use a vision-language model as the mission-level decision authority. | §2, §3 |
| L0-MIS-03 | The system SHALL express each mission decision as a structured command carrying a machine-readable reasoning field. | §11, §12 |
| L0-MIS-04 | The system SHALL maintain mission state across a flight. | §2 |
| L0-MIS-05 | The reasoning layer SHALL reason over a distilled map view derived from the world model and SHALL NOT be given raw camera frames. | §1, §3 |
| L0-MIS-06 | The system SHALL invoke the reasoning layer event-driven at discrete decision points, not continuously or on a timer. | §2, §3 |
| L0-MIS-07 | The system SHALL provide accumulated decision and world context to the reasoning layer at each invocation. | §2, §11 |
| L0-MIS-08 | The system SHALL autonomously return to launch and land on mission completion or abort. | §11.1, §12 |

## 2. Perception (PER)

| ID | Requirement | Trace |
|---|---|---|
| L0-PER-01 | The system SHALL continuously perceive from the onboard camera stream, independent of the reasoning layer's cadence. | §3 |
| L0-PER-02 | The system SHALL detect and classify targets and landmarks, assigning each a class and confidence. | §7, §1 |
| L0-PER-03 | The system SHALL geo-locate detections into geodetic coordinates from sensor data and aircraft pose. | §5 |
| L0-PER-04 | The system SHALL maintain persistent, uniquely identified tracks for detected entities. | §6, §7 |
| L0-PER-05 | The system SHALL represent each track's position uncertainty and SHALL NOT present an uncertain position as exact. | §11.2 |
| L0-PER-06 | The system SHALL expire or flag stale tracks so out-of-date world state is not presented as current. | §11.2 |
| L0-PER-07 | The system SHALL estimate kinematic state (velocity) for slow-moving tracked targets. | §7 |
| L0-PER-08 | Geo-location accuracy SHALL meet a bound sufficient for the reasoning layer to act on (value TBD, derived at lower level). | §10 |

## 3. Sensor Tasking / Attention (TSK)

| ID | Requirement | Trace |
|---|---|---|
| L0-TSK-01 | The reasoning layer SHALL be able to task the sensor to observe a specific track held in the registry. | §6 |
| L0-TSK-02 | The system SHALL carry out an observation as delegated closed-loop control — the aircraft orbiting the target and the sensor holding it centered — without reasoning-layer involvement for the duration of the loop. | §6, §11 |
| L0-TSK-03 | The system SHALL keep the orbit and the sensor centered on a slow-moving target's live, continuously-updated position throughout an observation. | §7 |
| L0-TSK-04 | Every observation SHALL have a defined termination condition. | §10, §11.3 |
| L0-TSK-05 | The system SHALL escalate to the reasoning layer when an observation cannot continue, including when the target is lost or becomes un-observable. | §6, §11.2 |
| L0-TSK-06 | The system SHALL conduct at most one observation at a time. | §11.2 |
| L0-TSK-07 | Sensor-tasking and target-selection references issued by the reasoning layer SHALL be symbolic registry references, not pixel coordinates or appearance descriptions. | §6 |

## 4. Decision Triggers (EVT)

| ID | Requirement | Trace |
|---|---|---|
| L0-EVT-01 | The system SHALL invoke the reasoning layer when a sufficiently confident detection occurs, interrupting the current activity rather than waiting for the next routine decision point. | §11.1, §11.3 |
| L0-EVT-02 | The system SHALL gate detection-triggered interrupts by mission state, raising them only in states where acting on a detection is appropriate, and otherwise deferring or suppressing them. | §11.3, §11.2 |

## 5. Safety & Degradation (SAF)

| ID | Requirement | Trace |
|---|---|---|
| L0-SAF-01 | The system SHALL delegate all low-level flight control to the autopilot and SHALL NOT issue control-surface commands. | §2 |
| L0-SAF-02 | The system SHALL keep perception out of the flight-safety loop in this increment: perception outputs SHALL NOT command flight control and SHALL NOT serve as safety-critical inputs to flight decisions. | §7, §9 |
| L0-SAF-03 | Continuous perception SHALL NOT block or stall the autopilot telemetry/command path. | §9 |
| L0-SAF-04 | A perception failure SHALL degrade to "no detections" and SHALL NOT disable the mission-management function. | §9 |
| L0-SAF-05 | The system SHALL fall back to a safe default (e.g., RTL or hold) on reasoning failure, command-parse failure, or loss of a required input. | §9, §11.2 |
| L0-SAF-06 | The system SHALL NOT begin a mission unless the required reasoning and perception services are confirmed healthy. | §12 |
| L0-SAF-07 | The system SHALL allow the operator to abort the mission (command RTL/hold) at any time. | §12.5 |

## 6. Interfaces & Sim/Real Boundary (IFC)

| ID | Requirement | Trace |
|---|---|---|
| L0-IFC-01 | The autonomy stack SHALL interface with its environment only via MAVLink (telemetry from, and commands to, the autopilot) and an inbound camera-frame stream, and SHALL emit only MAVLink. | §9 |
| L0-IFC-02 | Replacing the simulated autopilot, world, or camera with real equivalents SHALL require no change inside the autonomy stack. | §9 |

## 7. Integrity (INT)

| ID | Requirement | Trace |
|---|---|---|
| L0-INT-01 | The system SHALL derive all world knowledge from its sensor and telemetry streams. Authored scenario ground-truth SHALL NOT be supplied to any part of the system as input — including via the sensor streams, the world model, or the reasoning layer's prompts. | §9, §12.1 |

## 8. Observability & Logging (LOG)

| ID | Requirement | Trace |
|---|---|---|
| L0-LOG-01 | The system SHALL log every reasoning decision together with its issued command and the reasoning behind it. | §11, §12 |
| L0-LOG-02 | The system SHALL log perception output (detections and tracks) separately from reasoning decisions, so the two can be reviewed independently. | §12.2 |
| L0-LOG-03 | The system SHALL archive, per run, the mission configuration (objective, prompts, scenario reference) together with the decision and perception logs, the imagery the system reasoned over, and the mission outcome — sufficient to reconstruct and review the run. | §12.7, §12.2 |
| L0-LOG-04 | All logged decisions and perception outputs SHALL be timestamped and mutually correlatable, so the perceived world-state and the decisions taken can be aligned in time during review. | §12.2, §12.4 |

## 9. Simulation & Test (SIM)

| ID | Requirement | Trace |
|---|---|---|
| L0-SIM-01 | The flight stack (perception + reasoning) SHALL run on flight-representative edge hardware, separate from the simulation host. | §10, §12 |
| L0-SIM-02 | The system SHALL support authored scenarios with placed, perceivable entities (static or slow-moving) in a 3D world. | §12 |
| L0-SIM-03 | Scenarios SHALL be reproducible so runs are comparable across runs. | §12.2 |
| L0-SIM-04 | The system SHALL support a held-out scoring path comparing perceived world-state against authored ground-truth without exposing that truth to the system. | §12.1 |

---

## Summary

| Category | Prefix | Count |
|---|---|---|
| Mission & Reasoning | MIS | 8 |
| Perception | PER | 8 |
| Sensor Tasking / Attention | TSK | 7 |
| Decision Triggers | EVT | 2 |
| Safety & Degradation | SAF | 7 |
| Interfaces & Sim/Real Boundary | IFC | 2 |
| Integrity | INT | 1 |
| Observability & Logging | LOG | 4 |
| Simulation & Test | SIM | 4 |
| **Total** | | **43** |

## Open Items (to resolve at lower levels)
- **L0-PER-08** — geo-location accuracy bound is TBD; to be quantified when L1 requirements are derived (the ConOps sets it qualitatively via a "forgiving consumer").
- Reasoning-backend pluggability is treated as a design quality (architecture arm), not an L0 requirement.
- The stabilized-nadir-before-active-pointing validation sequence is an implementation/verification-plan item (right arm of the V), not an L0 requirement.
