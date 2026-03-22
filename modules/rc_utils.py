
import math
import numpy as np

def bar_area_mm2(d_mm: float) -> float:
    return math.pi * d_mm ** 2 / 4.0

def beta1_aci(fc_mpa: float) -> float:
    if fc_mpa <= 28:
        return 0.85
    return max(0.65, 0.85 - 0.05 * ((fc_mpa - 28) / 7.0))

def phi_flexure_tension_controlled(eps_t: float) -> float:
    if eps_t >= 0.005:
        return 0.90
    if eps_t <= 0.002:
        return 0.65
    return 0.65 + (eps_t - 0.002) * (0.25 / 0.003)

def phi_compression_tied() -> float:
    return 0.65

def steel_ratio_limits_beam(fc: float, fy: float):
    rho_min = max(0.25 * math.sqrt(fc) / fy, 1.4 / fy)
    rho_bal = 0.85 * beta1_aci(fc) * fc / fy * (0.003 / (0.003 + fy / 200000.0))
    rho_max = 0.75 * rho_bal
    return rho_min, rho_max

def frame_detailing_limits(frame_type: str, member: str, h: float):
    frame_type = frame_type.upper()
    if member == "beam":
        if frame_type == "SMRF":
            smax = min(h / 4.0, 150.0, 6 * 25.0)
        elif frame_type == "IMRF":
            smax = min(h / 3.0, 200.0)
        else:
            smax = min(h / 2.0, 300.0)
        return {
            "stirrup_spacing_max": smax,
            "first_hoop_max": min(50.0, smax),
            "end_zone_length": max(2*h, 500.0)
        }
    return {}

def effective_depth_beam(h: float, cover: float, stirrup_dia: float, main_bar_dia: float) -> float:
    return h - cover - stirrup_dia - 0.5 * main_bar_dia

def factored_self_weight_kN_m(b_mm: float, h_mm: float, gamma_rc=24.0) -> float:
    return (b_mm/1000.0) * (h_mm/1000.0) * gamma_rc

def beam_flexure_capacity(b, d, fc, fy, As):
    a = As * fy / (0.85 * fc * b)
    Mn = As * fy * (d - a / 2.0) / 1e6
    c = a / beta1_aci(fc) if beta1_aci(fc) > 1e-9 else 1e9
    eps_t = 0.003 * (d - c) / max(c, 1e-9)
    phi = phi_flexure_tension_controlled(eps_t)
    return phi * Mn, Mn

def design_beam_longitudinal_steel(b, d, fc, fy, Mu_kNm):
    rho_min, rho_max = steel_ratio_limits_beam(fc, fy)
    if Mu_kNm <= 1e-9:
        return rho_min * b * d, 0.0, rho_min
    As_try = max(rho_min * b * d, 1.0)
    for _ in range(200):
        phiMn, _ = beam_flexure_capacity(b, d, fc, fy, As_try)
        err = Mu_kNm - phiMn
        if abs(err) < 1e-3:
            break
        phiMn2, _ = beam_flexure_capacity(b, d, fc, fy, As_try * 1.001)
        grad = (phiMn2 - phiMn) / (As_try * 0.001)
        if abs(grad) < 1e-9:
            break
        As_try += err / grad
        As_try = max(As_try, rho_min * b * d)
        As_try = min(As_try, rho_max * b * d)
    rho = As_try / (b * d)
    return As_try, phiMn, rho

def beam_shear_capacity(b, d, fc, Av, fys, s):
    Vc = 0.17 * math.sqrt(fc) * b * d / 1000.0
    Vs = (Av * fys * d / s) / 1000.0
    phi = 0.75
    return phi * (Vc + Vs), Vc, Vs

def design_beam_stirrups(b, d, fc, fys, stirrup_dia, Vu, frame_type):
    Av = 2 * bar_area_mm2(stirrup_dia)
    Vc = 0.17 * math.sqrt(fc) * b * d / 1000.0
    phi = 0.75
    Vs_req = max(0.0, Vu / phi - Vc)
    if Vs_req <= 1e-9:
        s_req = 300.0
    else:
        s_req = Av * fys * d / (Vs_req * 1000.0)
    lim = frame_detailing_limits(frame_type, "beam", h=d*1.15)["stirrup_spacing_max"]
    s_req = min(s_req, lim)
    phiVn = phi * (Vc + (Av * fys * d / s_req) / 1000.0)
    return Av, s_req, phiVn, Vc, Vs_req

def _steel_stress_from_strain(es, fy, Es=200000.0):
    ey = fy / Es
    if es > ey:
        return fy
    if es < -ey:
        return -fy
    return Es * es

