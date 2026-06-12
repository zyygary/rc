LANGUAGE_ZH = "zh"
LANGUAGE_EN = "en"


def normalize_language(language: str) -> str:
    return LANGUAGE_EN if language == LANGUAGE_EN else LANGUAGE_ZH


def tr(language: str, zh_text: str, en_text: str) -> str:
    return en_text if normalize_language(language) == LANGUAGE_EN else zh_text
