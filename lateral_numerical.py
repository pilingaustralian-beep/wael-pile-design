# lateral_numerical.py
import numpy as np
import math
from inputs import PileGeometry, Loads, DesignOptions, SoilLayer, SoilType, PileHeadType

def solve_lateral_fdm(pile: PileGeometry, layers: list[SoilLayer], loads: Loads, options: DesignOptions, num_nodes=200):
    """
    Solves the lateral pile problem using the Finite Difference Method (FDM).
    EI * d4y/dz4 + Es(z) * y = 0
    """
    L = pile.pile_length
    dz = L / (num_nodes - 1)
    z_nodes = np.linspace(0, L, num_nodes)
    
    # Pile Properties
    D = pile.diameter / 1000.0
    I = (math.pi * D**4) / 64.0
    EI = options.E_concrete * 1000 * I # kN.m2 (since E is in MN/m2)
    
    # Soil Stiffness at each node (Es = nh * z)
    # We find which layer each node belongs to
    Es_nodes = np.zeros(num_nodes)
    for i, z in enumerate(z_nodes):
        depth_from_gl = z + abs(pile.cut_off_level - pile.ground_level)
        # Find layer
        for layer in layers:
            if layer.depth_top <= depth_from_gl <= layer.depth_bottom:
                if layer.soil_type == SoilType.SAND:
                    # nh increases with depth: Es = nh * depth_from_gl
                    # nh is typically in MN/m3, we need Es in kN/m2
                    Es_nodes[i] = layer.phi * 0.5 * depth_from_gl * options.nh # Simplified linear stiffness
                else:
                    # Clay: Constant or linear
                    Es_nodes[i] = layer.Cu * 0.2 * 100 # Simplified constant stiffness
                break
    
    # Boundary Conditions and Matrix Assembly
    # [K]{y} = {P}
    # For a node i, the FDM for EI*d4y/dz4 is:
    # (EI/dz4) * (y_{i-2} - 4y_{i-1} + 6y_{i} - 4y_{i+1} + y_{i+2}) + Es_i * y_i = 0
    
    K = np.zeros((num_nodes, num_nodes))
    P = np.zeros(num_nodes)
    
    C = EI / (dz**4)
    
    for i in range(2, num_nodes - 2):
        K[i, i-2] = C
        K[i, i-1] = -4 * C
        K[i, i]   = 6 * C + Es_nodes[i]
        K[i, i+1] = -4 * C
        K[i, i+2] = C

    # Applied Shear H and Moment M (including eccentricity)
    H = loads.horizontal if loads.horizontal > 0 else options.assumed_horizontal_pct * loads.working_vertical
    Mt_ecc = loads.working_vertical * options.out_of_position * options.fos_structural
    M_head = loads.moment_at_head + Mt_ecc
    
    # Node 0 (Shear BC): -EI * d3y/dz3 = H
    # d3y/dz3 = (y2 - 2y1 + 2y_{-1} - y_{-2}) / 2dz3
    # Node 1 (Moment BC): -EI * d2y/dz2 = M
    # d2y/dz2 = (y1 - 2y0 + y_{-1}) / dz2
    
    # We use ghost nodes or modify the first rows
    # Standard 4th order ODE with BCs
    # Simplified approach for top:
    K[0, 0] = 1 # We will force y0 in next steps
    K[1, 1] = 1
    
    # Matrix assembly with Head Type support
    matrix = np.zeros((num_nodes, num_nodes))
    for i in range(num_nodes):
        if i == 0:
            # Shear condition at top: -EI * d3y/dz3 = H
            matrix[i, 0:4] = [-1, 3, -3, 1] 
        elif i == 1:
            if options.head_type == PileHeadType.FIXED:
                # Slope = 0 at top: dy/dz = 0 => y1 = y0
                matrix[i, 0:2] = [-1, 1]
            else:
                # Moment condition at top: -EI * d2y/dz2 = M
                matrix[i, 0:3] = [1, -2, 1]
        elif i == num_nodes - 2:
            # Moment at bottom = 0
            matrix[i, num_nodes-3:num_nodes] = [1, -2, 1]
        elif i == num_nodes - 1:
            # Shear at bottom = 0
            matrix[i, num_nodes-4:num_nodes] = [-1, 3, -3, 1]
        else:
            matrix[i, i-2] = 1
            matrix[i, i-1] = -4
            matrix[i, i]   = 6 + (Es_nodes[i] * dz**4 / EI)
            matrix[i, i+1] = -4
            matrix[i, i+2] = 1

    rhs = np.zeros(num_nodes)
    rhs[0] = H * (dz**3) / EI
    rhs[1] = M_head * (dz**2) / EI if options.head_type == PileHeadType.FREE else 0.0
    
    try:
        y_sol = np.linalg.solve(matrix, rhs)
    except:
        y_sol = np.zeros(num_nodes)
    
    # Calculate Moments and Shear
    moments = np.zeros(num_nodes)
    shears = np.zeros(num_nodes)
    for i in range(1, num_nodes - 1):
        moments[i] = -EI * (y_sol[i+1] - 2*y_sol[i] + y_sol[i-1]) / (dz**2)
    
    for i in range(2, num_nodes - 2):
        # V = -EI * d3y/dz3
        shears[i] = -EI * (y_sol[i+2] - 2*y_sol[i+1] + 2*y_sol[i-1] - y_sol[i-2]) / (2 * dz**3)
    
    shears[0] = H
    moments[0] = M_head if options.head_type == PileHeadType.FREE else moments[1]
    
    Mmax = np.max(np.abs(moments))
    y_mm = y_sol * 1000.0
    
    return z_nodes, y_mm, moments, shears, Mmax
