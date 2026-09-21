Add an optional `--strict` flag to this project.

When `--strict` is present, process all input records and produce the normal report, but exit with status 2 if there is at least one invalid record. Otherwise exit 0. Duplicate valid records alone must not cause a strict-mode failure.

Without `--strict`, keep the existing behavior. Preserve all Stage A requirements, including JSON/CSV output, grouped reports, and writing to an output file. Update relevant tests and documentation.
