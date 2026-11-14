import re
from datetime import datetime, timezone
from typing import Sequence
from backend.app.models.entities import Keyword

DEFAULT_AGE_CURVE = [
    {"x": 0.0, "y": 5.0},    # Fresh (< 1 day)
    {"x": 2.0, "y": 3.0},    # 2 days old
    {"x": 7.0, "y": 0.0},    # 1 week old
    {"x": 14.0, "y": -3.0},  # 2 weeks old
    {"x": 30.0, "y": -8.0}   # 1 month old
]

DEFAULT_LENGTH_CURVE = [
    {"x": 0.0, "y": -5.0},     # Very short / stub
    {"x": 400.0, "y": 0.0},    # Short note
    {"x": 1200.0, "y": 4.0},   # Standard article
    {"x": 2500.0, "y": 6.0},   # Longform essay / deep dive
    {"x": 6000.0, "y": 3.0},   # Very long
    {"x": 12000.0, "y": -2.0}  # Massive / book length
]

def interpolate_curve(points: Sequence[dict], x: float) -> float:
    """Calculates piecewise linear interpolation for a curve given x."""
    if not points:
        return 0.0
    pts = []
    for p in points:
        try:
            px = float(p.x if hasattr(p, "x") else p.get("x", 0.0))
            py = float(p.y if hasattr(p, "y") else p.get("y", 0.0))
            pts.append((px, py))
        except (ValueError, TypeError):
            continue
    if not pts:
        return 0.0
    pts.sort(key=lambda item: item[0])

    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]

    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        if x1 <= x <= x2:
            dx = x2 - x1
            if dx == 0:
                return y1
            t = (x - x1) / dx
            return y1 + t * (y2 - y1)
    return 0.0

class KeywordScorer:
    @classmethod
    def evaluate(
        cls,
        title: str,
        text: str,
        keywords: Sequence[Keyword],
        source_weight: float = 0.0,
        published_at: datetime | None = None,
        word_count: int | None = None,
        age_curve: list[dict] | None = None,
        length_curve: list[dict] | None = None
    ) -> tuple[float, list[dict], bool, bool]:
        """
        Evaluates an article against active keyword rules, source weight,
        article age curve, and article length curve.
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

        # 3. Calculate weighted keyword scoring
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

        # 4. Source specific weight
        if source_weight != 0.0:
            sw_contrib = round(source_weight, 2)
            total_score += sw_contrib
            breakdown.append({
                "term": "Source Bias",
                "type": "source",
                "weight": sw_contrib,
                "title_hits": 0,
                "body_hits": 0,
                "contribution": sw_contrib
            })

        # 5. Article Age Curve Weight
        if age_curve:
            now_utc = datetime.now(timezone.utc)
            if published_at:
                pub_tz = published_at if published_at.tzinfo else published_at.replace(tzinfo=timezone.utc)
                age_days = max(0.0, (now_utc - pub_tz).total_seconds() / 86400.0)
            else:
                age_days = 0.0
            age_contrib = round(interpolate_curve(age_curve, age_days), 2)
            total_score += age_contrib
            breakdown.append({
                "term": f"Article Age ({age_days:.1f}d)",
                "type": "age",
                "weight": age_contrib,
                "title_hits": 0,
                "body_hits": 0,
                "contribution": age_contrib
            })

        # 6. Article Length Curve Weight
        if length_curve:
            words = word_count if word_count is not None else len(text.split())
            length_contrib = round(interpolate_curve(length_curve, float(words)), 2)
            total_score += length_contrib
            breakdown.append({
                "term": f"Article Length ({words}w)",
                "type": "length",
                "weight": length_contrib,
                "title_hits": 0,
                "body_hits": 0,
                "contribution": length_contrib
            })

        return max(0.0, round(total_score, 2)), breakdown, False, False

    @classmethod
    def score_article(
        cls,
        title: str,
        text: str,
        keywords: Sequence[Keyword],
        source_weight: float = 0.0,
        published_at: datetime | None = None,
        word_count: int | None = None,
        age_curve: list[dict] | None = None,
        length_curve: list[dict] | None = None
    ) -> float:
        score, _, _, _ = cls.evaluate(
            title=title,
            text=text,
            keywords=keywords,
            source_weight=source_weight,
            published_at=published_at,
            word_count=word_count,
            age_curve=age_curve,
            length_curve=length_curve
        )
        return score
