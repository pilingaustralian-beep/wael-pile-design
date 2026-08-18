# lateral_numerical.py
import numpy as np
import math
from inputs import PileGeometry, Loads, DesignOptions, SoilLayer, SoilType, PileHeadType


def solve_lateral_fdm(pile: PileGeometry, layers: list[SoilLayer], loads: Loads, options: DesignOptions, num_nodes=200):
    """
    Solves the lateral pile problem using the Finite Difference Method (FDM).
    Includes geometric stiffness (P-Delta effect):
    EI * d4y/dz4 + P * d2y/dz2 + Es(z) * y = 0
    """
    L = pile.pile_length
    dz = L / (num_nodes - 1)
    z_nodes = np.linspace(0, L, num_nodes)
    
    # Pile Properties
    D = pile.diameter / 1000.0
    I = (math.pi * D**4) / 64.0
    EI = options.E_concrete * 1000 * I  # kN.m2 (E in MN/m2)
    
    # Axial load for P-Delta (working load, compression positive)
    P_axial = max(loads.working_vertical, 0.0)  # kN
    
    # Soil Stiffness at each node - Improved model
    Es_nodes = np.zeros(num_nodes)
    for i, z in enumerate(z_nodes):
        depth_from_gl = z + abs(pile.cut_off_level - pile.ground_level)
        for layer in layers:
            if layer.depth_top <= depth_from_gl <= layer.depth_bottom:
                if layer.soil_type == SoilType.SAND:
                    # Linearly increasing modulus: Es = nh * z
                    nh_val = getattr(options, 'nh', 5.0)
                    Es_nodes[i] = nh_val * 1000.0 * max(depth_from_gl, 0.1)
                elif layer.soil_type == SoilType.CLAY:
                    # Constant modulus proportional to Cu
                    Es_nodes[i] = max(layer.Cu * 80.0, 500.0)
                else:  # ROCK
                    Es_nodes[i] = max(getattr(layer, 'Es', 200000.0) or 200000.0, 50000.0)
                break
        else:
            Es_nodes[i] = 5000.0
    
    # Applied loads
    H = loads.horizontal if loads.horizontal > 0 else options.assumed_horizontal_pct * loads.working_vertical
    Mt_ecc = loads.working_vertical * options.out_of_position * options.fos_structural
    M_head = loads.moment_at_head + Mt_ecc
    
    # Matrix assembly with Head Type support + P-Delta
    matrix = np.zeros((num_nodes, num_nodes))
    
    for i in range(num_nodes):
        if i == 0:
            # Shear condition at top
            matrix[i, 0:4] = [-1.0, 3.0, -3.0, 1.0]
        elif i == 1:
            if options.head_type == PileHeadType.FIXED:
                matrix[i, 0:2] = [-1.0, 1.0]
            else:
                matrix[i, 0:3] = [1.0, -2.0, 1.0]
        elif i == num_nodes - 2:
            matrix[i, num_nodes-3:num_nodes] = [1.0, -2.0, 1.0]
        elif i == num_nodes - 1:
            matrix[i, num_nodes-4:num_nodes] = [-1.0, 3.0, -3.0, 1.0]
        else:
            # Interior: EI y'''' + P y'' + Es y = 0
            p_term = (P_axial * dz**2) / EI if EI > 0 else 0.0
            es_term = (Es_nodes[i] * dz**4) / EI if EI > 0 else 0.0
            
            matrix[i, i-2] = 1.0
            matrix[i, i-1] = -4.0 + p_term
            matrix[i, i]   = 6.0 - 2.0 * p_term + es_term
            matrix[i, i+1] = -4.0 + p_term
            matrix[i, i+2] = 1.0

    rhs = np.zeros(num_nodes)
    rhs[0] = H * (dz**3) / EI if EI > 0 else 0.0
    if options.head_type == PileHeadType.FREE:
        rhs[1] = M_head * (dz**2) / EI if EI > 0 else 0.0
    else:
        rhs[1] = 0.0
    
    try:
        y_sol = np.linalg.solve(matrix, rhs)
    except np.linalg.LinAlgError:
        y_sol = np.zeros(num_nodes)
    
    # Moments and Shear
    moments = np.zeros(num_nodes)
    shears = np.zeros(num_nodes)
    
    for i in range(1, num_nodes - 1):
        moments[i] = -EI * (y_sol[i+1] - 2*y_sol[i] + y_sol[i-1]) / (dz**2)
    
    for i in range(2, num_nodes - 2):
        shears[i] = -EI * (y_sol[i+2] - 2*y_sol[i+1] + 2*y_sol[i-1] - y_sol[i-2]) / (2 * dz**3)
    
    shears[0] = H
    moments[0] = M_head if options.head_type == PileHeadType.FREE else moments[1]
    
    # Approximate additional P-Delta moment contribution
    for i in range(num_nodes):
        moments[i] += P_axial * y_sol[i]
    
    Mmax = np.max(np.abs(moments))
    y_mm = y_sol * 1000.0
    
    return z_nodes, y_mm, moments, shears, Mmax
