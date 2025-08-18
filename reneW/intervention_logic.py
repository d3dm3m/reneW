def suggest_intervention(pipe_type: str, material: str, age: int, renewal_need: float) -> str:
    """
    Suggests an intervention strategy for a pipe.
    """
    pipe_type = pipe_type.lower()
    material = (material or "").lower()

    # High renewal need → immediate action
    if renewal_need >= 0.75:
        if "concrete" in material or "cast iron" in material:
            return "Full Replacement"
        elif "plastic" in material or "PVC" in material:
            return "Replacement or Spot Repairs"
        else:
            return "Replacement"

    # Medium renewal need → preventive action
    if 0.5 <= renewal_need < 0.75:
        if pipe_type == "wastewater" or "spill" in pipe_type:
            return "CIPP Lining or Trenchless Rehab"
        elif pipe_type == "stormwater":
            return "Lining or Partial Replacement"
        elif pipe_type == "water":
            return "Lining (if feasible) or Increased Monitoring"
        else:
            return "Preventive Maintenance"

    # Low renewal need → defer action
    if renewal_need < 0.5:
        if age > 80:
            return "Increase Monitoring (very old asset)"
        elif age > 50:
            return "Plan Rehabilitation in Medium Term"
        else:
            return "No Action (Routine Monitoring)"

    return "Monitoring"
