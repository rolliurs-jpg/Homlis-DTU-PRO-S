"""Analyse locale en lecture seule des mesures et création du rapport mensuel."""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path


MAX_INTERVAL_SECONDS = 180.0
EXPECTED_INTERVAL_SECONDS = 60.0


def _finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _percent(value, total):
    return 0.0 if total <= 0 else 100.0 * value / total


def analyse_period(times, dtu_pv, shelly_pv, shelly_grid, start, end, export_positive=False):
    """Calcule énergie, provenance et continuité sans interroger les appareils."""
    result = {
        "start": start,
        "end": end,
        "production_kwh": 0.0,
        "consumption_kwh": 0.0,
        "import_kwh": 0.0,
        "export_kwh": 0.0,
        "self_consumption_kwh": 0.0,
        "dtu_seconds": 0.0,
        "shelly_backup_seconds": 0.0,
        "complete_seconds": 0.0,
        "observed_seconds": 0.0,
        "missing_seconds": 0.0,
        "dtu_outages": 0,
        "samples": [],
    }
    in_dtu_outage = False
    count = min(len(times), len(dtu_pv), len(shelly_pv), len(shelly_grid))
    for index in range(count):
        when = times[index]
        if when < start or when > end:
            continue
        next_when = times[index + 1] if index + 1 < count else end
        raw_seconds = max(0.0, (next_when - when).total_seconds())
        seconds = min(raw_seconds, MAX_INTERVAL_SECONDS)
        if seconds <= 0:
            continue
        result["observed_seconds"] += seconds
        if raw_seconds > MAX_INTERVAL_SECONDS:
            result["missing_seconds"] += raw_seconds - EXPECTED_INTERVAL_SECONDS

        dtu = _finite(dtu_pv[index])
        spv = _finite(shelly_pv[index])
        sgrid = _finite(shelly_grid[index])
        if dtu is None:
            if not in_dtu_outage:
                result["dtu_outages"] += 1
            in_dtu_outage = True
        else:
            in_dtu_outage = False
            result["dtu_seconds"] += seconds

        source = "DTU" if dtu is not None else "Shelly" if spv is not None else "Absente"
        production = dtu if dtu is not None else spv
        if dtu is None and spv is not None:
            result["shelly_backup_seconds"] += seconds

        signed_import = None if sgrid is None else (-sgrid if export_positive else sgrid)
        consumption = None
        if spv is not None and signed_import is not None:
            consumption = max(0.0, spv + signed_import)
            result["complete_seconds"] += seconds

        factor = seconds / 3_600_000.0
        if production is not None:
            result["production_kwh"] += max(0.0, production) * factor
        if consumption is not None:
            result["consumption_kwh"] += consumption * factor
            result["self_consumption_kwh"] += min(max(0.0, spv), consumption) * factor
        if signed_import is not None:
            result["import_kwh"] += max(0.0, signed_import) * factor
            result["export_kwh"] += max(0.0, -signed_import) * factor

        result["samples"].append({
            "when": when,
            "seconds": seconds,
            "pv_w": None if spv is None else max(0.0, spv),
            "grid_w": signed_import,
            "production_source": source,
        })

    quality_total = result["observed_seconds"] + result["missing_seconds"]
    result["coverage_pct"] = _percent(result["complete_seconds"], quality_total)
    result["dtu_coverage_pct"] = _percent(result["dtu_seconds"], quality_total)
    result["backup_pct"] = _percent(result["shelly_backup_seconds"], quality_total)
    result["self_consumption_pct"] = _percent(result["self_consumption_kwh"], result["production_kwh"])
    result["self_sufficiency_pct"] = _percent(result["self_consumption_kwh"], result["consumption_kwh"])
    return result


def simulate_batteries(analysis, capacities=(2.0, 5.0, 7.0, 10.0), efficiency=0.90, max_power_w=2000.0):
    """Simule plusieurs capacités à partir des flux Shelly déjà enregistrés."""
    one_way_efficiency = math.sqrt(max(0.01, min(1.0, float(efficiency))))
    simulations = []
    for capacity_kwh in capacities:
        capacity_wh = max(100.0, float(capacity_kwh) * 1000.0)
        soc_wh = 0.0
        captured_wh = delivered_wh = remaining_import_wh = remaining_export_wh = 0.0
        for sample in analysis.get("samples", []):
            pv = sample.get("pv_w")
            grid = sample.get("grid_w")
            seconds = float(sample.get("seconds", 0.0) or 0.0)
            if pv is None or grid is None or seconds <= 0:
                continue
            limit_wh = max_power_w * seconds / 3600.0
            flow_wh = abs(grid) * seconds / 3600.0
            if grid < 0:
                available_input_wh = min(flow_wh, limit_wh)
                stored_wh = min(available_input_wh * one_way_efficiency, capacity_wh - soc_wh)
                soc_wh += stored_wh
                captured_wh += stored_wh / one_way_efficiency
                remaining_export_wh += max(0.0, flow_wh - stored_wh / one_way_efficiency)
            else:
                requested_wh = min(flow_wh, limit_wh)
                delivered = min(requested_wh, soc_wh * one_way_efficiency)
                soc_wh -= delivered / one_way_efficiency
                delivered_wh += delivered
                remaining_import_wh += max(0.0, flow_wh - delivered)
        simulations.append({
            "capacity_kwh": float(capacity_kwh),
            "captured_kwh": captured_wh / 1000.0,
            "avoided_import_kwh": delivered_wh / 1000.0,
            "remaining_import_kwh": remaining_import_wh / 1000.0,
            "remaining_export_kwh": remaining_export_wh / 1000.0,
            "end_soc_kwh": soc_wh / 1000.0,
            "equivalent_cycles": 0.0 if capacity_wh <= 0 else captured_wh / capacity_wh,
        })
    return simulations


