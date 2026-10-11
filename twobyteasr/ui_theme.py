"""Shared visual tokens for the 2ByteASR desktop interface.

The application has several independently rendered surfaces (main workbench,
model workshop and project-owned dialogs).  Keeping the palette, radii and
spacing here prevents those surfaces from drifting into separate themes.
"""

from __future__ import annotations

from dataclasses import dataclass


# Warm neutral surfaces -----------------------------------------------------
BACKGROUND = "#faf7f1"
BACKGROUND_ALT = "#f5f0e7"
SURFACE = "#fffefa"
SURFACE_MUTED = "#f7f3eb"
SURFACE_RAISED = "#ffffff"

# Borders -------------------------------------------------------------------
BORDER = "#e1d7c8"
BORDER_STRONG = "#d2c3ae"
BORDER_ACTIVE = "#9fbd9f"

# Content -------------------------------------------------------------------
INK = "#292a27"
INK_SOFT = "#494943"
MUTED = "#65645d"
MUTED_LIGHT = "#87837a"

# Accents -------------------------------------------------------------------
GREEN = "#4f8557"
GREEN_HOVER = "#43754b"
GREEN_PRESSED = "#396641"
GREEN_SOFT = "#e6efe2"
GREEN_SUBTLE = "#f1f6ee"
AMBER = "#bd8535"
AMBER_SOFT = "#f7edd9"
CORAL = "#b86555"

# Legacy stage names intentionally remain available to the progress UI, but
# use warm, low-saturation values instead of a blue/purple SaaS palette.
BLUE = "#728878"
PURPLE = "#8a7972"
MINT = "#dce9d8"
CHARCOAL = "#3d403a"

# Component geometry --------------------------------------------------------
RADIUS_SM = 8
RADIUS_CONTROL = 10
RADIUS_CARD = 16
RADIUS_SHELL = 18
RADIUS_DIALOG = 20

SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16
SPACE_5 = 20
SPACE_6 = 24
SPACE_7 = 32

CONTROL_HEIGHT = 40
HEADER_HEIGHT = 58


