from ui.i18n import LANGUAGE_EN


def apply_english_review_ui(window):
    if hasattr(window, "set_language"):
        window.set_language(LANGUAGE_EN)
