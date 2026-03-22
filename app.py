
import math
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

from modules.rc_utils import (
    bar_area_mm2, beta1_aci, phi_flexure_tension_controlled, phi_compression_tied,
    steel_ratio_limits_beam, frame_detailing_limits, effective_depth_beam, factored_self_weight_kN_m,
    beam_flexure_capacity, beam_shear_capacity, design_beam_longitudinal_steel,
    design_beam_stirrups, moment_curvature_rect_beam, one_way_slab_design,
    two_way_slab_moment_coeff_design, rect_column_uniaxial_interaction,
    biaxial_column_capacity_ratio, joint_shear_check, column_tie_spacing_limit,
    development_length_note, strong_column_weak_beam_ratio
)

st.set_page_config(page_title="RC Seismic Designer", layout="wide")
st.title("RC Beam, Column, Slab, and Joint Designer")
st.caption("Educational preliminary design tool for reinforced concrete members with ACI/NSCP-style strength and seismic detailing checks. Final design still requires engineer review, full code verification, load combinations, and project-specific detailing.")

with st.sidebar:
    st.header("Design Basis")
    code_basis = st.selectbox("Reference basis", ["NSCP-aligned (ACI 318 style)", "ACI 318 style"])
    unit_strength = st.selectbox("Concrete unit system", ["MPa / mm / kN"])
    st.markdown("---")
    st.write("This app supports:")
    st.write("- Beam flexure, shear, detailing, moment-curvature")
    st.write("- Column uniaxial interaction and biaxial check")
    st.write("- Beam-column joint shear check")
    st.write("- One-way and two-way slab design")

tabs = st.tabs(["Beam", "Column", "Joint", "Slab", "Notes"])

