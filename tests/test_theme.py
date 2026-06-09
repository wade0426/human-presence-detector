from __future__ import annotations

from src.ui.theme import DARK_TOKENS, LIGHT_TOKENS, ColorScheme, build_qss, tokens_for


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
