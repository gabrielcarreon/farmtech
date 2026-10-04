from app.predictions.risk import overall_risk, risk_label


def test_risk_band_boundaries():
    assert risk_label(0) == "Very Low"
    assert risk_label(20) == "Very Low"
    assert risk_label(21) == "Low"
    assert risk_label(40) == "Low"
    assert risk_label(41) == "Moderate"
    assert risk_label(60) == "Moderate"
    assert risk_label(61) == "High"
    assert risk_label(80) == "High"
    assert risk_label(81) == "Very High"
    assert risk_label(100) == "Very High"


def test_overall_risk_is_the_mean_of_the_four_components():
    assert overall_risk(32, 58, 45, 51) == 47
