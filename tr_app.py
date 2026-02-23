import json
import os

import streamlit as st

CALCULATORS_DIR = "calculators"

CATEGORIES = {
    "Cardiac": ["Coronary", "Aortic", "Tricuspid", "Mitral", "Pulmonary", "Arrhythmia", "Miscellaneous"],
    "Thoracic": ["Malignant", "Benign"],
    "Transplant": [],
}

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

    for root, _dirs, files in os.walk(CALCULATORS_DIR):
        for filename in sorted(files):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(root, filename)
            rel_path = os.path.relpath(path, CALCULATORS_DIR)
            parts = rel_path.split(os.sep)
            category = parts[0] if len(parts) > 1 else "Uncategorized"
            subcategory = parts[1] if len(parts) > 2 else ""
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue

            name = data.get("name") or os.path.splitext(filename)[0]
            calculators.append(
                {
                    "id": rel_path,
                    "name": name,
                    "path": path,
                    "data": data,
                    "category": category,
                    "subcategory": subcategory,
                }
            )

    return calculators


def render_message(level, message):
    handler = LEVELS.get(level, st.error)
    handler(message)


# =========================
# SINGLE-MATCH RULE ENGINE
# =========================
def evaluate_rules(tool, values):
    def condition_match(cond):
        input_id = cond.get("input_id")
        expected = cond.get("value")
        op = str(cond.get("op", "equals")).strip().lower()
        actual = values.get(input_id)
        if op == "not_equals":
            return actual != expected
        return actual == expected

    def evaluate_condition_expression(rule):
        conditions = rule.get("conditions", [])
        if not conditions:
            return False, 0, 0.0, 0

        default_join = str(rule.get("condition_operator", "AND")).strip().upper()
        if default_join not in {"AND", "OR"}:
            default_join = "AND"

        matched_count = 0
        first_match = condition_match(conditions[0])
        if first_match:
            matched_count += 1
        current_group = first_match
        group_results = []

        for cond in conditions[1:]:
            cond_is_match = condition_match(cond)
            if cond_is_match:
                matched_count += 1
            join = str(cond.get("join_with_previous", default_join)).strip().upper()
            if join not in {"AND", "OR"}:
                join = default_join
            if join == "AND":
                current_group = current_group and cond_is_match
            else:
                group_results.append(current_group)
                current_group = cond_is_match

        group_results.append(current_group)
        is_match = any(group_results)
        ratio = matched_count / len(conditions)
        return is_match, matched_count, ratio, len(conditions)

    best_match = None

    for rule in tool.get("rules", []):
        is_match, matched, ratio, condition_count = evaluate_condition_expression(rule)
        if not is_match:
            continue

        candidate = {
            "rule": rule,
            "matched": matched,
            "ratio": ratio,
            "condition_count": condition_count,
        }

        if best_match is None:
            best_match = candidate
        else:
            # Prefer stronger / more complete matches
            if (
                (ratio == 1.0 and best_match["ratio"] != 1.0)
                or (matched > best_match["matched"])
                or (ratio > best_match["ratio"])
                or (condition_count > best_match["condition_count"])
            ):
                best_match = candidate

    return [best_match] if best_match else []


def compute_scores(tool, values):
    plus = 0
    minus = 0
    scoring_mode = tool.get("scoring_mode", "signed")
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
        elif score == -1 and scoring_mode == "signed":
            minus += weight

    total = plus - minus if scoring_mode == "signed" else plus
    return plus, minus, total


def evaluate_score_recommendation(tool, values, total_score):
    thresholds = tool.get("scoring_recommendations", [])
    if not thresholds:
        return None
    best = None
    for item in thresholds:
        try:
            min_score = int(item.get("min_score"))
        except (TypeError, ValueError):
            continue
        if total_score >= min_score:
            conditions = item.get("conditions", [])
            matched = 0
            for cond in conditions:
                input_id = cond.get("input_id")
                expected = cond.get("value")
                actual = values.get(input_id)
                op = str(cond.get("op", "equals")).strip().lower()
                if (op == "not_equals" and actual != expected) or (op != "not_equals" and actual == expected):
                    matched += 1
            if conditions and matched != len(conditions):
                continue
            ratio = matched / len(conditions) if conditions else 1.0
            candidate = {
                "min_score": min_score,
                "level": item.get("level", "info"),
                "message": item.get("message", ""),
                "matched": matched,
                "ratio": ratio,
            }
            if best is None or min_score > best.get("min_score", -10**9):
                best = candidate
    return best