# =========================
# BEAM TAB
# =========================
with tabs[0]:
    st.header("Beam Designer")
    c1, c2, c3 = st.columns(3)
    with c1:
        b = st.number_input("Beam width b (mm)", 200.0, 1500.0, 300.0, 10.0, key="beam_b")
        h = st.number_input("Overall depth h (mm)", 300.0, 2000.0, 600.0, 10.0, key="beam_h")
        cover = st.number_input("Clear cover (mm)", 20.0, 100.0, 40.0, 5.0, key="beam_cover")
        stirrup_dia = st.selectbox("Stirrup dia (mm)", [10, 12, 16], index=0, key="beam_st")
        main_bar_dia = st.selectbox("Trial main bar dia (mm)", [16, 20, 25, 28, 32], index=2, key="beam_main")
    with c2:
        fc = st.number_input("Concrete strength f'c (MPa)", 17.0, 80.0, 28.0, 1.0, key="beam_fc")
        fy = st.number_input("Longitudinal steel fy (MPa)", 280.0, 600.0, 420.0, 10.0, key="beam_fy")
        fys = st.number_input("Transverse steel fyt (MPa)", 280.0, 600.0, 420.0, 10.0, key="beam_fys")
        frame_type = st.selectbox("Seismic frame type", ["SMRF", "IMRF", "OMRF"], key="beam_frame")
    with c3:
        Mu_pos = st.number_input("Factored positive moment Mu+ (kN·m)", 0.0, 10000.0, 250.0, 5.0, key="beam_mu_pos")
        Mu_neg = st.number_input("Factored negative moment Mu- (kN·m)", 0.0, 10000.0, 300.0, 5.0, key="beam_mu_neg")
        Vu = st.number_input("Factored shear Vu (kN)", 0.0, 10000.0, 180.0, 5.0, key="beam_vu")
        L_clear = st.number_input("Clear span Ln (mm)", 1000.0, 20000.0, 6000.0, 50.0, key="beam_ln")
        include_self_weight = st.checkbox("Add self-weight estimate to notes", value=True, key="beam_sw")

    d = effective_depth_beam(h, cover, stirrup_dia, main_bar_dia)
    rho_min, rho_max = steel_ratio_limits_beam(fc, fy)
    steel_area = bar_area_mm2(main_bar_dia)
    limits = frame_detailing_limits(frame_type, member="beam", h=h)

    As_pos_req, phiMn_pos, rho_pos = design_beam_longitudinal_steel(b, d, fc, fy, Mu_pos)
    As_neg_req, phiMn_neg, rho_neg = design_beam_longitudinal_steel(b, d, fc, fy, Mu_neg)

    nbar_pos = max(2, math.ceil(As_pos_req / steel_area))
    nbar_neg = max(2, math.ceil(As_neg_req / steel_area))
    As_pos_prov = nbar_pos * steel_area
    As_neg_prov = nbar_neg * steel_area
    phiMn_pos_prov, Mn_pos_prov = beam_flexure_capacity(b, d, fc, fy, As_pos_prov)
    phiMn_neg_prov, Mn_neg_prov = beam_flexure_capacity(b, d, fc, fy, As_neg_prov)

    Av_req, s_req, phiVn, Vc, Vs_req = design_beam_stirrups(b, d, fc, fys, stirrup_dia, Vu, frame_type)
    sw = factored_self_weight_kN_m(b, h) if include_self_weight else None

    r1, r2 = st.columns([1,1])
    with r1:
        st.subheader("Beam Design Summary")
        beam_df = pd.DataFrame([
            ["Effective depth d (mm)", round(d,1)],
            ["ρmin", round(rho_min,4)],
            ["ρmax (tension-controlled cap used by app)", round(rho_max,4)],
            ["Required As+ (mm²)", round(As_pos_req,1)],
            ["Provided As+ (mm²)", round(As_pos_prov,1)],
            ["Required As- (mm²)", round(As_neg_req,1)],
            ["Provided As- (mm²)", round(As_neg_prov,1)],
            ["φMn+ provided (kN·m)", round(phiMn_pos_prov,1)],
            ["φMn- provided (kN·m)", round(phiMn_neg_prov,1)],
            ["Two-leg stirrup area Av (mm²)", round(Av_req,1)],
            ["Required stirrup spacing s (mm)", round(s_req,1)],
            ["Use stirrup spacing s_prov ≤ (mm)", round(min(s_req, limits["stirrup_spacing_max"]),1)],
            ["Beam end confinement length (mm)", round(limits["end_zone_length"],1)],
        ], columns=["Item","Value"])
        st.dataframe(beam_df, use_container_width=True, hide_index=True)

        st.markdown("**Seismic detailing checks**")
        st.write(f"- Frame type: **{frame_type}**")
        st.write(f"- Max hoop spacing near beam ends: **{limits['stirrup_spacing_max']:.0f} mm**")
        st.write(f"- First hoop from joint face: **≤ {limits['first_hoop_max']:.0f} mm**")
        st.write(f"- Minimum top and bottom continuous bars recommended: **2 each**")
        st.write(f"- Development note: {development_length_note(frame_type, 'beam')}")

        if sw is not None:
            st.info(f"Approximate unfactored self-weight = {sw:.2f} kN/m")

    with r2:
        st.subheader("Moment-Curvature Diagram")
        As_top = st.number_input("As top for M-κ plot (mm²)", 100.0, 20000.0, float(As_neg_prov), 10.0, key="mphi_top")
        As_bot = st.number_input("As bottom for M-κ plot (mm²)", 100.0, 20000.0, float(As_pos_prov), 10.0, key="mphi_bot")
        mc = moment_curvature_rect_beam(
            b=b, h=h, cover=cover, stirrup_dia=stirrup_dia,
            bar_dia=main_bar_dia, As_top=As_top, As_bot=As_bot,
            fc=fc, fy=fy
        )
        fig, ax = plt.subplots(figsize=(7,4))
        ax.plot(mc["curvature"], mc["moment_kNm"])
        ax.set_xlabel("Curvature 1/mm")
        ax.set_ylabel("Moment (kN·m)")
        ax.set_title("Beam Moment-Curvature")
        ax.grid(True, alpha=0.3)
        st.pyplot(fig, use_container_width=True)

        st.metric("Estimated yield moment (kN·m)", f"{mc['yield_moment_kNm']:.1f}")
        st.metric("Estimated ultimate moment (kN·m)", f"{mc['ultimate_moment_kNm']:.1f}")

