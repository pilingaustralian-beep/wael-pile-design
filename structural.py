# structural.py
import math
import numpy as np

def concrete_stress_check(Ac_mm2, Pw_kN, fcu):
    """Concrete stress check: fw = Pw/Ac <= 0.25 fcu"""
    fc = Pw_kN * 1000 / Ac_mm2  # N/mm²
    fa = 0.25 * fcu
    return fc, fa, fc <= fa

def get_concrete_modulus(fcu):
    """
    Ec calculation based on fcu (e.g. BS 8110 or ACI)
    Returns Ec in MPa (N/mm2)
    """
    # Ec = 4700 * sqrt(fcu) is common for ACI
    # Ec = 20 + 0.2*fcu is common for BS (GN/m2)
    ec_gn = 20 + 0.2 * fcu
    return ec_gn * 1000

def reinforcement_area(bar_dia, num):
    """Total steel area calculation"""
    return math.pi * (bar_dia**2) / 4 * num

def ultimate_axial_capacity(Ac_mm2, Asc_mm2, fcu, fy):
    """N = 0.4 fcu Ac + 0.75 fy Asc (BS 8110)"""
    N_newton = 0.4 * fcu * Ac_mm2 + 0.75 * fy * Asc_mm2
    return N_newton / 1000.0  # kN
def min_reinforcement_check(Ac_mm2, Asc_mm2, pile_dia_mm, axial_load_kN, moment_kNm, fcu, fy):
    rho_prov = (Asc_mm2 / Ac_mm2) * 100
    h = pile_dia_mm
    rho_code_min = 0.4
        
    # Refined Analytical interaction for circular section
    # M_res = 0.5 * As * fy * d_cage (approx)
    d_cage = 0.7 * h
    as_m = (abs(moment_kNm) * 10**6) / (0.87 * fy * d_cage)
    # Axial component: reduction of concrete capacity due to M
    as_n = ((axial_load_kN * 1000) - (0.4 * fcu * Ac_mm2)) / (0.75 * fy)
    
    rho_calc = (max(as_m, 0) + max(as_n, 0)) / Ac_mm2 * 100
    rho_req = max(rho_code_min, round(rho_calc, 2))
    return rho_prov, rho_req, rho_prov >= rho_req

def stirrup_spacing_check(pile_dia_mm, bar_dia_mm, stirrup_sp_mm):
    limit = min(12 * bar_dia_mm, pile_dia_mm, 300)
    return stirrup_sp_mm, limit, stirrup_sp_mm <= limit

def shear_check(Ac_mm2, V_max_kN, fcu, rho_prov_percent):
    """
    Checks if concrete shear stress is within allowable limits.
    Returns: Applied Stress, Allowable Stress, Pass/Fail
    """
    # Simplified code-based concrete shear strength (e.g. BS8110 approx)
    # Vc depends on fcu and reinforcement ratio
    vc_base = 0.45 * (fcu/25)**(1/3) # simplified base vc
    # Adjustment for reinforcement ratio (limited)
    k_rho = min((100 * rho_prov_percent / 100)**(1/3), 1.5)
    vc_allowable = vc_base * k_rho
    
    v_applied = (V_max_kN * 1000) / Ac_mm2 # N/mm2
    return v_applied, vc_allowable, v_applied <= vc_allowable

def crack_width_check(n_bars, bar_dia_mm, pile_dia_mm, cover_mm):
    """
    Checks the clear spacing between longitudinal bars.
    Codes usually limit this to 300mm or less to control cracking.
    """
    perimeter_cage = math.pi * (pile_dia_mm - 2 * cover_mm)
    spacing_center = perimeter_cage / n_bars
    clear_spacing = spacing_center - bar_dia_mm
    limit = 300 # standard limit for crack control
    return clear_spacing, limit, clear_spacing <= limit

def generate_interaction_diagram(D_mm, fcu, fy, n_bars, bar_dia_mm, cover_mm):
    """
    Generates points for N-M Interaction Diagram for a circular section.
    Returns (N_kN, M_kNm) points.
    """
    radius = D_mm / 2.0
    d_bar = radius - cover_mm - bar_dia_mm/2.0 # distance from center to bar center
    As_bar = math.pi * (bar_dia_mm**2) / 4.0
    
    # Angles of bars
    angles = [2 * math.pi * i / n_bars for i in range(n_bars)]
    
    # Points on the diagram
    n_points = 50
    N_list = []
    M_list = []
    
    # We iterate through the neutral axis depth x from 0 to D
    # We use a simplified rectangular stress block
    for x in np.linspace(0.01, D_mm * 1.2, n_points):
        # 1. Concrete force (Simplified integration for circular segment)
        # Using 0.45 fcu for the block depth 0.9x
        a = min(0.9 * x, D_mm)
        # Area of circular segment
        h = a
        r = radius
        if h <= r:
            theta = 2 * math.acos((r-h)/r)
            area_conc = (r**2 / 2) * (theta - math.sin(theta))
            y_conc = r - (4 * r * math.sin(theta/2)**3) / (3 * (theta - math.sin(theta)))
        else:
            h_inv = D_mm - h
            theta = 2 * math.acos((r-h_inv)/r)
            area_conc = math.pi * r**2 - (r**2 / 2) * (theta - math.sin(theta))
            # Rough CG for the remaining part
            y_conc = 0 # Approximated center for large compression
            
        Fc = 0.45 * fcu * area_conc
        Mc = Fc * (y_conc if h <= r else 0) # Moment about center

        # 2. Steel forces
        Fs_total = 0
        Ms_total = 0
        eps_cu = 0.0035 # standard max concrete strain
        
        for angle in angles:
            # depth of bar from top
            d_i = radius - d_bar * math.cos(angle)
            # strain in bar
            eps_i = eps_cu * (x - d_i) / x
            # stress (limited to fy/1.15)
            stress_i = np.clip(eps_i * 200000, -fy/1.15, fy/1.15)
            Fi = stress_i * As_bar
            Fs_total += Fi
            Ms_total += Fi * (radius - d_i) # Moment about center

        N_list.append((Fc + Fs_total) / 1000.0) # kN
        M_list.append(abs(Mc + Ms_total) / 1000000.0) # kNm

    return N_list, M_list
