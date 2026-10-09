# 2ByteASR: a tour of the interface

Everything below is the real app (development build, 2026-10-09). The sample is a self-made animation with two synthetic Chinese voices, recognised locally with MOSS + FireRedASR2-AED + Qwen3-ASR. How the assets were made is described in the [asset notes](assets/readme/README.md) (Chinese). Clips without "English UI" in the caption show the Chinese interface.

## Home and recognition

![Home screen in English: media drop zone, the three recognition roles, AI smart segmentation and content terms](assets/readme/home-en.png)

Home (English UI): drop in media, choose primary transcription, subtitle timeline and text review, then click "Start subtitles".

![Progress page: current step, step log and the full run log](assets/readme/progress.png)

Progress: the current step, the time and result of each step, and the full run log.

![Completion page: subtitle count, elapsed time, items to check and a subtitle preview](assets/readme/completion.png)

Completion: subtitle count, elapsed time, items to check and a full preview.

## Subtitle Studio

![Subtitle Studio in English](assets/readme/studio-en.png)

Studio (English UI): captions list, video preview, style panel and a timeline with one track per speaker.

![Razor: after merging, drag the razor to preview both halves, then cut](assets/readme/razor.gif)

Razor: drag to preview both halves and release to cut; cuts land on word boundaries.

![Review mode: compare the text from different models and adopt one](assets/readme/review.gif)

Review: versions from different models side by side with the differences highlighted; click to adopt.

![Speaker manager in English: names, colours and default styles](assets/readme/speakers-en.png)

Speaker manager (English UI): names, colours and default styles.

## Export

![Subtitles with a soft pop-in effect in the exported video](assets/readme/output.gif)

Cut from the MP4 the app actually exported.

![Encode finished: codec, resolution, bitrate and time taken](assets/readme/export.png)

Encode finished (the local output path is masked).

## Terms, models and themes

![Term library in English](assets/readme/glossary-en.png)

Term library (English UI): terms, misrecognitions, sources and confirmation status per game.

![Model workshop in English](assets/readme/workshop-en.png)

Model workshop (English UI): models per role with size, runtime and reference scores.

![Five UI themes](assets/readme/themes.png)

Five UI themes: Deep Grape / Burgundy, Warm Cream / Green, Warm Night / Cream, Lavender Workspace and Slate / Editorial.

[Back to the overview](../README_EN.md) · [User guide](product-guide.en.md)
