# Security Engineering experiments

These offline experiments characterize CAN traffic and document security
evidence independently of the AI Engineer's model development. Reusable code
lives in the repository's `security/` package. Experiment folders contain their
configuration, small measured results, figures, reports, and reproduction notes.

The first experiment is [F00: Kia Soul normal CAN traffic](F00_normal_traffic/README.md).
It uses only two specified attack-free recordings. No attack experiment is
implemented here yet.

Install optional plotting dependencies with
`python -m pip install -r experiments/security/requirements.txt` in an isolated
environment. This adds Matplotlib without changing the Data/AI requirements.

Private data and temporary or large derived files stay local. Each experiment's
`local_outputs/` is ignored; only deliberately reviewed small artifacts should
be committed. Never add raw recordings, credentials, or feature Parquet files.

The permanent [GitLab workflow](../../AGENTS.md) applies: a fresh task branch
from updated main, meaningful commits, tests, an MR targeting main, and explicit
approval before merge. Verify the preceding MR was actually merged before
starting another implementation.
