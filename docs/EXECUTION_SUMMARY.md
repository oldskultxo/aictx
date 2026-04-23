# Execution summary

AICTX finalize output includes a deterministic user-facing summary payload:

- `agent_summary`: structured fields for runner integration
- `agent_summary_text`: compact Markdown suitable for appending to an agent final response

The summary reports only observed or persisted facts:

- whether a prior strategy was reused
- why it was selected when available
- whether learning, strategy memory, or failure memory was stored
- observed file/reopen counts
- commands and tests captured when available

AICTX does not claim quality or speed improvements from this summary.
