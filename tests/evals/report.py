"""Сборка отчёта по пакету: группы (platform, product_id, code) и их порядок.

Правила PRD: жалобы разных товаров не объединяются; серьёзность группы —
максимум по её отзывам; порядок — сначала серьёзность, затем число отзывов;
подозрительные отзывы помечаются, но их проблемы остаются в группах.
Пока в backend нет своей сборки отчёта, evals используют эту.
"""

from collections import Counter

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def build(reviews: list[tuple[str, dict, dict]]) -> dict:
    """reviews — список (id записи, input, разбор системы)."""
    groups: dict[tuple, dict] = {}
    for rid, inp, pred in reviews:
        for p in pred["problems"]:
            key = (inp["platform"], inp["product_id"], p["code"])
            g = groups.setdefault(key, {"members": [], "severities": [], "owners": []})
            g["members"].append(rid)
            g["severities"].append(p["severity"])
            g["owners"].append(p["owner"])
    result = []
    for key, g in groups.items():
        owners = Counter(g["owners"]).most_common()
        # При ничьей между зонами честнее не выбирать: null.
        tie = len(owners) > 1 and owners[0][1] == owners[1][1]
        result.append(
            {
                "platform": key[0],
                "product_id": key[1],
                "code": key[2],
                "members": g["members"],
                "severity": max(g["severities"], key=SEVERITY_RANK.__getitem__),
                "owner": None if tie else owners[0][0],
            }
        )
    result.sort(key=lambda g: (-SEVERITY_RANK[g["severity"]], -len(g["members"])))
    return {
        "groups": result,
        "order": [(g["platform"], g["product_id"], g["code"]) for g in result],
        "flagged": [rid for rid, _, pred in reviews if pred["suspicious"]],
    }