# =========================
# COLUMN TAB
# =========================
with tabs[1]:
    st.header("Column Designer")
    c1, c2, c3 = st.columns(3)
    with c1:
        bx = st.number_input("Column size b_x (mm)", 250.0, 2000.0, 500.0, 10.0, key="col_bx")
        by = st.number_input("Column size b_y (mm)", 250.0, 2000.0, 500.0, 10.0, key="col_by")
        cover_c = st.number_input("Clear cover (mm)", 25.0, 100.0, 40.0, 5.0, key="col_cover")
        tie_dia = st.selectbox("Tie dia (mm)", [10, 12, 16], index=0, key="col_tie")
        bar_dia_c = st.selectbox("Longitudinal bar dia (mm)", [16, 20, 25, 28, 32, 36], index=2, key="col_bar")
    with c2:
        fc_c = st.number_input("Concrete f'c (MPa)", 17.0, 80.0, 28.0, 1.0, key="col_fc")
        fy_c = st.number_input("Longitudinal steel fy (MPa)", 280.0, 600.0, 420.0, 10.0, key="col_fy")
        fys_c = st.number_input("Tie steel fy (MPa)", 280.0, 600.0, 420.0, 10.0, key="col_fys")
        frame_type_c = st.selectbox("Seismic frame type", ["SMRF", "IMRF", "OMRF"], key="col_frame")
        Pu = st.number_input("Factored axial load Pu (kN, compression +)", -5000.0, 30000.0, 1800.0, 10.0, key="col_pu")
    with c3:
        Mux = st.number_input("Factored Mux (kN·m)", -10000.0, 10000.0, 150.0, 5.0, key="col_mux")
        Muy = st.number_input("Factored Muy (kN·m)", -10000.0, 10000.0, 120.0, 5.0, key="col_muy")
        nbx = st.number_input("Number of bars along x faces", 2, 12, 4, 1, key="nbx")
        nby = st.number_input("Number of bars along y faces", 2, 12, 4, 1, key="nby")
        L_clear_c = st.number_input("Clear column height (mm)", 1000.0, 10000.0, 3500.0, 50.0, key="col_lc")

    As_bar = bar_area_mm2(bar_dia_c)
    n_bars_total = 2 * nbx + 2 * max(0, nby - 2)
    As_total = n_bars_total * As_bar
    rho_g = As_total / (bx * by)

    inter_x = rect_column_uniaxial_interaction(
        b=bx, h=by, cover=cover_c, tie_dia=tie_dia, bar_dia=bar_dia_c,
        n_bars_face_top=nbx, n_bars_face_bot=nbx, n_bars_side_each=max(0, nby-2),
        fc=fc_c, fy=fy_c, axis="x"
    )
    inter_y = rect_column_uniaxial_interaction(
        b=by, h=bx, cover=cover_c, tie_dia=tie_dia, bar_dia=bar_dia_c,
        n_bars_face_top=nby, n_bars_face_bot=nby, n_bars_side_each=max(0, nbx-2),
        fc=fc_c, fy=fy_c, axis="y"
    )

    biax = biaxial_column_capacity_ratio(
        Pu=Pu, Mux=Mux, Muy=Muy,
        inter_x=inter_x, inter_y=inter_y
    )

    tie_lim = column_tie_spacing_limit(frame_type_c, min(bx, by), bar_dia_c, tie_dia, L_clear_c)

    r1, r2 = st.columns([1,1])
    with r1:
        st.subheader("Column Summary")
        col_df = pd.DataFrame([
            ["Total bars", int(n_bars_total)],
            ["Area per bar (mm²)", round(As_bar,1)],
            ["Total As (mm²)", round(As_total,1)],
            ["Gross steel ratio ρg", round(rho_g,4)],
            ["Biaxial demand/capacity ratio", round(biax["ratio"],3)],
            ["Status", "OK" if biax["ratio"] <= 1.0 else "NG"],
            ["Recommended max tie spacing (mm)", round(tie_lim["spacing_max"],1)],
            ["Confinement length from joint face (mm)", round(tie_lim["end_zone_length"],1)],
        ], columns=["Item","Value"])
        st.dataframe(col_df, use_container_width=True, hide_index=True)
        st.write(f"- Suggested tie spacing for {frame_type_c}: **≤ {tie_lim['spacing_max']:.0f} mm**")
        st.write(f"- First tie from joint face: **≤ {tie_lim['first_tie_max']:.0f} mm**")
        st.write(f"- Development note: {development_length_note(frame_type_c, 'column')}")

    with r2:
        st.subheader("Uniaxial Interaction Diagram")
        fig2, ax2 = plt.subplots(figsize=(7,5))
        ax2.plot(inter_x["Mphi"], inter_x["Pphi"], label="About x-axis")
        ax2.plot(inter_y["Mphi"], inter_y["Pphi"], label="About y-axis")
        ax2.scatter([abs(Mux)], [Pu], s=60, label="Demand vs x curve")
        ax2.set_xlabel("φMn (kN·m)")
        ax2.set_ylabel("φPn (kN)")
        ax2.set_title("Column Interaction")
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        st.pyplot(fig2, use_container_width=True)

        st.markdown("**Biaxial check using load-contour approximation**")
        st.write(f"- Available φMnx at Pu: **{biax['Mnx_at_Pu']:.1f} kN·m**")
        st.write(f"- Available φMny at Pu: **{biax['Mny_at_Pu']:.1f} kN·m**")
        st.write(f"- Interaction exponent α: **{biax['alpha']:.2f}**")
        st.write(f"- Ratio = (|Mux|/Mnx)^α + (|Muy|/Mny)^α = **{biax['ratio']:.3f}**")

