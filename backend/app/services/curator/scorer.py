import re
from typing import Sequence
from backend.app.models.entities import Keyword

class KeywordScorer:
    @staticmethod
    def evaluate(title: str, text: str, keywords: Sequence[Keyword]) -> tuple[float, list[dict], bool, bool]:
        """
        Evaluates an article against active keyword rules.
        Returns:
            (final_score, breakdown_items, is_excluded_match, is_required_missing)
        """
        title_lower = title.lower()
        text_lower = text.lower()

        breakdown = []
        is_excluded_match = False
        is_required_missing = False

        # 1. Check exclusions
        for kw in keywords:
            if kw.is_excluded:
                pattern = r"\b" + re.escape(kw.term.lower()) + r"\b"
                title_hits = len(re.findall(pattern, title_lower))
                body_hits = len(re.findall(pattern, text_lower))
                total_hits = title_hits + body_hits
                if total_hits > 0:
                    is_excluded_match = True
                    breakdown.append({
                        "term": kw.term,
                        "type": "excluded",
                        "weight": kw.weight,
                        "title_hits": title_hits,
                        "body_hits": body_hits,
                        "contribution": -9999.0
                    })

        if is_excluded_match:
            return -1.0, breakdown, True, False

        # 2. Check required terms
        for kw in keywords:
            if kw.is_required:
                pattern = r"\b" + re.escape(kw.term.lower()) + r"\b"
                title_hits = len(re.findall(pattern, title_lower))
                body_hits = len(re.findall(pattern, text_lower))
                total_hits = title_hits + body_hits
                if total_hits == 0:
                    is_required_missing = True
                    breakdown.append({
                        "term": kw.term,
                        "type": "required_missing",
                        "weight": kw.weight,
                        "title_hits": 0,
                        "body_hits": 0,
                        "contribution": 0.0
                    })
                else:
                    breakdown.append({
                        "term": kw.term,
                        "type": "required_present",
                        "weight": kw.weight,
                        "title_hits": title_hits,
                        "body_hits": body_hits,
                        "contribution": 5.0
                    })

        if is_required_missing:
            return 0.0, breakdown, False, True

        # 3. Calculate weighted scoring
        total_score = 0.0
        for kw in keywords:
            if kw.is_required or kw.is_excluded:
                continue

            term = kw.term.lower()
            pattern = r"\b" + re.escape(term) + r"\b"
            title_hits = len(re.findall(pattern, title_lower))
            body_hits = len(re.findall(pattern, text_lower))

            if title_hits > 0 or body_hits > 0:
                # Title matches have 3x weight multiplier
                term_score = (title_hits * 3.0) + (body_hits * 1.0)
                contribution = round(term_score * kw.weight, 2)
                total_score += contribution
                breakdown.append({
                    "term": kw.term,
                    "type": "weighted",
                    "weight": kw.weight,
                    "title_hits": title_hits,
                    "body_hits": body_hits,
                    "contribution": contribution
                })

        return max(0.0, round(total_score, 2)), breakdown, False, False

    @classmethod
    def score_article(cls, title: str, text: str, keywords: Sequence[Keyword]) -> float:
        score, _, _, _ = cls.evaluate(title, text, keywords)
        return score