@dataclass(frozen=True)
class ThemeDefinition:
    """Application-wide semantic colors shared by every desktop surface."""

    key: str
    label: str
    labels: dict[str, str]
    app_background: str
    surface: str
    surface_elevated: str
    panel: str
    input_surface: str
    selected: str
    timeline: str
    media: str
    border: str
    border_strong: str
    text: str
    text_secondary: str
    text_muted: str
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_soft: str
    success: str
    warning: str
    warning_soft: str
    danger: str
    danger_soft: str
    shell: str
    shell_border: str
    focus: str
    disabled: str

    # Canonical semantic contract. The legacy names above remain available
    # while independently styled surfaces migrate to role-based tokens.
    @property
    def surface_muted(self) -> str:
        return self.panel

    @property
    def surface_input(self) -> str:
        return self.input_surface

    @property
    def text_on_accent(self) -> str:
        if self.key == "grape":
            return "#fff6f9"
        return "#ffffff" if self.key == "warm" else self.app_background

    @property
    def primary_role(self) -> str:
        return self.accent

    @property
    def secondary_role(self) -> str:
        return self.success

    @property
    def tertiary_role(self) -> str:
        return self.warning

    @property
    def timeline_background(self) -> str:
        return self.timeline

    @property
    def timeline_grid(self) -> str:
        return self.border_strong

    @property
    def timeline_playhead(self) -> str:
        return self.accent

    @property
    def control_background(self) -> str:
        return self.surface_elevated

    @property
    def control_hover(self) -> str:
        return self.selected

    @property
    def control_checked(self) -> str:
        return self.accent_soft

    @property
    def overlay_scrim(self) -> str:
        return {
            "warm": "rgba(41, 42, 39, 92)",
            "plum": "rgba(16, 15, 12, 160)",
            "lavender": "rgba(15, 14, 28, 150)",
            "slate": "rgba(9, 14, 16, 150)",
        }.get(self.key, "rgba(0, 0, 0, 140)")

    @property
    def drop_surface(self) -> str:
        return self.surface_elevated

    # 2026-10-07 semantic roles (properties only; TOKEN_FIELDS stays frozen).
    @property
    def accent_text(self) -> str:
        """Brand color readable as text/icon on the theme's surfaces."""
        return {
            "grape": "#ec8db0", "plum": "#a9d1a6", "lavender": "#dcc3f7", "slate": "#f2b896",
        }.get(self.key, self.accent)

    @property
    def info(self) -> str:
        return self.focus

    @property
    def success_soft(self) -> str:
        return blend_hex(self.surface, self.success, 0.16)

    @property
    def info_soft(self) -> str:
        return blend_hex(self.surface, self.focus, 0.16)

    @property
    def accent_tint(self) -> str:
        """Quiet brand wash for selected navigation (never a status)."""
        return blend_hex(self.surface, self.accent, 0.22)

    @property
    def hairline(self) -> str:
        """Divider between rows inside one surface; quieter than border."""
        return blend_hex(self.surface, self.border, 0.7)

    @property
    def role_colors(self) -> dict[str, str]:
        """Each theme's own companion palette (identity hues, never status).

        A colour card per theme around its brand: grape = sunset (dusty violet,
        apricot, mauve beside raspberry); warm = garden (cornflower, berry
        rose, mustard beside forest green); plum = orchard (mauve, dusty aqua,
        apricot beside sage); lavender = pastel (sky, peach, lemon beside
        lilac); slate = nordic (sea glass, dusty rose, soft lavender beside
        peach). Readiness is always a labelled chip, never these hues.
        """
        # Dark themes use dusty, lower-chroma tones: noticeable above the
        # surface but never louder than the brand action (user, 2026-10-08).
        return {
            "grape": {"primary": "#a48ad9", "timeline": "#d6957c", "review": "#c48cb4"},
            "warm": {"primary": "#4a6fc2", "timeline": "#b44d7a", "review": "#a8841c"},
            "plum": {"primary": "#bc8fb0", "timeline": "#86b3b4", "review": "#d0a07c"},
            "lavender": {"primary": "#93bbe4", "timeline": "#e3a68c", "review": "#d9c78f"},
            "slate": {"primary": "#86bfb7", "timeline": "#d3a2b9", "review": "#b5a7da"},
        }.get(self.key, {"primary": "#a48ad9", "timeline": "#d6957c", "review": "#c48cb4"})

    @property
    def role_wash(self) -> tuple[float, float, float]:
        """(rest, hover, border) blend amounts for identity-tinted cards."""
        return (0.12, 0.18, 0.5) if self.key == "warm" else (0.08, 0.13, 0.32)

    @property
    def zone_colors(self) -> dict[str, str]:
        """Low-saturation zone hues for the home blocks (user, 2026-10-08):
        Studio berry pink / purple-red, AI magenta rose-violet, content &
        terms grey-violet leaning cyan. Light themes use deeper tones."""
        if self.key == "warm":
            return {"studio": "#b25a80", "ai": "#9a5aa6", "content": "#557e8e"}
        return {"studio": "#cc7f9e", "ai": "#b585c4", "content": "#8aa5b8"}

    @property
    def on_vivid(self) -> str:
        """Icon color on a vivid role/status chip."""
        return "#ffffff" if self.key == "warm" else self.app_background

    @property
    def log_background(self) -> str:
        return self.media if self.key != "warm" else "#2b2d29"

    @property
    def log_text(self) -> str:
        return "#e8e3de" if self.key != "warm" else "#ecebe4"

    # P9A aliases. Not dataclass fields — TOKEN_FIELDS must stay frozen.
    @property
    def bg_app(self) -> str:
        return self.app_background

    @property
    def bg_panel(self) -> str:
        return self.panel

    @property
    def bg_card(self) -> str:
        return self.surface

    @property
    def bg_control(self) -> str:
        return self.surface_elevated

    @property
    def bg_control_hover(self) -> str:
        return self.selected

    @property
    def bg_control_pressed(self) -> str:
        return self.accent_soft

    @property
    def bg_popup(self) -> str:
        return self.surface_elevated

    @property
    def bg_modal(self) -> str:
        return self.surface

    @property
    def border_subtle(self) -> str:
        return self.border

    @property
    def border_default(self) -> str:
        return self.border_strong

    @property
    def border_focus(self) -> str:
        return self.accent

    @property
    def text_primary(self) -> str:
        return self.text

    @property
    def text_disabled(self) -> str:
        return self.disabled

    @property
    def accent_primary(self) -> str:
        return self.accent



