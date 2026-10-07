from app.services.recommendation_service import generate_recommendations


def test_recommendations_are_derived_from_supplied_indicator_scores_and_sorted() -> None:
    indicators = {
        "income_stability": 72,
        "cashflow_stability": 42,
        "payment_discipline": 28,
        "savings_discipline": 48,
        "commitment_adherence": 60,
        "debt_burden": 35,
        "financial_stress": None,
        "financial_resilience": 55,
    }

    recommendations = generate_recommendations(indicators)

    assert [item["related_indicator"] for item in recommendations] == [
        "payment_discipline", "debt_burden", "cashflow_stability", "savings_discipline",
    ]
    assert [item["priority"] for item in recommendations] == ["High", "Medium", "Medium", "Low"]
    assert all(item["indicator_score"] == indicators[item["related_indicator"]] for item in recommendations)
    assert all("score" not in item["description"].lower() for item in recommendations)
    assert all("increase" not in item["reason"].lower() for item in recommendations)


def test_recommendations_ignore_unavailable_and_invalid_scores() -> None:
    assert generate_recommendations({
        "savings_discipline": None,
        "debt_burden": "48",
        "cashflow_stability": 101,
        "income_stability": True,
    }) == []


def test_recommendations_accept_indicator_detail_envelopes() -> None:
    recommendations = generate_recommendations({
        "financial_resilience": {"score": 51.7, "available": True},
    })

    assert len(recommendations) == 1
    assert recommendations[0]["related_indicator_label"] == "Financial Resilience"
    assert recommendations[0]["indicator_score"] == 51.7
    assert recommendations[0]["priority"] == "Low"


def test_estimated_assessment_can_recommend_missing_information_without_product_promises() -> None:
    recommendations = generate_recommendations(
        {"income_stability": 80, "payment_discipline": None},
        missing_sources=["credit", "insurance", "loans"],
    )
    assert [item["related_indicator"] for item in recommendations] == [
        "payment_discipline", "commitment_adherence", "debt_burden"
    ]
    assert all(item["indicator_score"] is None for item in recommendations[1:])
    assert all("+" not in item["description"] for item in recommendations)
    assert "confirm" in recommendations[-1]["title"]
