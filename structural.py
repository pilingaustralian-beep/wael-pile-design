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
    Ec calculation based on fcu (BS 8110 style)
    Returns Ec in MPa (N/mm2)
    """
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
        
    d_cage = 0.7 * h
    as_m = (abs(moment_kNm) * 10**6) / (0.87 * fy * d_cage) if fy > 0 and d_cage > 0 else 0
    as_n = ((axial_load_kN * 1000) - (0.4 * fcu * Ac_mm2)) / (0.75 * fy) if fy > 0 else 0
    
    rho_calc = (max(as_m, 0) + max(as_n, 0)) / Ac_mm2 * 100 if Ac_mm2 > 0 else 0
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
    vc_base = 0.45 * (fcu/25)**(1/3)
    k_rho = min((100 * rho_prov_percent / 100)**(1/3), 1.5) if rho_prov_percent > 0 else 0.5
    vc_allowable = vc_base * k_rho
    
    v_applied = (V_max_kN * 1000) / Ac_mm2 if Ac_mm2 > 0 else 0
    return v_applied, vc_allowable, v_applied <= vc_allowable


def crack_width_check(n_bars, bar_dia_mm, pile_dia_mm, cover_mm, moment_kNm=0.0, fcu=40.0, fy=460.0):
    """
    Improved crack control check (v2.3.2).
    1. Clear spacing between bars (code limit ~300 mm)
    2. Approximate crack width estimate based on BS 8110 / simplified approach.
    Returns: clear_spacing, spacing_limit, spacing_ok, estimated_w_mm, w_limit, crack_ok
    """
    # 1. Clear spacing check
    perimeter_cage = math.pi * (pile_dia_mm - 2 * cover_mm)
    spacing_center = perimeter_cage / max(n_bars, 1)
    clear_spacing = spacing_center - bar_dia_mm
    spacing_limit = 300.0
    spacing_ok = clear_spacing <= spacing_limit and clear_spacing > 0
    
    # 2. Approximate crack width (simplified)
    # w ≈ 3 * a_cr * ε_m   (very simplified BS-style)
    # a_cr ≈ distance from crack point to nearest bar
    a_cr = cover_mm + bar_dia_mm / 2.0
    # Approximate tensile strain under service moment
    # Use a conservative estimate of steel stress under service load
    # Assume service moment ≈ 0.7 * ultimate for estimation if moment given
    if moment_kNm > 0 and n_bars > 0 and bar_dia_mm > 0:
        As = n_bars * math.pi * (bar_dia_mm**2) / 4.0
        # lever arm approx 0.7*d
        d = pile_dia_mm - cover_mm - bar_dia_mm / 2.0
        z = 0.7 * d
        fs_service = (moment_kNm * 1e6) / (As * z) if As * z > 0 else 0  # N/mm2
        fs_service = min(fs_service, 0.8 * fy)  # cap
        eps_m = max(fs_service / 200000.0 - 0.0002, 0)  # simplified average strain
        w_est = 3.0 * a_cr * eps_m  # mm (very approximate)
    else:
        w_est = 0.0
    
    w_limit = 0.3  # mm typical for severe exposure / water retaining
    crack_ok = w_est <= w_limit if moment_kNm > 0 else True
    
    return clear_spacing, spacing_limit, spacing_ok, w_est, w_limit, crack_ok


def generate_interaction_diagram(D_mm, fcu, fy, n_bars, bar_dia_mm, cover_mm):
    """
    Generates points for N-M Interaction Diagram for a circular section.
    Improved accuracy (v2.3.2): better concrete segment CG and more points.
    Returns (N_kN, M_kNm) points.
    """
    radius = D_mm / 2.0
    d_bar = radius - cover_mm - bar_dia_mm / 2.0
    As_bar = math.pi * (bar_dia_mm**2) / 4.0
    
    angles = [2 * math.pi * i / n_bars for i in range(n_bars)]
    
    n_points = 80  # more points for smoother curve
    N_list = []
    M_list = []
    
    for x in np.linspace(0.01, D_mm * 1.25, n_points):
        # Concrete compression block (0.45 fcu, depth 0.9x)
        a = min(0.9 * x, D_mm)
        h = a
        r = radius
        
        if h <= 0:
            area_conc = 0.0
            y_conc = 0.0
        elif h >= 2 * r:
            area_conc = math.pi * r**2
            y_conc = 0.0
        elif h <= r:
            # Circular segment from top
            alpha = math.acos((r - h) / r)
            area_conc = r**2 * alpha - (r - h) * math.sqrt(2 * r * h - h**2)
            # CG of segment from center
            if area_conc > 1e-6:
                y_conc = (4 * r * (math.sin(alpha)**3)) / (3 * (2 * alpha - math.sin(2 * alpha))) - (r - h) * 0  
                # Distance from geometric center toward compression face
                y_conc = (r**2 * (math.sin(alpha)**3) * 4 / 3) / area_conc if area_conc > 0 else 0
                # y_conc measured from center, positive toward compression (top)
                y_from_top = r - y_conc
                y_conc = r - y_from_top  # keep consistent: from center
            else:
                y_conc = 0.0
        else:
            # More than half
            h_comp = 2 * r - h  # remaining tension side height
            alpha = math.acos((r - h_comp) / r) if h_comp < 2 * r else 0
            area_small = r**2 * alpha - (r - h_comp) * math.sqrt(max(2 * r * h_comp - h_comp**2, 0))
            area_conc = math.pi * r**2 - area_small
            y_conc = 0.0  # approximation for deep NA
            
        Fc = 0.45 * fcu * area_conc
        Mc = Fc * y_conc  # moment about center

        # Steel forces
        Fs_total = 0.0
        Ms_total = 0.0
        eps_cu = 0.0035
        Es = 200000.0  # MPa
        
        for angle in angles:
            # Position: top is angle=0 direction in our convention (cos)
            y_bar = d_bar * math.cos(angle)  # positive toward top
            d_i = radius - y_bar  # depth from top fiber
            
            if x > 1e-6:
                eps_i = eps_cu * (x - d_i) / x
            else:
                eps_i = 0.0
            
            stress_i = np.clip(eps_i * Es, -fy / 1.15, fy / 1.15)
            Fi = stress_i * As_bar
            Fs_total += Fi
            Ms_total += Fi * y_bar  # moment about center

        N_list.append((Fc + Fs_total) / 1000.0)  # kN
        M_list.append(abs(Mc + Ms_total) / 1e6)  # kNm

    return N_list, M_list
