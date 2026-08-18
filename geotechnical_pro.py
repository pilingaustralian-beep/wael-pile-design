# geotechnical_pro.py
import math
from inputs import SoilType, RockMethod, SoilLayer, PileGeometry, Loads, DesignOptions
from utils import deg2rad


def calculate_layered_bearing(layers: list[SoilLayer], pile: PileGeometry, loads: Loads, options: DesignOptions):
    """
    Calculates bearing capacity by iterating through soil layers.
    Includes GWT effects and Critical Depth concept.
    Improved settlement calculation (v2.3).
    """
    # 1. Initialize variables
    total_Qs_comp = 0.0
    total_Qs_tens = 0.0
    Qb = 0.0
    segments_summary = []
    toe_note = "Toe bearing not calculated (check depths)"
    D_m = pile.diameter / 1000.0
    Ab = math.pi * D_m**2 / 4.0
    
    toe_depth = abs(pile.toe_level - pile.ground_level)
    pile_top_depth = abs(pile.cut_off_level - pile.ground_level)
    gwt_depth = abs(pile.gwt_level - pile.ground_level)
    
    # Critical depth for sand (z_c = 15 * D)
    critical_depth = 15.0 * D_m
    
    current_sigma_v_eff = 0.0
    
    # 2. Perform Calculations (Layer by Layer)
    for layer in layers:
        L_top = layer.depth_top
        L_bottom = layer.depth_bottom
        
        z_start = max(L_top, pile_top_depth)
        z_end = min(L_bottom, toe_depth)
        
        if z_end > z_start:
            seg_length = z_end - z_start
            As_seg = math.pi * D_m * seg_length
            
            z_mid = (z_start + z_end) / 2.0
            
            def get_sigma_eff(depth):
                s = 0.0
                for l in layers:
                    l_t = l.depth_top
                    l_b = min(l.depth_bottom, depth)
                    if l_b > l_t:
                        z_w = gwt_depth
                        if l_b <= z_w:
                            s += (l_b - l_t) * l.gamma
                        elif l_t >= z_w:
                            s += (l_b - l_t) * (l.gamma - 9.81)
                        else:
                            s += (z_w - l_t) * l.gamma
                            s += (l_b - z_w) * (l.gamma - 9.81)
                    if l.depth_bottom >= depth:
                        break
                return s

            sigma_mid_raw = get_sigma_eff(z_mid)
            # Apply Critical Depth cap
            sigma_mid = min(sigma_mid_raw, get_sigma_eff(critical_depth))
            
            f_s = 0.0
            calc_note = ""
            
            if layer.ignore_skin_friction:
                f_s = 0.0
                calc_note = "Skin friction ignored (Socket Mode)"
            elif layer.soil_type == SoilType.SAND:
                delta = 0.9 * layer.phi
                f_s = layer.Ks * sigma_mid * math.tan(deg2rad(delta))
                calc_note = f"fs = Ks({layer.Ks:.2f}) * sigma_v'({sigma_mid:.1f}) * tan({delta:.1f}) = {f_s:.2f} kPa"
                if z_mid > critical_depth:
                    calc_note += f" (Capped at z_c={critical_depth:.1f}m)"
            elif layer.soil_type == SoilType.CLAY:
                f_s = layer.alpha * layer.Cu
                calc_note = f"fs = alpha({layer.alpha}) * Cu({layer.Cu}) = {f_s:.2f} kPa"
            elif layer.soil_type == SoilType.ROCK:
                quc_kpa = layer.quc * 98.0665
                if layer.RQD >= 0.75:
                    beta_q = 1.0
                elif layer.RQD >= 0.50:
                    beta_q = 0.7
                else:
                    beta_q = 0.3
                
                if quc_kpa < 5000:
                    f_s = layer.rock_reduction_factor * 0.5 * quc_kpa * beta_q
                    calc_note = f"fs (Weak) = alpha({layer.rock_reduction_factor}) * 0.5 * quc * beta_rqd({beta_q}) = {f_s:.2f} kPa"
                else:
                    f_s = 0.05 * quc_kpa * beta_q
                    calc_note = f"fs (Hard) = 0.05 * quc * beta_rqd({beta_q}) = {f_s:.2f} kPa"
            
            qs_layer = f_s * As_seg
            total_Qs_comp += qs_layer
            total_Qs_tens += qs_layer
            
            segments_summary.append({
                "Layer": layer.name,
                "Type": layer.soil_type.value,
                "L (m)": f"{seg_length:.2f}",
                "Area (m²)": f"{As_seg:.2f}",
                "Formula": calc_note,
                "Qs (kN)": round(qs_layer, 2)
            })
        
        current_sigma_v_eff = get_sigma_eff(L_bottom)
        
        # Check for toe bearing
        if L_top <= toe_depth <= L_bottom:
            sigma_toe_raw = get_sigma_eff(toe_depth)
            sigma_toe = min(sigma_toe_raw, get_sigma_eff(critical_depth))
            
            if layer.soil_type == SoilType.SAND:
                Qb = sigma_toe * layer.Nq * Ab
                toe_note = f"Qb = sigma_v'({sigma_toe:.1f}) * Nq({layer.Nq}) * Ab({Ab:.3f})"
                if toe_depth > critical_depth:
                    toe_note += f" (Capped at z_c={critical_depth:.1f}m)"
            elif layer.soil_type == SoilType.CLAY:
                Qb = layer.Nc * layer.Cu * Ab
                toe_note = f"Qb = Nc({layer.Nc}) * Cu({layer.Cu}) * Ab({Ab:.3f})"
            elif layer.soil_type == SoilType.ROCK:
                if layer.RQD >= 0.75:
                    ncr = 4.5
                elif layer.RQD >= 0.50:
                    ncr = 3.0
                else:
                    ncr = 1.0
                
                quc_kpa = layer.quc * 98.0665
                Qb = ncr * quc_kpa * Ab
                toe_note = f"Qb = Ncr({ncr}) [based on RQD {layer.RQD:.2f}] * quc({quc_kpa:.1f}) * Ab({Ab:.3f})"

    # 3. Improved Settlement Calculation (v2.3)
    # Weighted average Es along the pile shaft
    avg_Es = 0.0
    total_L = 0.0
    for layer in layers:
        l_t = max(layer.depth_top, pile_top_depth)
        l_b = min(layer.depth_bottom, toe_depth)
        if l_b > l_t:
            es_layer = getattr(layer, 'Es', 25000.0) or 25000.0
            avg_Es += es_layer * (l_b - l_t)
            total_L += (l_b - l_t)
    avg_Es = avg_Es / total_L if total_L > 0 else 25000.0
    
    # Pile axial stiffness (Ep in kPa)
    Ep = options.E_concrete * 1000.0
    
    # Working load for settlement (serviceability)
    P_service = loads.working_vertical if loads.working_vertical > 0 else 1.0
    
    # Approximate load distribution: assume ~30-50% of load taken by tip for friction piles
    # More accurate: use proportion of Qb / Qu
    Qu_temp = total_Qs_comp + Qb
    tip_ratio = Qb / Qu_temp if Qu_temp > 0 else 0.3
    tip_ratio = max(0.1, min(0.7, tip_ratio))
    
    Qb_service = P_service * tip_ratio
    Qs_service = P_service * (1.0 - tip_ratio)
    
    # s1: elastic shortening of pile
    # s1 = (Qb + 0.5*Qs) * L / (Ap * Ep)
    s1 = (Qb_service + 0.5 * Qs_service) * total_L / (Ab * Ep) * 1000.0  # mm
    
    # s2: settlement of pile tip (simplified elastic)
    # s2 ≈ (qb * D * I_p) / Es   with I_p ≈ 0.5~0.6 for rigid base
    qb = Qb_service / Ab if Ab > 0 else 0.0
    s2 = (qb * D_m / avg_Es) * 0.55 * 1000.0  # mm
    
    # s3: approximate additional settlement from shaft friction transfer (small)
    s3 = (Qs_service / (math.pi * D_m * total_L * avg_Es / 1000.0)) * 0.3 * 1000.0 if total_L > 0 else 0.0
    
    total_settlement = s1 + s2 + s3

    # 4. Final results
    Qu_comp = total_Qs_comp + Qb
    Qall_comp = Qu_comp / options.fos_geotech
    
    Qu_tens = total_Qs_tens
    Qall_tens = Qu_tens / (options.fos_geotech * 1.5)
    
    fos_actual = Qu_comp / loads.working_vertical if loads.working_vertical > 0 else 0.0
    
    l_eff = sum(float(seg["L (m)"]) for seg in segments_summary if "ignored" not in seg["Formula"].lower())
    as_eff = sum(float(seg["Area (m²)"]) for seg in segments_summary if "ignored" not in seg["Formula"].lower())

    return {
        "Qs": total_Qs_comp,
        "Qb": Qb,
        "Qu": Qu_comp,
        "Qall": Qall_comp,
        "Qu_tens": Qu_tens,
        "Qall_tens": Qall_tens,
        "Settlement": total_settlement,
        "Settlement_s1": s1,
        "Settlement_s2": s2,
        "Settlement_s3": s3,
        "FoS": fos_actual,
        "L_eff": l_eff,
        "As_eff": as_eff,
        "Segments": segments_summary,
        "ToeNote": toe_note,
        "avg_Es": avg_Es
    }
