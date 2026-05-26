from app.schemas import RequirementMatch
from app.services.matching import compute_score, lexical_retrieve, lexical_status


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

