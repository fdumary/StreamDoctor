OBSERVATION_FIELDS = ("clarity", "smell", "flow", "foam", "visible_life", "water_color")


def check_plausibility(report, has_photos: bool):
    flags = []

    def flag(code, reason, penalty=0, needs_review=True):
        flags.append({"code": code, "reason": reason, "penalty": penalty, "needs_review": needs_review})

    known = sum(getattr(report, name) not in (None, "unknown") for name in OBSERVATION_FIELDS)
    if known < 2:
        flag("limited_observations", "Fewer than two observation fields contain a known value.")
    if not has_photos:
        flag("missing_photo", "No attached photo is available.", 30)
    if report.flow == "dry" and report.foam not in (None, "none", "unknown"):
        flag(
            "dry_with_foam",
            "Flow is reported as dry while foam is reported present; a reviewer should resolve the context.",
            20,
        )
    if report.flow == "dry" and report.ph is not None:
        flag(
            "dry_with_ph",
            "A pH measurement accompanies a dry-stream observation; it may describe a remaining pool.",
        )
    if report.ph is not None and not 6 <= report.ph <= 9:
        flag(
            "unusual_ph",
            "pH is outside the prototype review band of 6–9. This may be a real event, not a reporting error.",
        )
    return max(0.0, 100.0 - sum(item["penalty"] for item in flags)), flags, known
