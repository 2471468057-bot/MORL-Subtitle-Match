<div align="center">

<img alt="2ByteASR · 兔白字幕" src="docs/assets/readme/banner-en.png" width="100%">

### Game stream subtitles, from recognition to final cut.

Three local models share the work, and every character gets a timestamp.<br>
Proofread, cut and style in Subtitle Studio, then export subtitles or burn them into the video.

[![Windows x64](https://img.shields.io/badge/Windows-x64-b34470?style=flat-square)](#download-and-install)
[![macOS experimental](https://img.shields.io/badge/macOS-Apple%20Silicon%20experimental-7a6a8c?style=flat-square)](#download-and-install)
[![0.5.0 pre-release](https://img.shields.io/badge/0.5.0-pre--release-d6957c?style=flat-square)](#download-and-install)
[![GPL-3.0-only](https://img.shields.io/badge/license-GPL--3.0--only-a48ad9?style=flat-square)](#license-and-third-party-terms)

[中文](README.md) · **English** · [日本語](README_JA.md)

[What's different](#what-makes-it-different) · [Download](#download-and-install) · [Models](#model-catalog) · [Run from source](#run-from-source) · [License](#license-and-third-party-terms)

</div>

<br>

![Subtitle Studio in English: captions list, video preview, style panel and a timeline with one track per speaker](docs/assets/readme/studio-en.png)

<sub>Every image on this page is the real app (development build, 2026-10-09). The sample is a 34-second two-person conversation in Chinese (self-made visuals, synthetic voices), recognised locally with MOSS + FireRedASR2-AED + Qwen3-ASR and then corrected in Studio. Feature clips show the Chinese UI; the app also ships English and Japanese UI. <a href="docs/assets/readme/README.md">About these assets</a></sub>

## What makes it different

### Three models listen separately, and disagreements are flagged

![Review mode: MOSS and FireRed heard one character, Qwen3-ASR heard another; clicking adopts it](docs/assets/readme/review.gif)

MOSS writes the draft, then FireRedASR2-AED and Qwen3-ASR each listen again on their own, and any character that differs is recorded. Here MOSS and FireRed heard 拉住**他** ("hold him") while Qwen3-ASR heard 拉住**它** ("hold it", the monster). Review mode lists the versions side by side, highlights the differing character, and adopts one with a click.

<sub>In this 34-second sample, 3 of 9 speech segments had a disagreement: FireRed heard 拿齐 as 拿起 and 捡掉 as 剪掉, and MOSS wrote 他 for 它. Each one is listed side by side in review; none is changed silently.</sub>

### Every character is timed, so the razor cuts between characters

![After merging two subtitles, dragging the razor shows both halves and cuts between two characters on release](docs/assets/readme/razor.gif)

FireRedASR2-AED provides start and end times at the character and word level, so segmentation and cuts follow character boundaries. The local rules split a phrase in the wrong place: merge the two pieces, drag the razor to the right spot while the card previews both halves, and release to cut. Timing follows the characters, and every cut can be undone.

### One track per speaker, automatically

![The timeline with each speaker on their own subtitle track, above the video track and waveform](docs/assets/readme/tracks.png)

Once MOSS has told the speakers apart, each person's lines go on their own track. Names, colours and default styles are set in the speaker manager, and exports can merge speakers into one file or split them.

### Term libraries organised per game

![Term library: terms, misrecognitions, sources and confirmation status per game](docs/assets/readme/glossary-en.png)

Character names, skills and common misrecognitions are kept per game with sources and confirmation status. They guide recognition and help catch misspelled names when proofreading, and they carry over to the next recording.

## From media to final video

![Home screen in English: media drop zone, the three role cards, AI smart segmentation and content terms](docs/assets/readme/home-en.png)

Media, recognition plan and terms share one page. "Pick a goal first" offers ready-made combinations, for example the quality-first **MOSS + FireRedASR2-AED + Qwen3-ASR**, and every role can switch model or be turned off. Once downloaded, models run offline on your machine. AI smart segmentation and AI proofreading are optional steps you can turn off on the home screen; when on, they use a service you configure.

<p align="center">
  <img src="docs/assets/readme/progress.png" width="49%" alt="Progress page: step 6 of local recognition, Qwen re-checking the text, with timings for each step">
  <img src="docs/assets/readme/completion.png" width="49%" alt="Completion page: 14 subtitles, 2:42 elapsed, items to check and a full subtitle preview">
</p>

The progress page shows the current step and the time and result of every step, and the full run log is saved with the project report. The completion page gives the subtitle count, items to check and a full preview.

<sub>One real run of the 34-second sample on a local RTX 5070 Ti, model loading included. Timing varies with hardware and media.</sub>

<p align="center">
  <img src="docs/assets/readme/speakers-en.png" width="49%" alt="Speaker manager: rename speakers and set colours and default styles">
  <img src="docs/assets/readme/export.png" width="49%" alt="Encode finished: H.264, 1920×1080, 30 fps, bitrate and time taken">
</p>

In Subtitle Studio you proofread, adjust styles and entrance motion, export SRT, ASS, TXT or JSON, or encode a video with the subtitles burned in. The encode page reports codec, resolution, bitrate and time taken.

<sub>The local output path on the encode page has been masked.</sub>

## More

![Model workshop in English: pick models per role and see size, runtime and reference scores](docs/assets/readme/workshop-en.png)

The **Model workshop** lists the models for each role with size, runtime and reference scores, and downloads or switches them in one place.

![Five UI themes: Deep Grape, Warm Cream, Warm Night, Lavender and Slate](docs/assets/readme/themes.png)

Besides the default **Deep Grape / Burgundy** theme there are Warm Cream / Green, Warm Night / Cream, Lavender Workspace and Slate / Editorial. The interface is available in Chinese, English and Japanese.

## Model catalog

**Primary transcription**

- Local: **MOSS-Transcribe-Diarize** (multi-speaker with diarization), SenseVoice Small (CPU capable), FireRedASR2-AED, Qwen3-ASR 1.7B, Paraformer Large, Whisper large-v3-turbo, Fun-ASR Nano, FireRedASR2-LLM, GLM-ASR-Nano, Canary-Qwen-2.5B (English)
- Online (your own account): Qwen Audio 3.1 long-audio, Spark-ASR 2.0, Groq Whisper, OpenAI Transcribe, MAI 2.1 (OpenRouter), OpenAI-compatible endpoints

**Subtitle timeline**

- Local: **FireRedASR2-AED**, Qwen3-ForcedAligner 0.6B, Paraformer Large, Whisper large-v3-turbo

**Text review**

- Local: **Qwen3-ASR 1.7B**, SenseVoice Small, Whisper large-v3-turbo, FireRedASR2-LLM, Fun-ASR Nano
- Online: the same online endpoints as primary transcription

Bold entries form the quality-first combination. MOSS, FireRedASR2-AED, Qwen3-ASR and similar local models need an NVIDIA CUDA GPU; SenseVoice Small can run on CPU only. Model weights are not bundled. Download them in the model workshop; each model follows its own license. Online endpoints are billed by their providers, and some are experimental. Omnilingual ASR LLM 7B is listed as weights only; native Windows inference is not supported.

## Download and install

> [!NOTE]
> No public installer has been released yet. The 0.5.0 pre-release (Windows x64 and an experimental macOS Apple Silicon build) will appear under [Releases](https://github.com/NOTBAD314/2ByteASR/releases) once published. Meanwhile you can [run from source](#run-from-source).

| System | Requirements | Status |
| --- | --- | --- |
| Windows | Windows 10 22H2 (19045) or later, x64; local GPU models need an NVIDIA GPU | Main platform |
| macOS | macOS 15 or later, Apple Silicon | Experimental: the SenseVoice CPU workflow is verified; no Developer ID signature or notarization. See the [notes](docs/deployment/macos-experimental.zh-CN.md) (Chinese) |

**Three steps to start**

1. Open the **Model workshop** and download the models you want, or enter the keys for an online service.
2. Back on the home screen, drop in a video or audio file, choose a recognition plan and click **Start subtitles**.
3. Open **Subtitle Studio** to proofread and polish, then export subtitles or encode the final video.

| Purpose | Formats |
| --- | --- |
| Import | MP4, MOV, MKV, WebM, FLV, AVI; MP3, WAV, M4A, FLAC, AAC |
| Subtitles and transcripts | SRT, ASS, TXT, JSON; speakers merged or exported separately |
| Final video | MP4, MKV, MOV |

Installation, model and format details are in the [user guide](docs/product-guide.en.md).

## Run from source

```powershell
git clone https://github.com/NOTBAD314/2ByteASR.git
cd 2ByteASR
.\setup_environment.bat
.\.venv-main\Scripts\python.exe quick_start.py
```

This repository is the standalone 0.5.0 source scope (snapshot of 2026-10-02). It is not the complete corresponding source of the full installer, and a complete package build from it has not been verified. The screenshots come from a newer development build, so the interface will differ. See the [source scope](SOURCE_ONLY_SCOPE.md), [build notes](BUILD_FROM_SOURCE.md) and [contributing guide](CONTRIBUTING.md).

## License and third-party terms

- **Project code** is licensed under [GPL-3.0-only](LICENSE) ([scope](PROJECT_LICENSE.md)). Official builds are free. You may use, modify and distribute it commercially under the GPL, including the obligation to provide corresponding source. Private modifications need not be published, and ordinary subtitles, videos and images made with the app do not become GPL-licensed just because of that.
- **Third-party components** keep their own licenses, for example Qt/PySide6, FFmpeg and mpv. **Remotion**, used by the high-fidelity renderer, is free for individuals and for-profit organisations of up to 3 employees; larger for-profit organisations need its Company License. **GSAP** uses its standard license, not MIT. Details are in the [third-party notices](THIRD_PARTY_NOTICES.md).
- **Model weights** are not distributed with the app and are used under their own licenses once downloaded (Apache-2.0, MIT, CC-BY-4.0, the FunASR model license and others). See the [model license table](licenses/MODELS.md).
- **Online services** use your own accounts and keys and are billed by their providers. When enabled, the relevant audio or text is sent to the selected service.
- Distribution materials for the full installer are still being completed; see the [distribution status](licenses/DISTRIBUTION-STATUS.md) and [source delivery notes](SOURCE_DELIVERY.md).

## Feedback

When filing an [issue](https://github.com/NOTBAD314/2ByteASR/issues), please include the version, the models used, steps to reproduce and screenshots.
