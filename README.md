
# RC Seismic Designer - Streamlit App

A Streamlit app for preliminary design of:
- RC beams
- RC columns
- beam-column joints
- one-way and two-way slabs

It includes:
- beam flexure + shear + seismic detailing checks
- beam moment-curvature diagram
- column uniaxial interaction diagram
- biaxial column demand/capacity check
- beam-column joint shear check
- slab design for one-way and two-way panels

## Important
This is an **educational and preliminary design tool**.
It is **not** a substitute for full code-based professional design, signed plans, or frame analysis.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Notes on code compliance
The app follows an **NSCP / ACI-style workflow** and includes practical seismic detailing limits for:
- SMRF
- IMRF
- OMRF

For final use on real projects, check the exact edition of NSCP / ACI being adopted in your office and verify:
- load combinations
- seismic overstrength provisions
- confinement and splice locations
- strong-column weak-beam requirements
- joint hoop details
- slab system classification
- drift and stability
- foundation load transfer
