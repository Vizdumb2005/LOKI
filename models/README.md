# models/ — Model Components

Phase 0/1 ships **no model weights** — all intelligence in the current vertical slice is the
classical (non-neural) baseline in `services/hypothesis/`, `services/policy/`, and
`services/language/`.

Component status, planned directories, and third-party initialization candidates are tracked in
the registries:

- [`configs/registries/models.yaml`](../configs/registries/models.yaml) — machine-readable source of truth
- [`docs/registries/model-registry.md`](../docs/registries/model-registry.md) — narrative + rules
- [`datasets/LICENSES.md`](../datasets/LICENSES.md) — cleared and **excluded** third-party models

Rule of thumb: no third-party model is downloaded, fine-tuned, or vendored before its registry
entry has a pinned revision and re-verified license (plan §15).