# =========================
# JOINT TAB
# =========================
with tabs[2]:
    st.header("Beam-Column Joint Check")
    jc1, jc2, jc3 = st.columns(3)
    with jc1:
        joint_type = st.selectbox("Joint type", ["Interior", "Exterior", "Corner"], key="joint_type")
        bj = st.number_input("Joint width b_j (mm)", 250.0, 2000.0, 500.0, 10.0)
        hc = st.number_input("Column depth in loading direction h_c (mm)", 250.0, 2000.0, 500.0, 10.0)
        fcj = st.number_input("Concrete f'c (MPa)", 17.0, 80.0, 28.0, 1.0)
    with jc2:
        Vu_joint = st.number_input("Joint shear demand Vjh (kN)", 0.0, 10000.0, 600.0, 10.0)
        frame_joint = st.selectbox("Frame type", ["SMRF", "IMRF", "OMRF"], key="joint_frame")
        beam_left_Mpr = st.number_input("Left beam probable moment Mpr (kN·m)", 0.0, 5000.0, 350.0, 10.0)
        beam_right_Mpr = st.number_input("Right beam probable moment Mpr (kN·m)", 0.0, 5000.0, 320.0, 10.0)
    with jc3:
        col_top_Mn = st.number_input("Top column nominal flexural strength Mn (kN·m)", 0.0, 10000.0, 450.0, 10.0)
        col_bot_Mn = st.number_input("Bottom column nominal flexural strength Mn (kN·m)", 0.0, 10000.0, 450.0, 10.0)
        beam_left_Mn = st.number_input("Left beam nominal strength Mn (kN·m)", 0.0, 10000.0, 300.0, 10.0)
        beam_right_Mn = st.number_input("Right beam nominal strength Mn (kN·m)", 0.0, 10000.0, 300.0, 10.0)

    joint = joint_shear_check(bj, hc, fcj, Vu_joint, frame_joint, joint_type)
    scwb = strong_column_weak_beam_ratio(col_top_Mn, col_bot_Mn, beam_left_Mpr, beam_right_Mpr)

    joint_df = pd.DataFrame([
        ["Joint shear demand Vjh (kN)", round(Vu_joint,1)],
        ["Nominal joint shear strength Vn (kN)", round(joint["Vn"],1)],
        ["φVn (kN)", round(joint["phiVn"],1)],
        ["Status", "OK" if joint["ok"] else "NG"],
        ["SCWB ratio ΣMnc / ΣMpb", round(scwb,3)],
        ["SCWB status", "OK" if scwb >= 1.2 else "Review / NG for SMRF intent"],
    ], columns=["Item","Value"])
    st.dataframe(joint_df, use_container_width=True, hide_index=True)
    st.write(f"Joint coefficient used = **{joint['gamma']}** for {frame_joint} {joint_type.lower()} joint.")
    st.write("Probable beam moments should reflect expected overstrength and reinforcement arrangement. Use project-specific code equations for final submission.")

