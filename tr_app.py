import json
import os

import streamlit as st

CALCULATORS_DIR = "calculators"

LEVELS = {
    "success": st.success,
    "info": st.info,
    "warning": st.warning,
    "error": st.error,
}


def load_calculators():
    calculators = []
    if not os.path.isdir(CALCULATORS_DIR):
        return calculators

    for filename in sorted(os.listdir(CALCULATORS_DIR)):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(CALCULATORS_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        name = data.get("name") or os.path.splitext(filename)[0]
        calculators.append({"id": filename, "name": name, "path": path, "data": data})

    return calculators


def render_message(level, message):
    handler = LEVELS.get(level, st.error)
    handler(message)


def evaluate_rules(tool, values):
    for rule in tool.get("rules", []):
        conditions = rule.get("conditions", [])
        if not conditions:
            continue
        matches = True
        for cond in conditions:
            input_id = cond.get("input_id")
            expected = cond.get("value")
            actual = values.get(input_id)
            if actual != expected:
                matches = False
                break
        if matches:
            return rule.get("level", "info"), rule.get("message", "")

    fallback = tool.get("fallback", {"level": "warning", "message": "No rules matched."})
    return fallback.get("level", "warning"), fallback.get("message", "No rules matched.")


def compute_scores(tool, values):
    plus = 0
    minus = 0
    for rule in tool.get("scoring_rules", []):
        input_id = rule.get("input_id")
        if not input_id:
            continue
        value = values.get(input_id)
        favor_values = rule.get("favor_values", [])
        against_values = rule.get("against_values", [])
        invert = rule.get("invert_favor", False)
        weight = rule.get("weight", 1) or 1

        score = 0
        if value in favor_values:
            score = -1 if invert else 1
        elif value in against_values:
            score = 1 if invert else -1

        if score == 1:
            plus += weight
        elif score == -1:
            minus += weight

    return plus, minus


def render_inputs(calc_id, inputs):
    values = {}
    for item in inputs:
        input_id = item.get("id")
        label = item.get("label", input_id)
        input_type = item.get("type", "select")
        key = f"{calc_id}_{input_id}"

        if input_type == "select":
            options = item.get("options", [])
            if not options:
                options = [""]
            values[input_id] = st.selectbox(label, options, key=key)
        elif input_type == "number":
            values[input_id] = st.number_input(label, key=key)
        else:
            values[input_id] = st.text_input(label, key=key)

    return values


def main():
    st.set_page_config(page_title="Calculator Home", layout="wide")
    st.title("Calculator Home")
    st.caption("Select a calculator and run it. Upload new JSONs to the repo to add more.")

    with st.sidebar:
        st.subheader("Add Calculator")
        upload = st.file_uploader("Upload calculator JSON", type=["json"])
        overwrite = st.checkbox("Overwrite if name exists", value=False)

        if upload is not None:
            os.makedirs(CALCULATORS_DIR, exist_ok=True)
            filename = os.path.basename(upload.name)
            dest = os.path.join(CALCULATORS_DIR, filename)
            if os.path.exists(dest) and not overwrite:
                st.warning(f"{filename} already exists. Check overwrite to replace it.")
            else:
                with open(dest, "wb") as f:
                    f.write(upload.getbuffer())
                st.success(f"Uploaded {filename}.")
                st.rerun()

        st.divider()
        st.subheader("Delete Calculator")
        existing_files = [
            f
            for f in sorted(os.listdir(CALCULATORS_DIR))
            if f.endswith(".json")
        ] if os.path.isdir(CALCULATORS_DIR) else []

        if not existing_files:
            st.caption("No calculators to delete.")
        else:
            delete_target = st.selectbox("Select calculator to delete", existing_files)
            confirm_delete = st.checkbox("I understand this will delete the file")
            if st.button("Delete selected"):
                if not confirm_delete:
                    st.warning("Please confirm deletion first.")
                else:
                    try:
                        os.remove(os.path.join(CALCULATORS_DIR, delete_target))
                        st.success(f"Deleted {delete_target}.")
                        st.rerun()
                    except OSError as exc:
                        st.error(f"Failed to delete: {exc}")

    calculators = load_calculators()
    if not calculators:
        st.info("No calculators found. Add JSON files to the calculators/ folder.")
        return

    labels = [calc["name"] for calc in calculators]
    selected_label = st.selectbox("Choose a calculator", labels)
    selected = calculators[labels.index(selected_label)]
    tool = selected["data"]

    st.divider()
    st.subheader(tool.get("name", "Calculator"))
    if tool.get("description"):
        st.write(tool["description"])

    values = render_inputs(selected["id"], tool.get("inputs", []))

    st.divider()
    st.subheader("Results")
    level, message = evaluate_rules(tool, values)
    render_message(level, message)

    plus, minus = compute_scores(tool, values)
    st.write(f"✅ **Factors favoring intervention:** {plus}")
    st.write(f"❌ **Factors NOT favoring intervention:** {minus}")


if __name__ == "__main__":
    main()
