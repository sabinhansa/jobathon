from app.schemas import RequirementMatch
from app.services.matching import compute_score, lexical_retrieve, lexical_status, normalize_match_result


def test_compute_score_uses_category_weights():
    score = compute_score(
        [
            RequirementMatch(
                requirement="Python",
                importance="required",
                status="strong_match",
                cv_evidence=["Python APIs"],
                explanation="visible",
            ),
            RequirementMatch(
                requirement="React",
                importance="technology",
                status="partial_match",
                cv_evidence=["React dashboard"],
                explanation="visible",
            ),
        ]
    )

    assert score == 92


def test_lexical_retrieve_and_status():
    evidence = lexical_retrieve(["Built FastAPI services with Docker", "Retail sales"], "FastAPI Docker", limit=1)
    assert evidence == ["Built FastAPI services with Docker"]
    assert lexical_status("FastAPI Docker", evidence) == "strong_match"
    assert lexical_status("Kubernetes", []) == "missing"


def test_normalize_match_result_coerces_llm_synonyms_and_fills_omissions():
    result = normalize_match_result(
        {
            "summary": "Deep comparison complete.",
            "confidence": "HIGH",
            "requirement_matches": [
                {
                    "requirement": "Python",
                    "importance": "hard_requirement",
                    "status": "strong",
                    "cv_evidence": ["Built Python APIs"],
                }
            ],
        },
        [("required", "Python"), ("technology", "Docker")],
        {"Docker": ["Built FastAPI services with Docker"]},
    )

    assert result["confidence"] == "high"
    assert result["requirement_matches"][0]["importance"] == "required"
    assert result["requirement_matches"][0]["status"] == "strong_match"
    assert result["requirement_matches"][1]["requirement"] == "Docker"
    assert "filled with local matching" in result["warnings"][0]
