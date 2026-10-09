<div align="center">

<img alt="2ByteASR · 兔白字幕" src="docs/assets/readme/banner-ja.png" width="100%">

### ゲーム実況の字幕を、認識から完成動画まで。

3 つのローカルモデルが役割を分けて認識し、1 文字ずつ時刻が付きます。<br>
字幕スタジオで校正・カット・スタイル調整を行い、字幕を書き出すか動画に焼き込みます。

[![Windows x64](https://img.shields.io/badge/Windows-x64-b34470?style=flat-square)](#ダウンロードとインストール)
[![macOS 実験版](https://img.shields.io/badge/macOS-Apple%20Silicon%20%E5%AE%9F%E9%A8%93%E7%89%88-7a6a8c?style=flat-square)](#ダウンロードとインストール)
[![0.5.0 プレリリース](https://img.shields.io/badge/0.5.0-%E3%83%97%E3%83%AC%E3%83%AA%E3%83%AA%E3%83%BC%E3%82%B9-d6957c?style=flat-square)](#ダウンロードとインストール)
[![GPL-3.0-only](https://img.shields.io/badge/license-GPL--3.0--only-a48ad9?style=flat-square)](#ライセンスとサードパーティ条件)

[中文](README.md) · [English](README_EN.md) · **日本語**

[ほかとの違い](#ほかの字幕ツールとの違い) · [ダウンロード](#ダウンロードとインストール) · [モデル一覧](#モデル一覧) · [ソースから実行](#ソースから実行) · [ライセンス](#ライセンスとサードパーティ条件)

</div>

<br>

![日本語 UI の字幕スタジオ：字幕リスト、動画プレビュー、スタイルパネル、話者ごとのトラックを持つタイムライン](docs/assets/readme/studio-ja.png)

<sub>このページの画像はすべて実際のアプリ画面です（2026-10-09 開発版）。サンプルは 34 秒の中国語の 2 人の会話（自作の映像と合成音声）で、ローカルの MOSS + FireRedASR2-AED + Qwen3-ASR で認識した後、スタジオで修正しました。機能クリップは中国語 UI ですが、アプリは日本語・英語 UI にも対応しています。<a href="docs/assets/readme/README.md">素材について</a></sub>

## ほかの字幕ツールとの違い

### 3 つのモデルが別々に聞き取り、食い違いを表示

![レビューモード：MOSS と FireRed は「他」、Qwen3-ASR は「它」と認識。クリックで採用](docs/assets/readme/review.gif)

下書きは MOSS が作り、FireRedASR2-AED と Qwen3-ASR がそれぞれ独立して聞き直します。1 文字でも食い違えば記録されます。この字幕では MOSS と FireRed が「拉住**他**」（彼を引きつける）、Qwen3-ASR が「拉住**它**」（それ＝モンスターを引きつける）と聞き取りました。レビューモードは候補を並べて違う文字を強調し、クリック 1 回で採用できます。

<sub>この 34 秒のサンプルでは 9 区間のうち 3 区間で食い違いがありました。FireRed は「拿齐」を「拿起」、「捡掉」を「剪掉」と聞き取り、MOSS は「它」を「他」と書きました。いずれもレビューで並べて表示され、黙って書き換えられることはありません。</sub>

### 1 文字ずつ時刻付き、レーザーは文字の境目でカット

![2 つの字幕を結合し、レーザーをドラッグすると前後が表示され、離すと文字の間でカット](docs/assets/readme/razor.gif)

FireRedASR2-AED が文字・単語単位の開始と終了の時刻を出すので、区切りもカットも文字の境界に沿います。ローカルのルールで区切りがずれた箇所は、2 つを結合し、レーザーを正しい位置までドラッグすればカードに前半と後半が表示され、離すとカットされます。時刻は文字に付いてきて、いつでも元に戻せます。

### 話者ごとに自動でトラック分け

![タイムラインで話者ごとに字幕トラックが分かれ、その下に動画トラックと波形](docs/assets/readme/tracks.png)

MOSS が話者を区別すると、それぞれの字幕が自分のトラックに入ります。名前・色・既定スタイルは話者管理でまとめて変えられ、書き出し時は 1 つにまとめることも話者ごとに分けることもできます。

### ゲームごとの用語集

![用語集：ゲームごとの用語、誤認識、出典、確認状態](docs/assets/readme/glossary-ja.png)

キャラクター名、スキル、よくある誤認識をゲームごとに整理し、出典と確認状態も残します。認識の参考語として使い、校正では固有名詞の誤りを見つけます。次の録画でもそのまま使えます。

## 素材から完成動画まで

![日本語 UI のホーム画面：素材の投入口、3 つの役割カード、AI自動文分割、内容と用語](docs/assets/readme/home-ja.png)

素材、認識プラン、用語が 1 ページにまとまっています。「まず目標を選択」には品質優先の **MOSS + FireRedASR2-AED + Qwen3-ASR** のような組み合わせが用意され、役割ごとにモデルを変えたりオフにしたりできます。モデルはダウンロード後、手元の PC でオフライン実行されます。AI自動文分割と AI 校正は任意の手順で、ホーム画面でオフにできます。オンのときはご自身で設定したサービスを使います。

<p align="center">
  <img src="docs/assets/readme/progress.png" width="49%" alt="進捗画面：ローカル認識の 6 番目のステップで Qwen が独立して文字を確認中。各ステップの所要時間を表示">
  <img src="docs/assets/readme/completion.png" width="49%" alt="完了画面：字幕 14 件、所要 2:42、確認項目と全字幕のプレビュー">
</p>

進捗画面には現在のステップと各ステップの所要時間・結果が並び、実行ログはプロジェクトのレポートにも保存されます。完了画面には字幕数、確認が必要な項目、全字幕のプレビューが表示されます。

<sub>34 秒のサンプルをローカルの RTX 5070 Ti で 1 回実行した実測で、モデルの読み込みを含みます。所要時間は環境や素材によって変わります。</sub>

<p align="center">
  <img src="docs/assets/readme/speakers-ja.png" width="49%" alt="話者管理：話者の名前・色・既定スタイルを設定">
  <img src="docs/assets/readme/export.png" width="49%" alt="焼き込み完了：H.264、1920×1080、30 fps、ビットレートと所要時間">
</p>

字幕スタジオで校正し、スタイルや登場の動きを調整して、SRT・ASS・TXT・JSON を書き出すか、字幕を焼き込んだ動画を作れます。焼き込み完了画面にはコーデック、解像度、ビットレート、所要時間が表示されます。

<sub>焼き込み完了画面のローカル出力パスは隠しています。</sub>

## その他

![日本語 UI のモデルワークショップ：役割ごとにモデルを選び、サイズ・実行方式・参考指数を確認](docs/assets/readme/workshop-ja.png)

**モデルワークショップ**は役割ごとに使えるモデルを一覧にし、サイズ、実行方式、参考指数を見ながらダウンロードや切り替えができます。

![5 つの UI テーマ：ディープグレープ、ウォームクリーム、ウォームナイト、ラベンダー、スレート](docs/assets/readme/themes.png)

既定の**ディープグレープ / ワイン**のほか、ウォームクリーム / グリーン、ウォームナイト / クリーム、ラベンダー・ワークスペース、スレート / エディトリアルの各テーマがあります。UI は中国語・英語・日本語に対応しています。

## モデル一覧

**メイン転写**

- ローカル：**MOSS-Transcribe-Diarize**（複数話者と話者分離）、SenseVoice Small（CPU 可）、FireRedASR2-AED、Qwen3-ASR 1.7B、Paraformer Large、Whisper large-v3-turbo、Fun-ASR Nano、FireRedASR2-LLM、GLM-ASR-Nano、Canary-Qwen-2.5B（英語）
- オンライン（ご自身のアカウント）：Qwen Audio 3.1 長時間音声、Spark-ASR 2.0、Groq Whisper、OpenAI Transcribe、MAI 2.1（OpenRouter）、OpenAI 互換エンドポイント

**字幕タイムライン**

- ローカル：**FireRedASR2-AED**、Qwen3-ForcedAligner 0.6B、Paraformer Large、Whisper large-v3-turbo

**テキストレビュー**

- ローカル：**Qwen3-ASR 1.7B**、SenseVoice Small、Whisper large-v3-turbo、FireRedASR2-LLM、Fun-ASR Nano
- オンライン：メイン転写と同じオンラインエンドポイント

太字は品質優先の組み合わせです。MOSS、FireRedASR2-AED、Qwen3-ASR などのローカルモデルには NVIDIA CUDA 対応 GPU が必要です。SenseVoice Small は CPU だけでも動きます。モデルの重みはアプリに同梱されません。モデルワークショップから必要に応じてダウンロードし、それぞれのライセンスに従って使います。オンラインエンドポイントは各サービスの条件で課金され、一部は実験的な接続です。Omnilingual ASR LLM 7B は重みのみの掲載で、ネイティブ Windows での推論には未対応です。

## ダウンロードとインストール

> [!NOTE]
> 公開インストーラーはまだリリースしていません。0.5.0 プレリリース（Windows x64 と macOS Apple Silicon 実験版）は公開後に [Releases](https://github.com/NOTBAD314/2ByteASR/releases) に掲載します。現時点では[ソースから実行](#ソースから実行)できます。

| システム | 要件 | 状態 |
| --- | --- | --- |
| Windows | Windows 10 22H2（19045）以降、x64。ローカル GPU モデルには NVIDIA GPU が必要 | 主要プラットフォーム |
| macOS | macOS 15 以降、Apple Silicon | 実験版：SenseVoice CPU の基本フローを確認済み。Developer ID 署名と公証はなし。[説明](docs/deployment/macos-experimental.zh-CN.md)（中国語） |

**はじめの 3 ステップ**

1. **モデルワークショップ**で使うモデルをダウンロードするか、オンラインサービスのキーを入力します。
2. ホーム画面に動画や音声をドロップし、認識プランを選んで**字幕生成を開始**を押します。
3. 完了したら**字幕スタジオ**で校正・仕上げを行い、字幕を書き出すか完成動画を焼き込みます。

| 用途 | 形式 |
| --- | --- |
| 読み込み | MP4、MOV、MKV、WebM、FLV、AVI／MP3、WAV、M4A、FLAC、AAC |
| 字幕と原稿 | SRT、ASS、TXT、JSON。話者はまとめても個別にも書き出せます |
| 完成動画 | MP4、MKV、MOV |

インストール、モデル、形式の詳細は[利用ガイド](docs/product-guide.ja.md)を参照してください。

## ソースから実行

```powershell
git clone https://github.com/NOTBAD314/2ByteASR.git
cd 2ByteASR
.\setup_environment.bat
.\.venv-main\Scripts\python.exe quick_start.py
```

このリポジトリは 0.5.0 の独立したソース範囲（2026-10-02 時点のスナップショット）です。完全なインストーラーに対応するソース一式ではなく、ここから完全なパッケージを作れることも検証していません。スクリーンショットはより新しい開発版のため、画面が異なる場合があります。詳しくは[ソース範囲](SOURCE_ONLY_SCOPE.md)、[ビルド手順](BUILD_FROM_SOURCE.md)、[コントリビューションガイド](CONTRIBUTING.md)を参照してください。

## ライセンスとサードパーティ条件

- **プロジェクトのコード**は [GPL-3.0-only](LICENSE)（[適用範囲](PROJECT_LICENSE.md)）です。公式版は無料で提供しています。GPL に従えば商用利用・改変・配布ができ、配布時には対応するソースの提供などの義務があります。個人的な改変を公開する必要はなく、このアプリで作った通常の字幕・動画・画像がそれだけで GPL の対象になることはありません。
- **サードパーティのコンポーネント**はそれぞれのライセンスに従います（Qt／PySide6、FFmpeg、mpv など）。高精度レンダリングに使う **Remotion** は個人と従業員 3 人までの営利組織は無料で、それより大きい営利組織には Company License が必要です。**GSAP** は標準ライセンスで、MIT ではありません。詳細は[サードパーティ通知](THIRD_PARTY_NOTICES.md)を参照してください。
- **モデルの重み**はアプリと一緒に配布されず、ダウンロード後はそれぞれのライセンス（Apache-2.0、MIT、CC-BY-4.0、FunASR モデルライセンスなど）に従って使います。[モデルライセンス表](licenses/MODELS.md)を参照してください。
- **オンラインサービス**はご自身のアカウントとキーを使い、各サービスの条件で課金されます。有効にすると、該当する音声や文字が選択したサービスに送信されます。
- 完全なインストーラーの公開配布に必要な資料は整備中です。[配布状況](licenses/DISTRIBUTION-STATUS.md)と[ソース提供の説明](SOURCE_DELIVERY.md)を参照してください。

## フィードバック

[Issues](https://github.com/NOTBAD314/2ByteASR/issues) に報告するときは、バージョン、使用したモデル、再現手順、スクリーンショットを添えてください。
