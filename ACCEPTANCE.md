# Final Acceptance

Run `scripts/acceptance.sh` on Linux/macOS or `scripts/verify.ps1` on Windows. Both scripts create `acceptance-report.txt` and leave the live-only checks explicit rather than silently treating source tests as production verification.

The automated suite covers compilation, Python tests, Compose configuration, container startup and API/database health. The target-laptop verification should then execute the role isolation, deadline, evaluation ownership, public-vote abuse, audit, webhook signature, public Ed25519 record and export/import checks against the running Docker stack.
