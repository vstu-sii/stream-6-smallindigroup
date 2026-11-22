"""Baseline на правилах: регулярные выражения из лабы 1 в формате выхода v2.0.

Правила перенесены из experiments/lab1/run.py (rules-v0) без подстройки под
выборку test: это нижняя планка, с которой сравнивается модель, а не кандидат
в продукт. Серьёзность и зона ответственности — те же правила лабы 1, только
применены к каждой проблеме отдельно, как требует формат v2.0.
"""

import re

VERSION = "rules-v0"

RULES = {
    "delivery_delay": r"долго|задерж|шло\s+\d+",
    "not_delivered": r"не приш[её]л|не доставлен",
    "wrong_item": r"пришли два|не тот цвет|не ту модель",
    "defect_on_arrival": r"дырк|пятно|брак",
    "defect_after_use": r"разош[её]лся шов|сломал",
    "material_quality": r"катышк|сел[ао]\b|полинял|линяет",
    "size_mismatch": r"как XS|маломер|не соответствует размер",
    "description_mismatch": r"не та, что в описании|не соответствует описанию",
    "smell": r"воня|пахнет|запах",
    "safety_hazard": r"красн\w* пятн|аллерг|ожог",
}
HIGH = {"not_delivered", "defect_on_arrival", "material_quality"}
DELIVERY = {"delivery_delay", "not_delivered"}


def _severity(code: str) -> str:
    if code == "safety_hazard":
        return "critical"
    return "high" if code in HIGH else "medium"


def predict(review: dict) -> dict:
    """Разбор одного отзыва. На вход — только поле input записи, без эталона."""
    text = review["text"]
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    problems = []
    for code, pattern in RULES.items():
        if re.search(pattern, text, re.I):
            # Целое предложение исходного текста: цитата не выдумывается.
            evidence = next((s for s in sentences if re.search(pattern, s, re.I)), text)
            problems.append(
                {
                    "code": code,
                    "severity": _severity(code),
                    "owner": "marketplace" if code in DELIVERY else "seller",
                    "evidence": [evidence],
                }
            )
    if problems:
        sentiment = "negative"
    else:
        sentiment = "positive" if review["rating"] >= 4 else "neutral"
    return {
        "sentiment": sentiment,
        "problems": problems,
        "suspicious": text.count("!!!") >= 3,
        "has_instruction": bool(re.search(r"игнорируй|СИСТЕМА:", text, re.I)),
    }