THEMES = {
    # 2026-10-07 视觉体系：保留深葡萄紫气质，但层级改为偏中性的灰紫表面，
    # 品牌莓果色只承担主操作/选中指示；成功/警告/错误/信息使用可区分的色相，
    # 不再与品牌粉紫混在一起。
    "grape": ThemeDefinition(
        key="grape", label="Deep Grape / Burgundy",
        labels={"zh": "深葡萄紫 / 酒红", "en": "Deep Grape / Burgundy", "ja": "ディープグレープ / ワイン"},
        app_background="#19151c", surface="#252028", surface_elevated="#2f2935",
        panel="#1e1a22", input_surface="#1b171e", selected="#3a3241",
        timeline="#17131a", media="#0e0c10", border="#342d3a", border_strong="#4a4152",
        text="#f4eee9", text_secondary="#d0c6cd", text_muted="#a69ba6",
        accent="#b34470", accent_hover="#c1517d", accent_pressed="#9b3a61", accent_soft="#3a2231",
        success="#69cf9b", warning="#e9b65b", warning_soft="#3a2f1c",
        danger="#f3866b", danger_soft="#3d2425", shell="#141117", shell_border="#2a2430",
        focus="#86b4f7", disabled="#716779",
    ),
    "warm": ThemeDefinition(
        key="warm", label="Warm Cream / Green", labels={"zh": "暖奶油 / 绿色", "en": "Warm Cream / Green", "ja": "ウォームクリーム / グリーン"},
        app_background=BACKGROUND, surface=SURFACE, surface_elevated=SURFACE_RAISED,
        panel=SURFACE_MUTED, input_surface="#f3eee5", selected=GREEN_SOFT,
        timeline="#f5f0e7", media="#30332f", border=BORDER, border_strong=BORDER_STRONG,
        text=INK, text_secondary=INK_SOFT, text_muted=MUTED, accent=GREEN, accent_hover=GREEN_HOVER,
        accent_pressed=GREEN_PRESSED, accent_soft=GREEN_SUBTLE, success=GREEN,
        warning=AMBER, warning_soft=AMBER_SOFT, danger=CORAL, danger_soft="#f7e8e3", shell=SURFACE, shell_border=BORDER,
        focus=BORDER_ACTIVE, disabled="#99958d",
    ),
    # 五十二轮重设（用户："暗色被强行反色的感觉，不一定继续紫色"）：key 保留
    # "plum" 以兼容已保存的 settings，调色板本体改为与 warm 同源的暗色伙伴——
    # 暖夜炭底 + 奶油文字 + 低饱和绿功能色，surface 层级/border 对比按暗色
    # 独立设计，不再复用亮色体系的映射结果。
    "plum": ThemeDefinition(
        key="plum", label="Warm Night / Cream", labels={"zh": "暖夜炭 / 奶油绿", "en": "Warm Night / Cream", "ja": "ウォームナイト / クリーム"},
        app_background="#262420", surface="#302c26", surface_elevated="#3a352d",
        panel="#2b2722", input_surface="#201d19", selected="#3b4634",
        timeline="#242220", media="#161411", border="#46413a", border_strong="#5b5548",
        text="#f1ebdc", text_secondary="#d7cfba", text_muted="#a59d89", accent="#8fb98c", accent_hover="#a0c99d",
        accent_pressed="#7ba67a", accent_soft="#37402e", success="#8fb98c",
        warning="#c9a25e", warning_soft="#3f3828", danger="#c98573", danger_soft="#45322c", shell="#211f1b", shell_border="#46413a",
        focus="#9db892", disabled="#857e6e",
    ),
    "lavender": ThemeDefinition(
        key="lavender", label="Lavender Workspace", labels={"zh": "薰衣草工作区", "en": "Lavender Workspace", "ja": "ラベンダー・ワークスペース"},
        app_background="#29263a", surface="#49445f", surface_elevated="#5a5474",
        panel="#353149", input_surface="#514b6a", selected="#716b91",
        timeline="#302d43", media="#171725", border="#817aa4", border_strong="#9b93bf",
        text="#f9f7ff", text_secondary="#e4e0f0", text_muted="#d0cbe2", accent="#c19bea", accent_hover="#d0b2f4",
        accent_pressed="#a97fda", accent_soft="#625a80", success="#96d0b3",
        warning="#efc47d", warning_soft="#6a5e65", danger="#ee8a86", danger_soft="#6a5267", shell="#29263a", shell_border="#817aa4",
        focus="#9b93bf", disabled="#8d88a6",
    ),
    "slate": ThemeDefinition(
        key="slate", label="Slate / Editorial", labels={"zh": "岩灰 / 编辑风格", "en": "Slate / Editorial", "ja": "スレート / エディトリアル"},
        app_background="#20272b", surface="#303b41", surface_elevated="#3c4a51",
        panel="#273238", input_surface="#37454c", selected="#4c626c",
        timeline="#202a2f", media="#10171a", border="#5d747d", border_strong="#76909a",
        text="#f2f5f4", text_secondary="#ccd7d9", text_muted="#b8c6c8", accent="#e39a73", accent_hover="#f0ae8c",
        accent_pressed="#c77c58", accent_soft="#485b62", success="#8bc6a3",
        warning="#e5c37b", warning_soft="#54564d", danger="#ed8a7e", danger_soft="#564b4d", shell="#20272b", shell_border="#5d747d",
        focus="#76909a", disabled="#7d929b",
    ),
}