def moment_curvature_rect_beam(b, h, cover, stirrup_dia, bar_dia, As_top, As_bot, fc, fy):
    y_top = cover + stirrup_dia + 0.5 * bar_dia
    y_bot = h - y_top
    curvatures, moments = [], []
    yield_reached = False
    yield_m = None
    eps_cu_values = np.linspace(1e-5, 0.0035, 120)

    for eps_top in eps_cu_values:
        best = None
        for c in np.linspace(5, h*3, 1500):
            a = beta1_aci(fc) * c
            Cc = 0.85 * fc * b * min(a, h)
            eps_s_top = eps_top * (1 - y_top / c)
            eps_s_bot = eps_top * (1 - y_bot / c)
            fs_top = _steel_stress_from_strain(eps_s_top, fy)
            fs_bot = _steel_stress_from_strain(eps_s_bot, fy)
            Ttop = As_top * fs_top
            Tbot = As_bot * fs_bot
            P = Cc + Ttop + Tbot
            if best is None or abs(P) < best[0]:
                M = (
                    Cc * (h/2 - min(a, h)/2) +
                    Ttop * (h/2 - y_top) +
                    Tbot * (h/2 - y_bot)
                ) / 1e6
                best = (abs(P), c, M, eps_s_top, eps_s_bot)
        _, c, M, est, esb = best
        phi = eps_top / c
        curvatures.append(phi)
        moments.append(abs(M))
        if not yield_reached and (abs(est) >= fy/200000.0 or abs(esb) >= fy/200000.0):
            yield_reached = True
            yield_m = abs(M)

    return {
        "curvature": np.array(curvatures),
        "moment_kNm": np.array(moments),
        "yield_moment_kNm": float(yield_m if yield_m is not None else moments[0]),
        "ultimate_moment_kNm": float(max(moments)),
    }

def _rect_bar_coords(b, h, cover, tie_dia, bar_dia, n_top, n_bot, n_side_each):
    x_left = cover + tie_dia + 0.5 * bar_dia
    x_right = b - x_left
    y_top = cover + tie_dia + 0.5 * bar_dia
    y_bot = h - y_top
    coords = []
    if n_top == 1:
        xs = [b/2]
    else:
        xs = np.linspace(x_left, x_right, n_top)
    for x in xs:
        coords.append((x, y_top))
    if n_bot == 1:
        xs = [b/2]
    else:
        xs = np.linspace(x_left, x_right, n_bot)
    for x in xs:
        coords.append((x, y_bot))
    if n_side_each > 0:
        ys = np.linspace(y_top, y_bot, n_side_each + 2)[1:-1]
        for y in ys:
            coords.append((x_left, y))
            coords.append((x_right, y))
    return coords

def rect_column_uniaxial_interaction(b, h, cover, tie_dia, bar_dia, n_bars_face_top, n_bars_face_bot, n_bars_side_each, fc, fy, axis="x"):
    As_bar = bar_area_mm2(bar_dia)
    coords = _rect_bar_coords(b, h, cover, tie_dia, bar_dia, n_bars_face_top, n_bars_face_bot, n_bars_side_each)
    ys = np.array([y for _, y in coords])
    Pphi, Mphi = [], []
    for c in np.linspace(10, h*4, 220):
        beta1 = beta1_aci(fc)
        a = min(beta1 * c, h)
        Cc = 0.85 * fc * b * a
        yc = a / 2.0
        Pn = Cc
        Mn = Cc * (h/2 - yc)
        eps_top = 0.003
        eps_tension = None
        for y in ys:
            eps = eps_top * (1 - y / c)
            fs = _steel_stress_from_strain(eps, fy)
            Fs = fs * As_bar
            Pn += Fs
            Mn += Fs * (h/2 - y)
            if eps_tension is None:
                eps_tension = eps
            else:
                if y > h/2:
                    eps_tension = min(eps_tension, eps)
        phi = phi_flexure_tension_controlled(abs(min(eps_tension,0))) if eps_tension is not None else 0.65
        phi = max(0.65, min(phi, 0.90))
        Pphi.append(phi * Pn / 1000.0)
        Mphi.append(abs(phi * Mn / 1e6))
    # add pure compression cap
    Ag = b*h
    Ast = As_bar * len(coords)
    P0 = 0.85*fc*(Ag - Ast) + fy*Ast
    Pphi.insert(0, 0.80 * phi_compression_tied() * P0 / 1000.0)
    Mphi.insert(0, 0.0)
    return {"Pphi": np.array(Pphi), "Mphi": np.array(Mphi)}

def _interp_capacity_at_P(Ptarget, P_arr, M_arr):
    P = np.array(P_arr); M = np.array(M_arr)
    idx = np.argsort(P)
    P = P[idx]; M = M[idx]
    if Ptarget <= P.min():
        return float(M[np.argmin(P)])
    if Ptarget >= P.max():
        return float(M[np.argmax(P)])
    return float(np.interp(Ptarget, P, M))

def biaxial_column_capacity_ratio(Pu, Mux, Muy, inter_x, inter_y):
    Mnx = max(1e-6, _interp_capacity_at_P(Pu, inter_x["Pphi"], inter_x["Mphi"]))
    Mny = max(1e-6, _interp_capacity_at_P(Pu, inter_y["Pphi"], inter_y["Mphi"]))
    compression_ratio = max(0.0, Pu) / max(inter_x["Pphi"].max(), inter_y["Pphi"].max(), 1e-6)
    alpha = 1.0 + 1.0 * min(compression_ratio, 1.0)
    ratio = (abs(Mux)/Mnx)**alpha + (abs(Muy)/Mny)**alpha
    return {"Mnx_at_Pu": Mnx, "Mny_at_Pu": Mny, "alpha": alpha, "ratio": ratio}

