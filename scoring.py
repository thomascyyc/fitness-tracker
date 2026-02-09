"""Point calculation for fitness competition entries."""

# Scoring rates
CARDIO_PTS_PER_MIN = 1.0
LIGHT_PTS_PER_MIN = 0.5
STRENGTH_PTS_PER_REP = 1.0
FLEX_PTS_PER_MIN = 1.0


def calculate_points(cardio_mins, light_mins, strength_reps, flex_mins):
    """Calculate total points for a fitness entry.

    Returns total points (float).
    """
    return (
        cardio_mins * CARDIO_PTS_PER_MIN
        + light_mins * LIGHT_PTS_PER_MIN
        + strength_reps * STRENGTH_PTS_PER_REP
        + flex_mins * FLEX_PTS_PER_MIN
    )
