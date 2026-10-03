# License Registry — Third-Party Models & Datasets

Rules (plan §15): prefer MIT / Apache-2.0 / BSD / clearly compatible CC. **Never assume a
Hugging Face dataset or model is usable just because it is hosted there.** Every dependency on
this list must carry repo ID, pinned revision, license, provenance, and restrictions in
`configs/registries/models.yaml` (or a dataset manifest under `datasets/manifests/`) before it
is downloaded. Re-verify before any release — hub terms change.

## Cleared candidates (verified at planning time; re-verify revision + license at first use)

| repo | license | notes |
|---|---|---|
| `openai/whisper-small` | Apache-2.0 | ASR init candidate |
| `openai/whisper-large-v3-turbo` | MIT | ASR init candidate |
| `ai4bharat/indic-conformer-600m-multilingual` | MIT | ASR init candidate, **gated** (Hub access required) |
| `pyannote/speaker-diarization-3.1` | MIT | diarization, **gated** (Hub access required) |
| `ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition` | Apache-2.0 | audio baseline candidate |

## Explicitly EXCLUDED from the commercial-friendly base

| repo | license | reason |
|---|---|---|
| `audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim` | CC-BY-NC-SA-4.0 | non-commercial + share-alike; incompatible with the licensing base |

Do not add excluded models as dependencies, baselines, or distillation teachers.

## In-repo assets

- All first-party code: MIT (see root `LICENSE`).
- Phase 0/1 ships **no** third-party weights and **no** external datasets; effect definitions
  (`configs/effects/*.yaml`) and the 52-card / integer-range hypothesis spaces are first-party.
