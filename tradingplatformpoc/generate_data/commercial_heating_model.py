import numpy as np

# Binomial model coefficients
BM_INTERCEPT = 33.973192
BM_TEMP_1 = -2.012400
BM_TEMP_2 = -0.548222
BM_TEMP_3 = -0.880526
# Linear model coefficients
LM_INTERCEPT = 26.030581
LM_TEMP = -1.943567
LM_STD_DEV = 3.8660184261891652


def inv_logit(p):
    # Binomial GLM has the logit function as link
    return np.exp(p) / (1 + np.exp(p))


def probability_of_0_space_heating(temperature: float) -> float:
    # No observations of 0 energy where temperature is < 5.5. Therefore, to not get random 0s for much lower
    # temperatures than this, we'll artificially set heating to be non-zero whenever temperature < 5.
    # Also, no observations of >0 energy where temperature is > 18.7. Therefore we set heating to be 0 whenever
    # temperature >= 20.
    if temperature < 5:
        return 0
    elif temperature >= 20:
        return 1
    else:
        return 1 - inv_logit(BM_INTERCEPT
                             + BM_TEMP_1 * min(max(temperature, 5.5), 8)
                             + BM_TEMP_2 * min(max(temperature, 8), 12.5)
                             + BM_TEMP_3 * max(temperature, 12.5))


def space_heating_given_more_than_0(temperature: float) -> float:
    """
    If we have concluded that the heating energy use is > 0, then we use this model to predict how much it will be.
    """
    return max(0.0, LM_INTERCEPT + LM_TEMP * temperature)