# =========================
# SLAB TAB
# =========================
with tabs[3]:
    st.header("Slab Designer")
    slab_type = st.selectbox("Slab type", ["One-way", "Two-way"])
    s1, s2, s3 = st.columns(3)
    with s1:
        lx = st.number_input("Short span lx (mm)", 1000.0, 15000.0, 3000.0, 50.0)
        ly = st.number_input("Long span ly (mm)", 1000.0, 15000.0, 5000.0, 50.0)
        hs = st.number_input("Slab thickness h (mm)", 80.0, 500.0, 150.0, 5.0)
    with s2:
        fc_s = st.number_input("Concrete f'c (MPa)", 17.0, 80.0, 28.0, 1.0, key="slab_fc")
        fy_s = st.number_input("Steel fy (MPa)", 280.0, 600.0, 420.0, 10.0, key="slab_fy")
        cover_s = st.number_input("Cover (mm)", 15.0, 50.0, 20.0, 5.0)
        bar_s = st.selectbox("Bar dia (mm)", [10, 12, 16], index=0, key="slab_bar")
    with s3:
        D = st.number_input("Superimposed dead load (kPa)", 0.0, 20.0, 1.5, 0.1)
        L = st.number_input("Live load (kPa)", 0.0, 20.0, 2.0, 0.1)
        strip_w = st.number_input("Design strip width (mm)", 500.0, 2000.0, 1000.0, 100.0)

    if slab_type == "One-way":
        res = one_way_slab_design(lx, hs, cover_s, bar_s, fc_s, fy_s, D, L, strip_w)
        slab_df = pd.DataFrame([
            ["Factored load wu (kPa)", round(res["wu"],3)],
            ["Design moment Mu (kN·m)", round(res["Mu"],3)],
            ["Required As (mm²/m)", round(res["As_req"],1)],
            ["Provided As (mm²/m)", round(res["As_prov"],1)],
            ["Bar spacing used (mm)", round(res["spacing"],1)],
            ["φMn (kN·m)", round(res["phiMn"],3)],
            ["Status", "OK" if res["ok"] else "NG"]
        ], columns=["Item","Value"])
        st.dataframe(slab_df, use_container_width=True, hide_index=True)
        st.write("One-way slab uses simple strip design with simply supported coefficient Mu = wu L² / 8 unless user refines externally.")
    else:
        panel = two_way_slab_moment_coeff_design(lx, ly, hs, cover_s, bar_s, fc_s, fy_s, D, L, strip_w)
        slab_df = pd.DataFrame([
            ["Aspect ratio ly/lx", round(panel["ly_lx"],3)],
            ["wu (kPa)", round(panel["wu"],3)],
            ["Mx+ (kN·m/m)", round(panel["Mx_pos"],3)],
            ["My+ (kN·m/m)", round(panel["My_pos"],3)],
            ["Required Asx (mm²/m)", round(panel["Asx_req"],1)],
            ["Required Asy (mm²/m)", round(panel["Asy_req"],1)],
            ["Provided Asx (mm²/m)", round(panel["Asx_prov"],1)],
            ["Provided Asy (mm²/m)", round(panel["Asy_prov"],1)],
            ["Status X", "OK" if panel["ok_x"] else "NG"],
            ["Status Y", "OK" if panel["ok_y"] else "NG"],
        ], columns=["Item","Value"])
        st.dataframe(slab_df, use_container_width=True, hide_index=True)
        st.write("Two-way slab uses coefficient-based approximate design for uniformly loaded panels. Use direct design or equivalent frame method as required by project conditions.")

# =========================
# NOTES TAB
# =========================
with tabs[4]:
    st.header("Important Notes")
    st.markdown("""
1. This app is intended for **preliminary design, teaching, and rapid checking**.
2. NSCP seismic detailing provisions are implemented in an **ACI-style simplified manner** using practical spacing and confinement limits. Final project design must be checked against the exact adopted code edition, material limits, load combinations, development, splice rules, drift, and foundation transfer.
3. Beam moment-curvature and column interaction are **section-level analyses** and do not replace frame-level analysis.
4. Joint design here is a **shear strength screening tool**, not a complete full-detail joint model.
5. Slab design is for **uniform gravity loading** only.
""")
