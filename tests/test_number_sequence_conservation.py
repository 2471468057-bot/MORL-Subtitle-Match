import subtitle_core


def test_adjacent_spoken_amounts_stay_chinese_and_are_never_added_together():
    assert subtitle_core.normalize_output_text("哎三万三万最后一本两万救一下") == (
        "哎三万三万最后一本两万救一下"
    )
    assert subtitle_core.normalize_output_text("又来个二十万十万") == "又来个二十万十万"
    assert subtitle_core.normalize_output_text(
        "第二本刮完赚二十二万十万九万九万十一万十万"
    ) == "第二本刮完赚二十二万十万九万九万十一万十万"


def test_single_compound_amount_avoids_arabic_chinese_hybrid():
    assert subtitle_core.normalize_output_text("三百二十万") == "三百二十万"
    assert subtitle_core.normalize_output_text("三亿五千万") == "三亿五千万"


def test_game_stats_use_arabic_digits_but_spoken_magnitudes_stay_chinese():
    assert subtitle_core.normalize_output_text("这1万多威力吗") == "这一万多威力吗"
    assert subtitle_core.normalize_output_text("这百分之1万有问题") == "这百分之一万有问题"
    assert subtitle_core.normalize_output_text("十六层毒") == "十六层毒"
    assert subtitle_core.normalize_output_text("威力加四十") == "威力加40"
    assert subtitle_core.normalize_output_text("回复十二生命值") == "回复12生命值"


def test_spoken_ten_nine_eight_countdown_uses_separate_arabic_digits():
    assert subtitle_core.normalize_output_text("十九八") == "10 9 8"
    assert subtitle_core.normalize_output_text("倒计时十九八开始") == "倒计时10 9 8开始"


def test_ten_second_boarding_term_uses_the_live_membership_character():
    assert subtitle_core.normalize_output_text("十秒内不上剑给你号刮完") == (
        "十秒内不上舰给你号刮完"
    )