def build_label_maps(inputs):
    id_to_label = {}
    for item in inputs:
        input_id = str(item.get("id", "")).strip()
        label = str(item.get("label", "")).strip() or input_id
        if input_id:
            id_to_label[input_id] = label
    return id_to_label


def build_decision_tree_graph(tool, id_to_label, values=None):
    values = values or {}

    def condition_match(cond):
        input_id = cond.get("input_id")
        expected = cond.get("value")
        actual = values.get(input_id)
        op = str(cond.get("op", "equals")).strip().lower()
        if op == "not_equals":
            return actual != expected
        return actual == expected

    lines = [
        "digraph DecisionTree {",
        'rankdir=LR;',
        'node [shape=box, style="rounded,filled", color="gray35", fillcolor="white"];',
    ]
    lines.append('start [label="Start", shape=oval, fillcolor="white"];')
    for ridx, rule in enumerate(tool.get("rules", [])):
        conditions = rule.get("conditions", [])
        rule_node = f"rule_{ridx}"
        rule_label = str(rule.get("name", "")).strip() or f"Rule {ridx + 1}"
        rule_match = all(condition_match(c) for c in conditions) if conditions else False
        rule_attrs = 'fillcolor="white"'
        if rule_match:
            rule_attrs = 'fillcolor="lightyellow", color="goldenrod"'
        lines.append(f'{rule_node} [label="{rule_label}", {rule_attrs}];')
        lines.append(f"start -> {rule_node};")

        prev_node = rule_node
        for cidx, cond in enumerate(conditions):
            cond_node = f"rule_{ridx}_cond_{cidx}"
            input_label = id_to_label.get(cond.get("input_id", ""), cond.get("input_id", ""))
            value = str(cond.get("value", "")).strip()
            op = str(cond.get("op", "equals")).strip().lower()
            operator_label = "!=" if op == "not_equals" else "="
            cond_label = f"{input_label} {operator_label} {value}".replace('"', "'")
            matched = condition_match(cond)
            cond_attrs = 'fillcolor="white"'
            if values:
                cond_attrs = 'fillcolor="palegreen", color="green"' if matched else 'fillcolor="mistyrose", color="red"'
            lines.append(f'{cond_node} [label="{cond_label}", {cond_attrs}];')
            lines.append(f"{prev_node} -> {cond_node};")
            prev_node = cond_node

        out_node = f"rule_{ridx}_out"
        msg = str(rule.get("message", "")).strip() or "Recommendation"
        msg = msg.replace('"', "'")
        out_attrs = 'fillcolor="white"'
        if rule_match:
            out_attrs = 'fillcolor="lightblue", color="dodgerblue4"'
        lines.append(f'{out_node} [shape=note, label="{msg}", {out_attrs}];')
        lines.append(f"{prev_node} -> {out_node};")

    lines.append("}")
    return "\n".join(lines)


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

    calculators = load_calculators()
    if not calculators:
        st.info("No calculators found. Add JSON files to the calculators/ folder.")
        return

    category_choice = st.selectbox("Section", ["Cardiac", "Thoracic", "Transplant", "Uncategorized"])
    filtered = [c for c in calculators if c["category"].lower() == category_choice.lower()]
    if category_choice in CATEGORIES and CATEGORIES[category_choice]:
        sub_choice = st.selectbox("Subsection", CATEGORIES[category_choice])
        filtered = [c for c in filtered if c["subcategory"].lower() == sub_choice.lower()]

    labels = [calc["name"] for calc in filtered]
    if not labels:
        st.info("No calculators found in this section.")
        return
    selected_label = st.selectbox("Choose a calculator", labels)
    selected = filtered[labels.index(selected_label)]
    tool = selected["data"]

    st.divider()
    st.subheader(tool.get("name", "Calculator"))
    if tool.get("description"):
        st.write(tool["description"])

    values = render_inputs(selected["id"], tool.get("inputs", []))

    st.divider()
    st.subheader("Results")
    matches = evaluate_rules(tool, values)
    if matches:
        rule = matches[0]["rule"]
        render_message(rule.get("level", "info"), rule.get("message", ""))

    if tool.get("scoring_rules"):
        plus, minus, total = compute_scores(tool, values)
        score_reco = evaluate_score_recommendation(tool, values, total)
        if score_reco:
            render_message(score_reco.get("level", "info"), score_reco.get("message", ""))
            st.write(f"**Score:** {total}")

    if st.checkbox("Show decision tree", key=f"show_decision_tree_{selected['id']}"):
        id_to_label = build_label_maps(tool.get("inputs", []))
        st.graphviz_chart(build_decision_tree_graph(tool, id_to_label, values))


if __name__ == "__main__":
    main()