def create_monthly_pdf(path, analysis, simulations, title="Rapport mensuel solaire"):
    """Crée un PDF local lisible contenant mesures, qualité et simulation."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError("Le module reportlab manque. Relance l'installateur pour l'ajouter.") from exc

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SmallGrey", parent=styles["BodyText"], fontSize=8.5, leading=11, textColor=colors.HexColor("#475569")))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontSize=13, leading=16, textColor=colors.HexColor("#0f3b69"), spaceBefore=9, spaceAfter=6))
    styles["Title"].fontName = "Helvetica-Bold"
    styles["Title"].fontSize = 21
    styles["Title"].textColor = colors.HexColor("#0b2b4b")
    styles["BodyText"].alignment = TA_LEFT

    doc = SimpleDocTemplate(str(output), pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=15 * mm, bottomMargin=15 * mm, title=title)
    story = [Paragraph(title, styles["Title"])]
    start, end = analysis["start"], analysis["end"]
    story += [Paragraph(f"Période analysée : {start:%d/%m/%Y %H:%M} - {end:%d/%m/%Y %H:%M}", styles["SmallGrey"]), Spacer(1, 5 * mm)]

    metrics = [
        ["Production", "Consommation maison", "Achat réseau", "Injection"],
        [f"{analysis['production_kwh']:.2f} kWh", f"{analysis['consumption_kwh']:.2f} kWh", f"{analysis['import_kwh']:.2f} kWh", f"{analysis['export_kwh']:.2f} kWh"],
    ]
    table = Table(metrics, colWidths=[44 * mm] * 4, rowHeights=[8 * mm, 12 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f2fc")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#334155")),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#0b2b4b")),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8), ("FONTSIZE", (0, 1), (-1, 1), 13),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#94a3b8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
    ]))
    story += [table, Paragraph("Qualité et provenance", styles["Section"])]
    quality = [
        ["Indicateur", "Résultat", "Interprétation"],
        ["Données complètes Shelly", f"{analysis['coverage_pct']:.1f} %", "Production et flux réseau disponibles"],
        ["Production DTU réelle", f"{analysis['dtu_coverage_pct']:.1f} %", "Valeur directement fournie par la DTU"],
        ["Secours production Shelly", f"{analysis['backup_pct']:.1f} %", "DTU absente, mesure Shelly utilisée"],
        ["Séquences DTU indisponibles", str(analysis["dtu_outages"]), "Coupures distinctes observées"],
        ["Temps non mesuré détecté", f"{analysis['missing_seconds'] / 60.0:.0f} min", "Intervalles supérieurs au rythme normal"],
    ]
    qtable = Table(quality, colWidths=[50 * mm, 30 * mm, 96 * mm], repeatRows=1)
    qtable.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f3b69")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [qtable, Paragraph("Simulation batterie", styles["Section"])]
    rows = [["Capacité", "Surplus capté", "Achat évité", "Injection restante", "Cycles équiv."]]
    for item in simulations:
        rows.append([
            f"{item['capacity_kwh']:.1f} kWh", f"{item['captured_kwh']:.2f} kWh", f"{item['avoided_import_kwh']:.2f} kWh",
            f"{item['remaining_export_kwh']:.2f} kWh", f"{item['equivalent_cycles']:.1f}",
        ])
    btable = Table(rows, colWidths=[31 * mm, 36 * mm, 36 * mm, 40 * mm, 33 * mm], repeatRows=1)
    btable.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")), ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0fdfa")]),
    ]))
    story += [btable, Spacer(1, 4 * mm), Paragraph(
        "Hypothèses : batterie vide au début de la période, rendement aller-retour de 90 %, puissance de charge et décharge limitée à 2 000 W. "
        "Cette simulation sert au dimensionnement. Elle ne tient pas compte du prix, de l'usure, de la réserve de secours ni des limites propres à un modèle de batterie.",
        styles["SmallGrey"],
    ), Paragraph(
        "Rapport généré localement par Boîte noire Hoymiles. Lecture seule : aucune commande n'est envoyée à la DTU, au Dinky, au Shelly ou à l'installation électrique.",
        styles["SmallGrey"],
    )]
    doc.build(story)
    return output
