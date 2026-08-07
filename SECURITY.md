# Security policy

## Credentials and private data

2ByteASR reads `DASHSCOPE_API_KEY` and optional `HF_TOKEN` from environment variables or Windows DPAPI-encrypted `%LOCALAPPDATA%\2ByteASR\secrets.dat`. Never place credentials in source files, `twobyteasr_settings.json`, reports, screenshots, or issue attachments.

Task reports contain media paths and recognized text metadata. Voiceprint samples and learned mappings may be personally identifying. Review and redact them before sharing diagnostics.

Runtime event logs are redacted and retained for at most 30 days / 100 files, but they can still contain local paths and processing metadata.

## Model and network trust

Model repositories and source revisions are pinned in `dependencies.lock.json`. Files that contain executable model code, Pickle-compatible checkpoints, configuration, or speaker embeddings are checked against locked SHA-256 values before use. FireRed checkpoints are loaded with PyTorch's restricted `weights_only` unpickler. Qwen3-ASR does not fall back to an unpinned online model or user cache.

Cloud model endpoints require HTTPS, except explicit loopback addresses such as `http://127.0.0.1`. Domain-term evidence follows redirects manually, rejects non-public destinations, and stops reading after 1.5 MB.

`qwen-asr 0.0.6` currently requires Transformers 4.57.6. Newer fixed Transformers releases are not API-compatible with this package. The application therefore disables online fallback and verifies the locked Qwen model configuration before the vulnerable loader is reached. Do not bypass the model lock or point the application at arbitrary model directories; this compatibility pin should be removed when upstream publishes a compatible release.

## Reporting a vulnerability

Do not open a public issue containing a working credential, private audio, or an exploitable proof of concept. Contact the repository owner privately and include:

- affected version or commit;
- impact and reproduction conditions;
- the smallest redacted log that demonstrates the problem.

If a credential is exposed, revoke it immediately. Removing it from a later commit is not sufficient because Git history may retain it.
