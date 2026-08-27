def get_recommendation(
    score,
    sector_confidence,
):
    if score >= 6:
        if sector_confidence == "Supported":
            return {
                "label": "High Confidence",
                "priority": 5,
                "reason":
                    "Maximum financial score with "
                    "supportive sector evidence.",
            }

        if sector_confidence == "Unconfirmed":
            return {
                "label":
                    "Strong / Needs Confirmation",
                "priority": 4,
                "reason":
                    "Maximum financial score, but "
                    "sector evidence is not yet "
                    "confirmed out-of-sample.",
            }

        if sector_confidence == "Mixed":
            return {
                "label":
                    "Strong / Mixed Sector",
                "priority": 3,
                "reason":
                    "Maximum financial score, but "
                    "sector history is inconsistent.",
            }

        if sector_confidence == "Caution":
            return {
                "label":
                    "Strong / Sector Caution",
                "priority": 2,
                "reason":
                    "Maximum financial score, but "
                    "recent sector evidence is weak.",
            }

        if sector_confidence == "Unsupported":
            return {
                "label":
                    "Strong / Sector Conflict",
                "priority": 2,
                "reason":
                    "Maximum financial score, but "
                    "historical sector evidence "
                    "does not support the signal.",
            }

        return {
            "label":
                "Strong / Limited Evidence",
            "priority": 3,
            "reason":
                "Maximum financial score, but "
                "there is not enough sector "
                "evidence yet.",
        }

    if score >= 4:
        if sector_confidence == "Supported":
            return {
                "label": "Strong Candidate",
                "priority": 4,
                "reason":
                    "Strong financial score with "
                    "supportive sector evidence.",
            }

        if sector_confidence == "Unconfirmed":
            return {
                "label":
                    "Strong / Needs Confirmation",
                "priority": 3,
                "reason":
                    "Strong financial score, but "
                    "sector evidence is not yet "
                    "confirmed out-of-sample.",
            }

        if sector_confidence == "Mixed":
            return {
                "label":
                    "Strong / Mixed Sector",
                "priority": 3,
                "reason":
                    "Strong financial score with "
                    "mixed historical sector results.",
            }

        if sector_confidence == "Caution":
            return {
                "label": "Cautious",
                "priority": 2,
                "reason":
                    "Strong financial score, but "
                    "recent sector evidence is "
                    "negative.",
            }

        if sector_confidence == "Unsupported":
            return {
                "label":
                    "Strong / Sector Conflict",
                "priority": 2,
                "reason":
                    "Strong company fundamentals, "
                    "but historical sector evidence "
                    "is unfavorable.",
            }

        return {
            "label":
                "Strong / Limited Evidence",
            "priority": 3,
            "reason":
                "Strong financial score, but "
                "sector evidence is limited.",
        }

    if score == 3:
        if sector_confidence in (
            "Supported",
            "Unconfirmed",
        ):
            return {
                "label": "Positive",
                "priority": 2,
                "reason":
                    "Positive financial evidence, "
                    "but below the strong-signal "
                    "threshold.",
            }

        return {
            "label":
                "Positive / Watch",
            "priority": 1,
            "reason":
                "Positive financial evidence, but "
                "sector evidence does not add "
                "confidence.",
        }

    if score == 2:
        return {
            "label": "Neutral",
            "priority": 1,
            "reason":
                "Some positive financial evidence, "
                "but not enough for a strong signal.",
        }

    return {
        "label": "Low Priority",
        "priority": 0,
        "reason":
            "Current financial evidence is weak.",
    }


def main():
    test_cases = [
        (
            6,
            "Supported",
        ),
        (
            6,
            "Unconfirmed",
        ),
        (
            6,
            "Unsupported",
        ),
        (
            4,
            "Mixed",
        ),
        (
            4,
            "Caution",
        ),
        (
            3,
            "Unconfirmed",
        ),
        (
            2,
            "No Evidence",
        ),
        (
            0,
            "Unsupported",
        ),
    ]

    print()
    print(
        "RECOMMENDATION ENGINE TEST"
    )

    print("=" * 100)

    print(
        f"{'Score':<8}"
        f"{'Sector Confidence':<20}"
        f"{'Recommendation':<32}"
        f"{'Priority':>10}"
    )

    print("-" * 100)

    for score, confidence in test_cases:
        result = get_recommendation(
            score,
            confidence,
        )

        print(
            f"{score:<8}"
            f"{confidence:<20}"
            f"{result['label']:<32}"
            f"{result['priority']:>10}"
        )

        print(
            f"  {result['reason']}"
        )


if __name__ == "__main__":
    main()