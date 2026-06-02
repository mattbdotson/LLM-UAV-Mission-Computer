# LLM-UAV Mission Computer — Systems Engineering Documentation

## Documents

| Document | Description |
|---|---|
| system_requirements.md | System-level requirements (SHALLs) |
| block_definition.md | SysML-style block definitions and responsibilities |
| interface_control.md | Interface control document — data flows between blocks |
| state_machine.md | Formal state machine specification |
| hardware.md | Pennyroyal hardware constraints, memory budget, and quantization guidance |
| inference_setup.md | Native llama.cpp build and launch instructions for Pennyroyal |
| troubleshooting.md | Known failure modes and fixes |
| prompt_design.md | Prompt design principles and visual grounding strategy |

The systems engineering documents (requirements, block definitions, ICD, state machine) describe the system as designed for SITL simulation and must be updated before any HIL or real flight testing.

The operational documents (hardware, inference_setup, troubleshooting, prompt_design) reflect lessons from active SITL testing and are updated as the system evolves.
