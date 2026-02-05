import streamlit as st
from enum import Enum

# --- 1. THE RULES (Enums) ---
class YesNoUnknown(Enum):
    YES = "Yes"
    NO = "No"
    UNKNOWN = "Unknown"

class Severity(Enum):
    MILD = "Mild"
    MODERATE = "Moderate"
    SEVERE = "Severe"

class Mechanism(Enum):
    PRIMARY = "Primary"
    SECONDARY_FUNCTIONAL = "Secondary (functional)"

# --- 2. THE FRONT END (The "Face") ---
st.title("Concomittant Tricuspid Repair Evaluator")
st.write("Fill out the clinical data below to see the ESC Guideline recommendations.")

# We use columns to make it look organized
col1, col2 = st.columns(2)

with col1:
    left_sided_valve_surgery = st.selectbox("Has the patient had left-sided valve surgery?", [e.value for e in YesNoUnknown])
    tr_severity_input = st.selectbox("What is the TR severity?", [e.value for e in Severity])
    tr_mechanism_input = st.selectbox("What is the TR mechanism?", [e.value for e in Mechanism])
    annulus_dilated = st.selectbox("Tricuspid annulus dilated?", [e.value for e in YesNoUnknown])
    atrial_fib = st.selectbox("Chronic atrial fibrillation?", [e.value for e in YesNoUnknown])

with col2:
    ra_dilatation = st.selectbox("Significant right atrial dilatation?", [e.value for e in YesNoUnknown])
    rv_dysfunction = st.selectbox("RV dilatation or dysfunction?", [e.value for e in YesNoUnknown])
    tethering = st.selectbox("Non-severe leaflet tethering?", [e.value for e in YesNoUnknown])
    phtn = st.selectbox("Pulmonary hypertension present?", [e.value for e in YesNoUnknown])
    organ_dysfunction = st.selectbox("Reversible renal/liver dysfunction?", [e.value for e in YesNoUnknown])

# Additional comorbidities at the bottom
cond_disease = st.selectbox("Is there Conduction disease?", [e.value for e in YesNoUnknown])
no_comorbidities = st.selectbox("No other relevant comorbidities?", [e.value for e in YesNoUnknown])

# Map the strings back to your Enum objects so your logic works
relevant_vars = {
    'tricuspid_regurgitation_severity': Severity(tr_severity_input),
    'tricuspid_annulus_dilated': YesNoUnknown(annulus_dilated),
    'chronic_atrial_fibrillation': YesNoUnknown(atrial_fib),
    'significant_right_atrial_dilatation': YesNoUnknown(ra_dilatation),
    'right_ventricular_dilatation_or_rv_dysfunction': YesNoUnknown(rv_dysfunction),
    'non_severe_tricuspid_leaflet_tethering': YesNoUnknown(tethering),
    'pulmonary_hypertension_present': YesNoUnknown(phtn),
    'reversible_renal_liver_dysfunction': YesNoUnknown(organ_dysfunction),
    'conduction_disease': YesNoUnknown(cond_disease),
    'no_other_relevant_comorbidities': YesNoUnknown(no_comorbidities),
}

# --- 3. THE BRAINS (Scoring Logic) ---
scores_list = []
for var_name, value in relevant_vars.items():
    score = 0
    if var_name == 'tricuspid_regurgitation_severity' and value in [Severity.MODERATE, Severity.SEVERE]:
        score = 1
    elif value == YesNoUnknown.YES and var_name not in ['conduction_disease', 'no_other_relevant_comorbidities']:
        score = 1
    elif var_name == 'tricuspid_regurgitation_severity' and value == Severity.MILD:
        score = -1
    elif value == YesNoUnknown.NO and var_name not in ['conduction_disease', 'no_other_relevant_comorbidities']:
        score = -1
    elif var_name in ['conduction_disease', 'no_other_relevant_comorbidities'] and value == YesNoUnknown.YES:
        score = -1
    scores_list.append(score)

# --- 4. THE OUTPUT (Showing the Results) ---
st.divider()
st.subheader("Results")

# Recommendation Logic
tr_sev = relevant_vars['tricuspid_regurgitation_severity']
tr_mech = Mechanism(tr_mechanism_input)
tr_ann = relevant_vars['tricuspid_annulus_dilated']

if tr_sev == Severity.SEVERE:
    st.success("Class 1: Concomitant TR Repair Recommended")
elif tr_sev == Severity.MODERATE:
    st.info("Class 2a: Concomitant TR Repair should be considered")
elif tr_sev == Severity.MILD and tr_mech == Mechanism.SECONDARY_FUNCTIONAL and tr_ann == YesNoUnknown.YES:
    st.warning("Class 2b: Concomitant TR Repair may be considered")
else:
    st.error("Class 1c: Careful Evaluation / MDT Recommended prior to consideration of intervention")

# Totals
total_plus = sum(1 for s in scores_list if s == 1)
total_minus = sum(1 for s in scores_list if s == -1)

st.write(f"✅ **Factors favoring intervention:** {total_plus}")
st.write(f"❌ **Factors NOT favoring intervention:** {total_minus}")
