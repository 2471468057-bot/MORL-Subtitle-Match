"""2026-10-11: in-app component update texts (check, sizes, download, restart).

English and Japanese were written in this round and have not been reviewed
by native speakers."""

UPDATE_2026_10_11: dict[str, tuple[str, str]] = {
    '检查更新': ('Check for updates', '更新を確認'),
    '正在检查…': ('Checking…', '確認中…'),
    '新版本 {value0}': ('New version {value0}', '新しいバージョン {value0}'),
    '重启以完成更新': ('Restart to finish update', '再起動して更新を完了'),
    '发现新版本 {value0}，点击查看更新内容和下载量': (
        'Version {value0} is available. Click to see what changed and how much to download',
        'バージョン {value0} があります。クリックすると変更内容とダウンロード量を確認できます'),
    '发现新版本': ('New version available', '新しいバージョンがあります'),
    '兔白字幕 {value0}（当前 {value1}）': ('2ByteASR {value0} (installed: {value1})', '2ByteASR {value0}（現在 {value1}）'),
    '主要变更': ('What changed', '主な変更点'),
    '本次需要下载：{value0}': ('Download needed: {value0}', '今回のダウンロード：{value0}'),
    '（已下载过，直接使用）': (' (already downloaded, reused)', '（ダウンロード済み、そのまま使用）'),
    '{value0}：{value1}': ('{value0}: {value1}', '{value0}：{value1}'),
    '沿用、不下载：{value0}': ('Kept, not downloaded: {value0}', 'そのまま使用（ダウンロードなし）：{value0}'),
    '需要用完整安装包更新（{value0}）。': (
        'This update needs the full installer ({value0}).', 'この更新には完全なインストーラーが必要です（{value0}）。'),
    '原因：{value0}': ('Reason: {value0}', '理由：{value0}'),
    '安装包会保留设置、词库、工程、模型和运行环境，覆盖安装即可，不要先卸载。': (
        'The installer keeps settings, glossaries, projects, models and runtime environments. '
        'Install over the current version; do not uninstall first.',
        'インストーラーは設定・用語集・プロジェクト・モデル・実行環境を保持します。'
        'アンインストールせずにそのまま上書きインストールしてください。'),
    '运行环境：{value0} 的需求有变化，用到时程序会提示补齐。': (
        'Runtime environments: requirements of {value0} changed; you will be asked to complete them when needed.',
        '実行環境：{value0} の要件が変わりました。使うときに補完を案内します。'),
    '运行环境：沿用，不需要重新下载。': ('Runtime environments: kept, nothing to download.', '実行環境：そのまま使用、再ダウンロード不要。'),
    '模型：{value0} 有新版本，只有用到该模型时才需要下载。': (
        'Models: {value0} has a new revision; it downloads only when you use that model.',
        'モデル：{value0} に新しい版があります。そのモデルを使うときだけダウンロードします。'),
    '模型：沿用，不需要重新下载。': ('Models: kept, nothing to download.', 'モデル：そのまま使用、再ダウンロード不要。'),
    '打开发布页': ('Open release page', 'リリースページを開く'),
    '稍后': ('Later', 'あとで'),
    '下载并准备更新': ('Download and prepare', 'ダウンロードして準備'),
    '下载安装包': ('Download installer', 'インストーラーをダウンロード'),
    '正在下载更新': ('Downloading update', '更新をダウンロード中'),
    '要取消这次更新下载吗？已下载的部分会保留，下次继续。': (
        'Cancel this download? What was downloaded is kept and resumes next time.',
        'ダウンロードを中止しますか？ダウンロード済みの部分は保持され、次回続きから再開します。'),
    '检查更新失败': ('Update check failed', '更新の確認に失敗しました'),
    '暂时无法取得更新信息，程序可以照常使用。': (
        'Update information is not available right now. 2ByteASR keeps working as usual.',
        '更新情報を取得できませんでした。2ByteASR はそのまま使えます。'),
    '{value0}\n\n可稍后重试，或打开发布页手动下载。': (
        '{value0}\n\nTry again later, or open the release page to download manually.',
        '{value0}\n\nあとで再試行するか、リリースページから手動でダウンロードしてください。'),
    '关闭': ('Close', '閉じる'),
    '已经是最新版': ('Up to date', '最新版です'),
    '当前版本 {value0}，发布版 {value1}。': ('Installed {value0}, latest release {value1}.', '現在 {value0}、最新リリース {value1}。'),
    '准备下载更新…': ('Preparing update download…', '更新のダウンロードを準備中…'),
    '下载更新 {percent}%': ('Downloading update {percent}%', '更新をダウンロード中 {percent}%'),
    '已下载 {value0:.1f} MB': ('Downloaded {value0:.1f} MB', '{value0:.1f} MB ダウンロード済み'),
    '更新下载失败': ('Update download failed', '更新のダウンロードに失敗しました'),
    '更新未修改任何程序文件。可稍后重试或直接覆盖安装新版。\n\n{value0}': (
        'No program file was changed. Try again later or install the new version over this one.\n\n{value0}',
        'プログラムファイルは変更されていません。あとで再試行するか、新しいバージョンを上書きインストールしてください。\n\n{value0}'),
    '更新已准备好': ('Update ready', '更新の準備ができました'),
    '兔白字幕 {value0} 已下载并校验完成（本次下载 {value1}）。\n\n需要退出程序才能完成更新：'
    '退出前会提示保存未保存的工程，更新完成后自动重新打开。设置、词库、工程、模型和运行环境都会保留。'
    '\n\n现在退出并更新吗？': (
        '2ByteASR {value0} is downloaded and verified ({value1} downloaded).\n\n'
        'The program must quit to finish: you will be asked to save unsaved projects first, and it reopens afterwards. '
        'Settings, glossaries, projects, models and runtime environments are kept.\n\nQuit and update now?',
        '2ByteASR {value0} のダウンロードと検証が完了しました（今回 {value1}）。\n\n'
        '更新を完了するにはプログラムを終了します。未保存のプロジェクトは終了前に保存を確認し、更新後に自動で再起動します。'
        '設定・用語集・プロジェクト・モデル・実行環境は保持されます。\n\n今すぐ終了して更新しますか？'),
    '字幕识别正在进行': ('Subtitle recognition is running', '字幕認識を実行中です'),
    '视频导出正在进行': ('A video export is running', '動画の書き出しを実行中です'),
    '模型下载或环境准备正在进行': ('A model download or environment setup is running', 'モデルのダウンロードまたは環境の準備を実行中です'),
    '后台任务正在进行': ('A background task is running', 'バックグラウンドタスクを実行中です'),
    '暂时不能更新': ('Cannot update right now', '今は更新できません'),
    '{value0}。请等它完成后再点“重启以完成更新”；更新已保留，不会重复下载。': (
        '{value0}. Wait until it finishes, then click "Restart to finish update". The update is kept and will not be downloaded again.',
        '{value0}。完了してから「再起動して更新を完了」を押してください。更新は保持され、再ダウンロードはしません。'),
    '当前版本 {value0} · 检查 GitHub Release': ('Installed {value0} · check GitHub Releases', '現在 {value0} · GitHub Release を確認'),
    # component labels
    '主程序': ('Main program', 'メインプログラム'),
    '程序运行库': ('Program runtime libraries', 'プログラム実行ライブラリ'),
    '界面字体': ('Interface fonts', 'UI フォント'),
    '高级字幕渲染器': ('Advanced subtitle renderer', '高度な字幕レンダラー'),
    '媒体工具': ('Media tools', 'メディアツール'),
    '环境安装包缓存': ('Environment package cache', '環境インストール用パッケージ'),
    '许可证与第三方材料': ('Licenses and third-party materials', 'ライセンスとサードパーティ資料'),
}
