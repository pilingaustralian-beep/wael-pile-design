# reese_matlock.py
import math
from inputs import PileHeadType

# Coefficients for Free-Head (Simplified representation)
FREE_HEAD_COEFFS = {
    0.0: (0.0, 1.0, 1.0, 0.0),
    0.5: (0.5, 0.97, 0.67, -0.18),
    1.0: (0.7, 0.77, 0.04, -0.65),
    1.5: (0.66, 0.45, -0.37, -0.45),
    2.0: (0.45, 0.22, -0.4, -0.37),
    2.5: (0.22, 0.05, -0.36, -0.22),
    3.0: (0.03, 0.02, -0.2, -0.07),
    3.5: (-0.03, -0.02, -0.1, -0.02),
    4.0: (-0.02, -0.05, 0.0, 0.0, 0.0, 0.0), # (Am, Bm, Av, Bv, As, Bs)
}
# As, Bs are shear coeffs
FREE_HEAD_COEFFS = {
    0.0: (0.0, 1.0, 1.0, 0.0, 1.0, 0.0),
    0.5: (0.5, 0.97, 0.67, -0.18, 0.99, -0.01),
    1.0: (0.7, 0.77, 0.04, -0.65, 0.94, -0.1),
    1.5: (0.66, 0.45, -0.37, -0.45, 0.78, -0.2),
    2.0: (0.45, 0.22, -0.4, -0.37, 0.54, -0.26),
    2.5: (0.22, 0.05, -0.36, -0.22, 0.3, -0.24),
    3.0: (0.03, 0.02, -0.2, -0.07, 0.12, -0.16),
    3.5: (-0.03, -0.02, -0.1, -0.02, 0.0, -0.08),
    4.0: (-0.02, -0.05, 0.0, 0.0, -0.04, -0.03),
}

# Coefficients for Fixed-Head
FIXED_HEAD_COEFFS = {
    0.0: (-0.93, 0.93, 1.0), # (Fm, Fy, Fs)
    0.5: (-0.45, 0.86, 0.98),
    1.0: (-0.04, 0.65, 0.82),
    1.5: (0.17, 0.39, 0.57),
    2.0: (0.25, 0.19, 0.32),
    2.5: (0.22, 0.07, 0.13),
    3.0: (0.14, 0.01, 0.02),
    3.5: (0.05, -0.02, -0.03),
    4.0: (0.01, -0.02, -0.04),
}

def stiffness_factor(E_MN_m2, I_m4, nh_MN_m3):
    """T = (E*I / nh)^(1/5)"""
    if nh_MN_m3 <= 0: return 1.0
    return (E_MN_m2 * I_m4 / nh_MN_m3) ** 0.2

def moment_and_distribution(pile, loads, options):
    D = pile.diameter / 1000.0
    I = math.pi * D**4 / 64.0
    T = stiffness_factor(options.E_concrete, I, options.nh)
    L = pile.pile_length
    
    H = loads.horizontal if loads.horizontal > 0 else options.assumed_horizontal_pct * loads.working_vertical
    Mt = loads.working_vertical * options.out_of_position * options.fos_structural

    results = []
    M_max = 0
    
    if options.head_type == PileHeadType.FIXED:
        for z, (Fm, Fy, Fs) in sorted(FIXED_HEAD_COEFFS.items()):
            depth = z * T
            if depth > L: continue
            M = Fm * H * T + Mt
            Y = Fy * H * T**3 / (options.E_concrete * 1000 * I) * 1000  # mm
            V = Fs * H
            M_max = max(M_max, abs(M))
            results.append((depth, M, Y, V))
    else:
        for z, (Am, Bm, Av, Bv, As, Bs) in sorted(FREE_HEAD_COEFFS.items()):
            depth = z * T
            if depth > L: continue
            M = Am * H * T + Bm * Mt
            Y = (Av * H * T**3 + Bv * Mt * T**2) / (options.E_concrete * 1000 * I) * 1000
            V = As * H + Bs * Mt / T
            M_max = max(M_max, abs(M))
            results.append((depth, M, Y, V))
            
    return T, L/T, results, M_max
