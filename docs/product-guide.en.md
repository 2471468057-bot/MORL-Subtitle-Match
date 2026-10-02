# 2ByteASR: installation, models, and advanced use

0.5.0 platform status: the Windows repair build has verified local transcription, editing/cuts, subtitles and a short video export. The macOS Apple Silicon experiment has a verified SenseVoice CPU workflow, with ad hoc signing only and no Developer ID signature or notarization. No public installer is available yet; the Docker product direction has been retired.

## Installation and setup

No public installer is available yet; internal test candidates are not public downloads. This repository provides a limited source-only scope, not the complete Corresponding Source for an existing Setup.

1. Read the [source scope and build requirements](../SOURCE_ONLY_SCOPE.md), then prepare authorized external dependencies in a separate environment. The remaining steps describe product use after dependencies are ready.
2. Open Model Workshop to download the selected model weights and prepare their runtime environments.
3. For online services, enter the account details or API key for your provider.
4. Import video or audio, choose your recognition setup, and start generating subtitles.

The default theme is Deep Grape. Change the color scheme in Appearance settings.

## Choosing models

Transcription, character and word timing, and text review serve different purposes. Combine them to suit your language, hardware, and available services.

| Role | Purpose | Common options |
| --- | --- | --- |
| Main transcription | Turns speech into text, with speaker identification where supported by the model | MOSS, SenseVoice, Whisper |
| Character and word timing | Locates boundaries for segmentation and timing adjustments | FireRedASR2-AED, Paraformer, standalone aligners |
| Text review | Compares candidates to check misrecognized words, names, and context | Qwen3-ASR, local or online review options |

Check each model's requirements in Model Workshop. SenseVoice supports CPU processing; MOSS, FireRedASR2-AED, Qwen3-ASR 1.7B, and Qwen3-ForcedAligner use NVIDIA CUDA. Once the models are downloaded, local recognition can run offline.

Enable AI sentence segmentation, text proofreading, terminology search, subtitle design, and clip analysis as needed. Online services use your own account or API key and follow your provider's billing terms; the relevant media or text is sent to the selected service.

## Input and output

| Use | Formats |
| --- | --- |
| Video input | MP4, MOV, MKV, WebM, FLV, AVI |
| Audio input | MP3, WAV, M4A, FLAC, AAC |
| Subtitle import in Studio | SRT, ASS |
| Subtitle and transcript output | SRT, ASS, TXT, JSON, separate speaker tracks |
| Video output | MP4, MKV, MOV |

Select subtitles and clips in Studio, adjust text, timing, styles, and video, then export the format you need. Save your project to continue editing later.

## Run and build from source

From the repository directory on Windows, prepare the environment and start the app:

```powershell
.\setup_environment.bat
.\.venv-main\Scripts\python.exe quick_start.py
```

See the [contribution guide](../CONTRIBUTING.md) for development and testing, and [source scope](../SOURCE_ONLY_SCOPE.md) / [build instructions](../BUILD_FROM_SOURCE.md) for external dependencies and missing inputs. A complete build from this tree has not been verified.

## Reporting issues

Include your version, model, steps to reproduce, and screenshots in an [issue](https://github.com/NOTBAD314/2ByteASR/issues).

[Back to the product overview](../README_EN.md) · [Interface and feature tour](product-demo.en.md) · [Third-party components](../THIRD_PARTY_NOTICES.md)
