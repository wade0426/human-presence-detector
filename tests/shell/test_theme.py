from __future__ import annotations

from src.shell.theme import DARK_TOKENS, LIGHT_TOKENS, ColorScheme, build_qss, tokens_for

# ConnectionBadge / PresenceBadge 會用到的全部語意角色（嚴禁 import 舊 src.app 模組，
# 故以靜態清單守護：muted=IDLE/無人、info=連線中、success=已連線/有人、
# warning=重連/無訊號/影像異常、danger=錯誤）。
BADGE_ROLES = ("muted", "info", "success", "warning", "danger")


def test_tokens_for_returns_different_tokens() -> None:
    light = tokens_for(ColorScheme.LIGHT)
    dark = tokens_for(ColorScheme.DARK)

    assert light != dark
    assert light == LIGHT_TOKENS
    assert dark == DARK_TOKENS


def test_build_qss_contains_token_colors() -> None:
    qss = build_qss(LIGHT_TOKENS)

    assert LIGHT_TOKENS.bg in qss
    assert LIGHT_TOKENS.text_primary in qss
    assert LIGHT_TOKENS.accent in qss


def test_build_qss_contains_role_selectors() -> None:
    qss = build_qss(LIGHT_TOKENS)

    assert '[role="danger"]' in qss
    assert '[role="secondary"]' in qss


def test_build_qss_contains_checked_and_danger_button_rules() -> None:
    """M6: build_qss must include QPushButton:checked and QPushButton[role='danger']."""
    qss = build_qss(LIGHT_TOKENS)

    assert "QPushButton:checked" in qss
    assert 'QPushButton[role="danger"]' in qss


def test_build_qss_contains_muted_label_rule() -> None:
    """§4.16: muted role must have its own QSS rule (not reuse 11px secondary)."""
    qss = build_qss(LIGHT_TOKENS)

    assert 'QLabel[role="muted"]' in qss


def test_build_qss_covers_all_badge_roles() -> None:
    """§4.16 regression guard: every role used by PresenceBadge / ConnectionBadge
    must appear as a selector in the generated QSS."""
    qss = build_qss(LIGHT_TOKENS)

    for role in BADGE_ROLES:
        assert f'[role="{role}"]' in qss, f"no QSS rule for role={role!r}"
