# LLM-UAV Mission Computer — Systems Engineering Documentation

## Documents

The V1.0 documentation set is frozen as of git tag `v1.0`. Retrieve any V1.0 document as it was at the freeze with `git show v1.0:docs/<file>`.

| Document | Description |
|---|---|
| architecture_baseline.md | LLM-UAV-Mission-Computer V1.0 — frozen as-built baseline |
| system_requirements.md | System-level requirements (SHALLs) |
| block_definition.md | SysML-style block definitions and responsibilities |
| interface_control.md | Interface control document — data flows between blocks |
| state_machine.md | Formal state machine specification |
| hardware.md | Pennyroyal hardware constraints, memory budget, and quantization guidance |
| inference_setup.md | Native llama.cpp build and launch instructions for Pennyroyal |
| troubleshooting.md | Known failure modes and fixes |
| prompt_design.md | Prompt design principles and visual grounding strategy |
| results.md | Mission run records and observed failure modes |
| scratchpad.md | Model-authored scratchpad — design, philosophy, and schema |

The systems engineering documents (requirements, block definitions, ICD, state machine) describe the system as designed for SITL simulation and must be updated before any HIL or real flight testing.

The operational documents (hardware, inference_setup, troubleshooting, prompt_design) reflect lessons from active SITL testing and are updated as the system evolves.