DEFAULT_THEME_KEY = "grape"


def blend_hex(base: str, overlay: str, amount: float) -> str:
    """Mix ``overlay`` into ``base`` (0..1) in sRGB; used for soft state washes."""
    def channels(value):
        raw = str(value or "").lstrip("#")
        if len(raw) != 6:
            return (0, 0, 0)
        return tuple(int(raw[index:index + 2], 16) for index in (0, 2, 4))
    first, second = channels(base), channels(overlay)
    amount = max(0.0, min(1.0, float(amount)))
    mixed = (round(a + (b - a) * amount) for a, b in zip(first, second))
    return "#" + "".join(f"{value:02x}" for value in mixed)


def hex_luminance(value: str) -> float:
    raw = str(value or "").lstrip("#")
    if len(raw) != 6:
        return 0.0
    red, green, blue = (int(raw[0:2], 16) / 255.0, int(raw[2:4], 16) / 255.0, int(raw[4:6], 16) / 255.0)

    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    return 0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue)


def contrast_ratio(first: str, second: str) -> float:
    left, right = hex_luminance(first), hex_luminance(second)
    lighter, darker = max(left, right), min(left, right)
    return (lighter + 0.05) / (darker + 0.05)


def theme_definition(key: str | None = None) -> ThemeDefinition:
    return THEMES.get(str(key or DEFAULT_THEME_KEY), THEMES[DEFAULT_THEME_KEY])


WORKSHOP_TOKENS = {
    "page": BACKGROUND,
    "sidebar": SURFACE_MUTED,
    "content": SURFACE,
    "surface": SURFACE_RAISED,
    "detail": "#faf5ea",
    "border": BORDER,
    "border_warm": BORDER_STRONG,
    "green": GREEN,
    "green_hover": GREEN_HOVER,
    "green_soft": GREEN_SOFT,
    "green_subtle": GREEN_SUBTLE,
    "ink": INK,
    "muted": MUTED,
    "icon": "#858177",
    "score_track": "#e8e2d8",
    "score_low": CORAL,
    "score_low_2": "#c77a6c",
    "score_mid": "#be914b",
    "score_high": "#64875b",
    "score_top": "#587e52",
}


def theme_display_label(theme: ThemeDefinition, language: str | None = None) -> str:
    """Localized theme name; the stable ``label`` stays as the English fallback."""
    if language is None:
        from .i18n import current_language

        language = current_language()
    return theme.labels.get(str(language), theme.label)
