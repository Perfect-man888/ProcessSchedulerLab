from app.data.experiment_profiles import EXPERIMENT_PROFILES
from app.services.experiment_service import EXPERIMENT_PRESETS


def test_every_dataset_dropdown_entry_has_a_complete_experiment_profile():
    dropdown_keys = {"current", *(preset.key for preset in EXPERIMENT_PRESETS)}

    assert set(EXPERIMENT_PROFILES) == dropdown_keys
    for key in dropdown_keys:
        profile = EXPERIMENT_PROFILES[key]
        assert profile.purpose.strip()
        assert profile.recommended_algorithms
        assert profile.metrics
        assert profile.report_suggestion.strip()