def joint_shear_check(bj, hc, fc, Vuh, frame_type, joint_type):
    # Simplified joint shear coefficient
    frame_type = frame_type.upper()
    jt = joint_type.lower()
    if frame_type == "SMRF":
        gamma = 1.25 if jt == "interior" else 1.0
    elif frame_type == "IMRF":
        gamma = 1.0 if jt == "interior" else 0.8
    else:
        gamma = 0.85 if jt == "interior" else 0.7
    Vn = gamma * math.sqrt(fc) * bj * hc / 1000.0
    phiVn = 0.85 * Vn
    return {"gamma": gamma, "Vn": Vn, "phiVn": phiVn, "ok": phiVn >= Vuh}

def column_tie_spacing_limit(frame_type, least_dim, long_bar_dia, tie_dia, clear_height):
    frame_type = frame_type.upper()
    if frame_type == "SMRF":
        smax = min(least_dim/4.0, 6*long_bar_dia, 150.0)
    elif frame_type == "IMRF":
        smax = min(least_dim/3.0, 200.0)
    else:
        smax = min(least_dim/2.0, 300.0)
    return {
        "spacing_max": smax,
        "first_tie_max": min(75.0, smax),
        "end_zone_length": max(least_dim, clear_height/6.0, 450.0)
    }

def development_length_note(frame_type, member_type):
    if frame_type == "SMRF":
        return f"Use seismic hook/anchorage and avoid lap splices in potential plastic hinge zones for {member_type}s."
    if frame_type == "IMRF":
        return f"Check splice and anchorage away from critical end regions for {member_type}s."
    return f"Use full development and code splice limits for {member_type}s."

def strong_column_weak_beam_ratio(col_top_Mn, col_bot_Mn, beam_left_Mpr, beam_right_Mpr):
    denom = max(beam_left_Mpr + beam_right_Mpr, 1e-6)
    return (col_top_Mn + col_bot_Mn) / denom

def one_way_slab_design(lx, h, cover, bar_dia, fc, fy, D, L, strip_w):
    self_w = 24.0 * h/1000.0
    wu = 1.2*(D + self_w) + 1.6*L
    Mu = wu * (lx/1000.0)**2 / 8.0 * (strip_w/1000.0) / 1.0
    d = h - cover - 0.5*bar_dia
    b = strip_w
    As_req, _, _ = design_beam_longitudinal_steel(b, d, fc, fy, Mu)
    area_bar = bar_area_mm2(bar_dia)
    spacing = min(450.0, max(75.0, 1000.0 * area_bar / max(As_req, 1e-6)))
    As_prov = 1000.0/spacing * area_bar
    phiMn, _ = beam_flexure_capacity(b, d, fc, fy, As_prov)
    return {
        "wu": wu, "Mu": Mu, "As_req": As_req * 1000.0 / strip_w, "As_prov": As_prov,
        "spacing": spacing, "phiMn": phiMn, "ok": phiMn >= Mu
    }

def two_way_slab_moment_coeff_design(lx, ly, h, cover, bar_dia, fc, fy, D, L, strip_w):
    self_w = 24.0 * h/1000.0
    wu = 1.2*(D + self_w) + 1.6*L
    ratio = ly / lx
    # coarse coefficients for uniformly loaded simply supported-like panel
    ax = 0.045 if ratio <= 2 else 0.05
    ay = 0.025 if ratio <= 2 else 0.02
    Mx = ax * wu * (lx/1000.0)**2
    My = ay * wu * (lx/1000.0)**2
    d = h - cover - 0.5*bar_dia
    Asx_req, _, _ = design_beam_longitudinal_steel(1000.0, d, fc, fy, Mx)
    Asy_req, _, _ = design_beam_longitudinal_steel(1000.0, d, fc, fy, My)
    area_bar = bar_area_mm2(bar_dia)
    sx = min(450.0, max(75.0, 1000.0 * area_bar / max(Asx_req,1e-6)))
    sy = min(450.0, max(75.0, 1000.0 * area_bar / max(Asy_req,1e-6)))
    Asx_prov = 1000.0/sx * area_bar
    Asy_prov = 1000.0/sy * area_bar
    phiMn_x, _ = beam_flexure_capacity(1000.0, d, fc, fy, Asx_prov)
    phiMn_y, _ = beam_flexure_capacity(1000.0, d, fc, fy, Asy_prov)
    return {
        "ly_lx": ratio, "wu": wu, "Mx_pos": Mx, "My_pos": My,
        "Asx_req": Asx_req, "Asy_req": Asy_req,
        "Asx_prov": Asx_prov, "Asy_prov": Asy_prov,
        "ok_x": phiMn_x >= Mx, "ok_y": phiMn_y >= My
    }
