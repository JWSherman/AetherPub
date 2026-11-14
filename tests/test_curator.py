import pytest
from backend.app.services.curator.simhash import compute_simhash, hamming_distance, are_near_duplicates
from backend.app.services.curator.scorer import KeywordScorer
from backend.app.models.entities import Keyword

def test_simhash_identical_and_similar_texts():
    text1 = "Quantum computing relies on quantum bits or qubits to perform computations exponentially faster."
    text2 = "Quantum computing relies on quantum bits or qubits to perform calculations exponentially faster."
    text3 = "Baking sourdough bread requires flour, water, salt, wild yeast culture, and patience."

    h1 = compute_simhash(text1)
    h2 = compute_simhash(text2)
    h3 = compute_simhash(text3)

    assert isinstance(h1, str)
    assert len(h1) == 16
    assert hamming_distance(h1, h1) == 0

    dist_near = hamming_distance(h1, h2)
    dist_far = hamming_distance(h1, h3)

    assert dist_near < dist_far
    assert are_near_duplicates(h1, h2, max_distance=10) is True

def test_simhash_malformed_hashes_resilience():
    # Verify that non-hex or malformed hashes do not crash hamming_distance
    assert hamming_distance("abc123simhash0001", "0000000000000000") == 64
    assert are_near_duplicates("not_a_hex", "1234567890abcdef") is False
    assert hamming_distance("", "1234567890abcdef") == 64
    assert hamming_distance(None, "1234567890abcdef") == 64

def test_keyword_scorer_weighted_interest():
    kw1 = Keyword(term="rust", weight=1.5, is_required=False, is_excluded=False)
    kw2 = Keyword(term="performance", weight=2.0, is_required=False, is_excluded=False)
    keywords = [kw1, kw2]

    # Title match has 3x multiplier
    title = "Rust Performance Optimization Guide"
    body = "In this article we discuss rust memory safety and execution speed."

    score = KeywordScorer.score_article(title, body, keywords)
    # rust in title (1 * 3) + rust in body (1 * 1) = 4 * 1.5 = 6.0
    # performance in title (1 * 3) = 3 * 2.0 = 6.0
    # Total = 12.0
    assert score == 12.0

def test_keyword_scorer_exclusion():
    kw1 = Keyword(term="ai", weight=2.0, is_required=False, is_excluded=False)
    kw_exclude = Keyword(term="crypto", weight=1.0, is_required=False, is_excluded=True)
    keywords = [kw1, kw_exclude]

    title = "AI in Modern Finance and Crypto Trading"
    body = "Analyzing algorithmic trends."

    score = KeywordScorer.score_article(title, body, keywords)
    assert score == -1.0  # Discarded immediately due to 'crypto'

def test_keyword_scorer_required_missing():
    kw_req = Keyword(term="tutorial", weight=1.0, is_required=True, is_excluded=False)
    kw_opt = Keyword(term="python", weight=2.0, is_required=False, is_excluded=False)
    keywords = [kw_req, kw_opt]

    title = "Python 3.14 Features Overview"
    body = "Here is what is new in the latest release."

    # Missing 'tutorial'
    score = KeywordScorer.score_article(title, body, keywords)
    assert score == 0.0

def test_interpolate_curve():
    from backend.app.services.curator.scorer import interpolate_curve
    curve = [{"x": 0.0, "y": 10.0}, {"x": 10.0, "y": 0.0}]
    assert interpolate_curve(curve, -5.0) == 10.0
    assert interpolate_curve(curve, 0.0) == 10.0
    assert interpolate_curve(curve, 5.0) == 5.0
    assert interpolate_curve(curve, 10.0) == 0.0
    assert interpolate_curve(curve, 15.0) == 0.0

def test_keyword_scorer_source_and_curve_weights():
    from datetime import datetime, timezone, timedelta
    kw = Keyword(term="robotics", weight=2.0, is_required=False, is_excluded=False)
    keywords = [kw]

    title = "Robotics Revolution"
    body = "Advanced robotics are transforming factories."

    # Base score: robotics in title (3 * 2.0) + robotics in body (1 * 2.0) = 8.0
    # Add source weight: +3.0
    # Add age curve: 0d -> +5.0
    # Add length curve: 50w -> 0.0
    now = datetime.now(timezone.utc)
    age_curve = [{"x": 0.0, "y": 5.0}, {"x": 10.0, "y": 0.0}]
    length_curve = [{"x": 0.0, "y": 0.0}, {"x": 500.0, "y": 5.0}]

    score, breakdown, is_ex, is_req = KeywordScorer.evaluate(
        title=title,
        text=body,
        keywords=keywords,
        source_weight=3.0,
        published_at=now,
        word_count=50,
        age_curve=age_curve,
        length_curve=length_curve
    )
    assert is_ex is False
    assert is_req is False
    # 8.0 (keyword) + 3.0 (source) + 5.0 (age) + 0.5 (length: 50/500 * 5.0 = 0.5) = 16.5
    assert score == 16.5
    types = [b["type"] for b in breakdown]
    assert "weighted" in types
    assert "source" in types
    assert "age" in types
    assert "length" in types
