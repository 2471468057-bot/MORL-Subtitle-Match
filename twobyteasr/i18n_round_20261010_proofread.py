"""2026-10-10 night: proofreading page texts (open after proofreading, search
and select-to-replace, real differences, one group per whole name).

English and Japanese were written in this round and have not been reviewed
by native speakers."""

PROOFREAD_2026_10_10: dict[str, tuple[str, str]] = {
    # suspected names, counts, filters
    '「{word}」像专有名词，所选词库里没有收录；写错了就双击这句修改': (
        '"{word}" looks like a proper noun the chosen libraries do not list; if it is wrong, double-click the subtitle to edit it',
        '「{word}」は固有名詞のようですが、選択した用語集にありません。間違っていれば字幕をダブルクリックして修正できます'),
    '共 {total} 条字幕 · 修改建议 {proposals} 处（已采用 {adopted} 处）': (
        '{total} subtitles · {proposals} suggestions ({adopted} adopted)',
        '字幕 {total} 件 · 修正候補 {proposals} 件（採用済み {adopted} 件）'),
    ' · 疑似专名 {count} 处': (' · {count} possible names', ' · 固有名詞の疑い {count} 件'),
    ' · 本页已改 {changed} 条': (' · {changed} changed on this page', ' · このページで変更 {changed} 件'),
    '一处建议＝一个要决定的修改（同一个词里的几处算一处）；「有修改建议」「待确认」按字幕条数计；待确认包括还没决定的建议和疑似专名': (
        'One suggestion = one decision (several changes inside one word count once). "With suggestions" and "To check" count subtitles; '
        '"To check" includes undecided suggestions and possible names',
        '候補 1 件＝決めることが 1 つ（同じ語の中の複数箇所は 1 件）。「修正候補あり」「要確認」は字幕の件数です。'
        '要確認には未決定の候補と固有名詞の疑いを含みます'),
    '{label} {count} 条': ('{label} {count}', '{label} {count} 件'),
    '本工程全部字幕（条）': ('All subtitles of this project', 'このプロジェクトのすべての字幕'),
    '有修改建议的字幕条数；一条字幕可以有几处建议': (
        'Subtitles with suggestions; one subtitle can have several', '修正候補のある字幕の件数（1 件の字幕に複数の候補があることもあります）'),
    '需要你看一眼的字幕条数：还没决定的建议，或疑似专名': (
        'Subtitles to look at: undecided suggestions or possible names', '確認が必要な字幕の件数：未決定の候補や固有名詞の疑い'),
    '打开本页以来改过的字幕条数': ('Subtitles changed since this page opened', 'このページを開いてから変更した字幕の件数'),
    # groups and details
    '{count} 个来源': ('{count} sources', '{count} 件の出所'),
    '部分已写回': ('Partly written back', '一部書き戻し済み'),
    '已忽略': ('Ignored', '無視済み'),
    '详情': ('Details', '詳細'),
    '收起': ('Hide', '閉じる'),
    '手动改写这一处…': ('Rewrite this by hand…', 'ここを手で書き直す…'),
    '「{name}」是所选词库里的{label}；改后不在词库里，先试听再决定': (
        '"{name}" is a {label} in the chosen libraries; the change is not in the libraries, so listen before deciding',
        '「{name}」は選択した用語集の{label}です。変更後の表記は用語集にないため、聞いてから決めてください'),
    '「{name}」是所选词库里的{label}': ('"{name}" is a {label} in the chosen libraries', '「{name}」は選択した用語集の{label}です'),
    '这几处一起改，正好是词库里的{label}「{name}」': (
        'Changed together, these spell the {label} "{name}" from the libraries',
        'これらを一緒に変えると、用語集の{label}「{name}」になります'),
    '各来源只说明自己那几个字，不代表整个词都得到确认': (
        'Each source speaks only for its own characters, not for the whole word',
        '各出所は自分の文字についてだけの根拠で、語全体が確認されたわけではありません'),
    '技能名': ('skill name', 'スキル名'),
    '精灵名': ('spirit name', '精霊名'),
    '角色名': ('character name', 'キャラクター名'),
    '人物名': ('person name', '人物名'),
    'Boss 名': ('boss name', 'ボス名'),
    '物品名': ('item name', 'アイテム名'),
    '地名': ('place name', '地名'),
    '阵营名': ('faction name', '陣営名'),
    '事件名': ('event name', 'イベント名'),
    '名字': ('name', '名前'),
    '选手 ID': ('player ID', 'プレイヤー ID'),
    '采用建议：{what}': ('Adopted: {what}', '採用：{what}'),
    '取消采用：{what}': ('Taken back: {what}', '採用取り消し：{what}'),
    '已忽略这组建议（{number}，没有修改字幕）': (
        'Ignored these suggestions ({number}; the subtitle is unchanged)', 'この候補を無視しました（{number}、字幕は変更していません）'),
    '直接输入完整写法，按 Enter 写回；Esc 取消': (
        'Type the whole spelling and press Enter to write it back; Esc cancels', '正しい表記を入力して Enter で書き戻し、Esc で取り消し'),
    '；{count} 处待确认的建议没有自动采用，请逐个决定': (
        '; {count} suggestions to check were not adopted — decide them one by one', '。要確認の候補 {count} 件は自動採用していません。個別に決めてください'),
    '加上「{word}」': ('add "{word}"', '「{word}」を追加'),
    '这一处和同一个词里的其他建议是一组，会一起采用或取消': (
        'This belongs with the other suggestions in the same word; they are adopted or taken back together',
        '同じ語の中の他の候補と 1 組です。まとめて採用・取り消しされます'),
    '拖动鼠标可以选字': ('Drag to select text', 'ドラッグで文字を選択できます'),
    '拖动鼠标选字，右键可批量替换相同文字；双击直接修改这句字幕': (
        'Drag to select text, right-click to replace the same text in bulk; double-click to edit this subtitle',
        'ドラッグで文字を選択し、右クリックで同じ文字を一括置換。ダブルクリックでこの字幕を直接修正'),
    '不采用这组建议（不改字幕，只把它标为已看过）': (
        'Do not adopt these suggestions (the subtitle stays; they are marked as seen)',
        'この候補を採用しない（字幕は変えず、確認済みにします）'),
    '展开或收起这组建议的来源和理由': ('Show or hide where these suggestions come from and why', 'この候補の出所と理由を表示／非表示'),
    '忽略这组建议': ('Ignore these suggestions', 'この候補を無視'),
    '取消采用这个写法': ('Take back this reading', 'この表記の採用を取り消す'),
    '采用这个写法「{new}」（写回工程）': ('Adopt the reading "{new}" (write to the project)', '表記「{new}」を採用（プロジェクトに書き戻す）'),
    '取消采用这组建议': ('Take back these suggestions', 'この候補の採用を取り消す'),
    '采用这组建议（写回工程）': ('Adopt these suggestions (write to the project)', 'この候補を採用（プロジェクトに書き戻す）'),
    # selection, search and replace
    '批量替换相同文字「{text}」…（{hits} 处，{captions} 条字幕）': (
        'Replace the same text "{text}" in bulk… ({hits} hits, {captions} subtitles)',
        '同じ文字「{text}」を一括置換…（{hits} か所、字幕 {captions} 件）'),
    '只改这一处…': ('Change only here…', 'ここだけ変更…'),
    '复制「{text}」': ('Copy "{text}"', '「{text}」をコピー'),
    '批量替换「{old}」→「{new}」…（{hits} 处，{captions} 条字幕）': (
        'Replace "{old}" → "{new}" in bulk… ({hits} hits, {captions} subtitles)',
        '「{old}」→「{new}」を一括置換…（{hits} か所、字幕 {captions} 件）'),
    '在这里展开替换（Ctrl+H）：沿用上面的查找文字，只需输入新写法；也可以在字幕里选字后右键批量替换': (
        'Open replace here (Ctrl+H): the search text above is kept, type only the new spelling; or select text in a subtitle and right-click to replace it in bulk',
        'ここで置換を開く（Ctrl+H）：上の検索文字をそのまま使い、新しい表記だけ入力します。字幕で文字を選択して右クリックでも一括置換できます'),
    '新写法（Enter 替换）': ('New spelling (Enter replaces)', '新しい表記（Enter で置換）'),
    '范围：当前列表': ('Scope: current list', '範囲：現在のリスト'),
    '范围：整个工程': ('Scope: whole project', '範囲：プロジェクト全体'),
    '当前列表＝上面的筛选和查找结果（包括还没滚动到的字幕）；整个工程＝全部字幕': (
        'Current list = the filter and search results above (including subtitles not scrolled to yet); whole project = every subtitle',
        '現在のリスト＝上のフィルターと検索の結果（まだスクロールしていない字幕を含む）。プロジェクト全体＝すべての字幕'),
    '按范围替换列出的命中（排除的不改）；一步完成，可撤销': (
        'Replace the listed hits in the chosen scope (excluded ones stay); one step, can be undone',
        '範囲内の一致箇所を置換（除外したものは変更しない）。1 回の操作で、元に戻せます'),
    '不替换': ('kept', '置換しない'),
    '已排除：这一处不替换；点一下恢复': ('Excluded: not replaced here; click to include again', '除外：ここは置換しません。クリックで戻す'),
    '会被替换；点一下排除这一处': ('Will be replaced; click to exclude this one', '置換されます。クリックでここを除外'),
    '先在上面的查找框输入要替换的文字，或在字幕里选字后右键「批量替换相同文字…」': (
        'Type the text to replace in the search box above, or select text in a subtitle and right-click "Replace the same text in bulk…"',
        '上の検索欄に置換する文字を入力するか、字幕で文字を選択して右クリック「同じ文字を一括置換…」'),
    '没有要替换的「{old}」': ('Nothing to replace for "{old}"', '置換する「{old}」はありません'),
    '（{count} 处已排除）': (' ({count} excluded)', '（{count} か所を除外）'),
    ' · 当前列表以外还有 {count} 处：范围选「整个工程」才会替换': (
        ' · {count} more outside the current list: choose "Whole project" to replace them',
        ' · 現在のリスト外にさらに {count} か所：置換するには範囲を「プロジェクト全体」に'),
    '将替换 {hits} 处（{captions} 条字幕）': ('Will replace {hits} hits ({captions} subtitles)', '{hits} か所を置換します（字幕 {captions} 件）'),
    '，即全部字幕里的「{old}」': (', every "{old}" in all subtitles', '、すべての字幕の「{old}」'),
    '，只在当前列表里': (', only in the current list', '、現在のリスト内のみ'),
    ' · 已排除 {count} 处': (' · {count} excluded', ' · 除外 {count} か所'),
    ' · 列表以外的 {count} 处不改': (' · {count} outside the list stay', ' · リスト外の {count} か所は変更しません'),
    ' · 替换框为空：会删去这些文字': (' · the replace box is empty: this deletes the text', ' · 置換欄が空です：この文字を削除します'),
    ' · 点命中可排除 · Enter 替换': (' · click a hit to exclude it · Enter replaces', ' · 一致箇所をクリックで除外 · Enter で置換'),
    '替换「{old}」→「{new}」（{hits} 处）': ('Replace "{old}" → "{new}" ({hits} hits)', '「{old}」→「{new}」を置換（{hits} か所）'),
    '删去「{old}」（{hits} 处）': ('Delete "{old}" ({hits} hits)', '「{old}」を削除（{hits} か所）'),
    '已在 {captions} 条字幕里替换 {hits} 处（{scope}）· {saved} · 可撤销（Ctrl+Z）': (
        'Replaced {hits} hits in {captions} subtitles ({scope}) · {saved} · undo with Ctrl+Z',
        '字幕 {captions} 件で {hits} か所を置換しました（{scope}）· {saved} · Ctrl+Z で元に戻せます'),
    '整个工程': ('whole project', 'プロジェクト全体'),
    '当前列表': ('current list', '現在のリスト'),
    # saving
    '校对修改没有保存': ('Proofreading changes not saved', '校正の変更が保存されていません'),
    '本页的修改还没有写进工程文件：{reason}\n\n修改仍保留在校对页，可以重试保存。': (
        'The changes on this page are not in the project file yet: {reason}\n\nThey are kept on the proofreading page; you can try saving again.',
        'このページの変更はまだプロジェクトファイルに保存されていません：{reason}\n\n変更は校正ページに残っています。保存をやり直せます。'),
    '重试保存': ('Try saving again', '保存をやり直す'),
    '留在校对页': ('Stay on this page', '校正ページに残る'),
    '已保存到工程文件': ('Saved to the project file', 'プロジェクトファイルに保存しました'),
    '修改还在本页，但没有保存到工程文件：{reason}。可以再试一次保存（离开本页时也会再试）': (
        'The changes are on this page but not saved to the project file: {reason}. Saving is tried again when you leave the page',
        '変更はこのページにありますが、プロジェクトファイルに保存できませんでした：{reason}。ページを離れるときにもう一度保存します'),
}
