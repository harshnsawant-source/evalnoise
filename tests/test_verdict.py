from evalnoise.verdict import decide


def test_a_large_one_sided_effect_is_real():
    v = decide(delta_ab=0.12, gains=30, losses=4, n=240,
               critical=0.05, noise_band=0.042, p_value=0.0001)
    assert v.name == "REAL"
    assert v.exit_code == 0


def test_an_effect_below_the_noise_floor_is_inside_noise():
    v = decide(delta_ab=0.03, gains=34, losses=33, n=240,
               critical=0.051, noise_band=0.042, p_value=0.71)
    assert v.name == "INSIDE_NOISE"
    assert v.exit_code == 1
    assert "noise floor" in v.reason


def test_an_effect_above_the_floor_but_balanced_is_inside_noise():
    #: Clears both thresholds on size, but the flips are a coin toss.
    v = decide(delta_ab=0.09, gains=34, losses=33, n=240,
               critical=0.05, noise_band=0.042, p_value=0.71)
    assert v.name == "INSIDE_NOISE"
    assert "balanced" in v.reason


def test_too_few_items_is_inconclusive():
    v = decide(delta_ab=0.2, gains=5, losses=0, n=20,
               critical=0.05, noise_band=0.04, p_value=0.03)
    assert v.name == "INCONCLUSIVE"
    assert v.exit_code == 2
    assert "20" in v.reason


def test_too_few_changed_items_is_inconclusive():
    v = decide(delta_ab=0.02, gains=4, losses=1, n=240,
               critical=0.01, noise_band=0.005, p_value=0.2)
    assert v.name == "INCONCLUSIVE"


def test_nothing_changed_is_inside_noise_not_inconclusive():
    v = decide(delta_ab=0.0, gains=0, losses=0, n=240,
               critical=0.0, noise_band=0.04, p_value=1.0)
    assert v.name == "INSIDE_NOISE"
    assert "no item changed" in v.reason


def test_without_a_noise_floor_the_verdict_says_so():
    v = decide(delta_ab=0.12, gains=30, losses=4, n=240,
               critical=0.05, noise_band=None, p_value=0.0001)
    assert v.name == "UNCALIBRATED_REAL"
    assert "no A/A" in v.reason
    assert v.exit_code == 0
