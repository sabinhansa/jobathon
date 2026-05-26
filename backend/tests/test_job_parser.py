from app.services.job_parser import deterministic_extract


def test_deterministic_extract_ignores_employer_responsibilities():
    job = """
About the job

Our responsibilities
Update you on the progress of our recruitment process.
Provide the tools and resources to help you do your best.

Your responsibilities
Contribute to data, ML, crawling, infra, or delivery projects based on team priorities.
Design and ship production-grade components that integrate into live systems.
Investigate failures, trace root causes, and fix them at the source.

What we expect from you in return
Strong problem-solving and critical thinking.
Comfort with uncertainty, paired with structured execution.
"""
    structured = deterministic_extract(job)

    assert "Update you on the progress of our recruitment process." not in structured.responsibilities
    assert structured.responsibilities == [
        "Contribute to data, ML, crawling, infra, or delivery projects based on team priorities.",
        "Design and ship production-grade components that integrate into live systems.",
        "Investigate failures, trace root causes, and fix them at the source.",
    ]
    assert "Strong problem-solving and critical thinking." in structured.hard_requirements
