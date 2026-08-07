# Contributing

2ByteASR currently targets Windows 10/11 with an NVIDIA CUDA GPU. Changes that affect subtitle text, speaker assignment, timing, caching, or output paths should include a regression test.

## Development setup

1. Run `setup_environment.bat`.
2. Run `download_models.bat` only when a GPU integration test is required.
3. Run `run_tests.bat` before submitting a change.

The unit test suite is intentionally offline and does not require model weights or a GPU. Do not commit media, model weights, task reports, voiceprints, API responses, or credentials.

## Change guidelines

- Keep `twobyteasr_settings.json` free of secrets.
- Preserve transactional subtitle output: a failed task must not replace a valid existing result with a partial file.
- Add or update fixtures for segmentation and timing behavior changes.
- Keep public dependencies and model/source revisions synchronized with `dependencies.lock.json` and `THIRD_PARTY_NOTICES.md`.
- Format user-visible errors in clear Chinese and include the exact recovery command when possible.
