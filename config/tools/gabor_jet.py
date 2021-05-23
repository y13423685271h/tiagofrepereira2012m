#!/usr/bin/env python

import spkrectool
import bob
import math


# setup of the tool chain
tool = spkrectool.tools.GaborJetTool

# extract average model?
extract_averaged_model = False


# Gabor wavelet transform setup (if required by the Gabor jet similarity function)
GABOR_DIRECTIONS = 8
GABOR_SCALES = 5
GABOR_SIGMA = 2. * math.pi
GABOR_K_MAX = math.pi / 2.
GABOR_K_FAC = math.sqrt(.5)
GABOR_POW_OF_K = 0
GABOR_DC_FREE = True

gabor_wavelet_transform = bob.ip.GaborWaveletTransform(number_of_scales=GABOR_SCALES, number_of_angles=GABOR_DIRECTIONS, sigma=GABOR_SIGMA, k_max=GABOR_K_MAX, k_fac=GABOR_K_FAC, pow_of_k=GABOR_POW_OF_K, dc_free=GABOR_DC_FREE)

# Gabor jet comparison setup
similarity_type = bob.machine.gabor_jet_similarity_type.PHASE_DIFF_PLUS_CANBERRA
