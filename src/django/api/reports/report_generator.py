from io import BytesIO
from datetime import datetime, timedelta
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import api.controllers as controllers
from auth_app.models import Store
from reportlab.lib.units import mm


class ReportBuildError(Exception):

    pass


def draw_page_meta(canvas, doc, store_code):
    canvas.saveState()

    timestamp = datetime.now().strftime("%d %b %Y %H:%M:%S")

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)

    page_width, page_height = doc.pagesize

    # ---- STORE HEADER (TOP LEFT) ----
    canvas.drawString(36, page_height - 20, f"Store: {store_code}")

    # ---- FOOTER (BOTTOM CENTER) ----
    footer_text = f"Page {doc.page} - {timestamp}"
    canvas.drawCentredString(page_width / 2, 15, footer_text)

    canvas.restoreState()


def build_shift_logs_pdf(
    store, start, end, results, sort_by, min_hours, min_deliveries, sort_desc
) -> bytes:
    try:

        if min_hours is not None:
            results = [
                r for r in results if float(r.get("hours_worked") or 0) >= min_hours
            ]

        if min_deliveries is not None:
            results = [
                r for r in results if int(r.get("deliveries") or 0) >= min_deliveries
            ]

        sort_keys = {
            "name": lambda r: f"{r.get('emp_first_name','')} {r.get('emp_last_name','')}",
            "hours": lambda r: float(r.get("hours_worked") or 0),
            "deliveries": lambda r: int(r.get("deliveries") or 0),
            "login": lambda r: r.get("login_timestamp_raw") or "",
            "logout": lambda r: r.get("logout_timestamp_raw") or "",
        }

        if sort_by in sort_keys:
            results.sort(key=sort_keys[sort_by], reverse=sort_desc)

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=24,
            bottomMargin=36,
        )

        generated_time = datetime.now().strftime("%d %b %Y %H:%M:%S")
        start_fmt = datetime.strptime(start, "%Y-%m-%d").strftime("%d %b %Y")
        end_fmt = datetime.strptime(end, "%Y-%m-%d").strftime("%d %b %Y")

        elements = []
        styles = getSampleStyleSheet()

        # Header
        elements.append(Paragraph(f"Shift Logs Report — {store.name}", styles["Title"]))
        elements.append(Spacer(1, 12))
        meta_line = (
            f"<b>Date Range:</b> {start_fmt} → {end_fmt} &nbsp;&nbsp;&nbsp; "
            f"<b>Store:</b> {store.code} &nbsp;&nbsp;&nbsp; "
            f"<b>Generated:</b> {generated_time}"
        )

        elements.append(Paragraph(meta_line, styles["Normal"]))
        elements.append(Spacer(1, 12))

        # Table data
        table_data = [
            [
                "Staff Name",
                "Exact Login",
                "Exact Logout",
                "Public Hol",
                "Deliveries",
                "Hours Worked",
            ]
        ]

        for r in results:
            full_name = (
                f"{r.get('emp_first_name','')} {r.get('emp_last_name','')}".strip()
            )
            try:
                hours = float(r.get("hours_worked", 0) or 0)
            except ValueError:
                hours = 0.0

            table_data.append(
                [
                    full_name,
                    r.get("login_timestamp", "-"),
                    r.get("logout_timestamp", "-"),
                    "Yes" if r.get("is_public_holiday") else "No",
                    str(r.get("deliveries", 0)),
                    f"{hours:.2f}",
                ]
            )

        if len(table_data) == 1:
            table_data.append(["No shifts found", "", "", "", "", ""])

        table = Table(
            table_data,
            repeatRows=1,
            colWidths=[
                120,
                90,
                90,
                75,
                70,
                90,
            ],  # proportional modern column sizing
        )

        table.setStyle(
            TableStyle(
                [
                    # --- HEADER STYLING ---
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor("#1a73e8"),
                    ),  # Google blue tone
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 11),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                    ("TOPPADDING", (0, 0), (-1, 0), 6),
                    # --- ROW STYLING ---
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#222222")),
                    ("ALIGN", (0, 1), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 1), (-1, -1), "MIDDLE"),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.25,
                        colors.HexColor("#CCCCCC"),
                    ),
                    # --- ZEBRA STRIPING (alternating row shading) ---
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                    (
                        "BACKGROUND",
                        (0, 2),
                        (-1, -1),
                        colors.HexColor("#f7faff"),
                    ),  # pale blue tint
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [
                            colors.white,
                            colors.HexColor("#f7faff"),  # alternate striping
                        ],
                    ),
                    # --- CELL SPACING + PAD LOOK ---
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        elements.append(table)
        elements.append(Spacer(1, 12))

        doc.build(
            elements,
            onFirstPage=lambda c, d: draw_page_meta(c, d, store.code),
            onLaterPages=lambda c, d: draw_page_meta(c, d, store.code),
        )

        pdf = buffer.getvalue()
        buffer.close()

        return pdf

    except Exception as e:

        logger.critical(f"Shift log PDF build failure: {e}")

        raise ReportBuildError("Failed to generate shift log report PDF.")


def build_account_summary_pdf(
    store,
    start,
    end,
    summaries,
    ignore_no_hours,
    filter_list,
    min_hours=None,
    min_deliveries=None,
    sort_by="name",
    sort_desc=False,
) -> bytes:
    try:

        if min_hours is not None:
            summaries = [
                s for s in summaries if float(s.get("hours_total") or 0) >= min_hours
            ]

        if min_deliveries is not None:
            summaries = [
                s for s in summaries if int(s.get("deliveries") or 0) >= min_deliveries
            ]

        sort_keys = {
            "name": lambda s: s.get("name", ""),
            "weekday": lambda s: float(s.get("hours_weekday") or 0),
            "weekend": lambda s: float(s.get("hours_weekend") or 0),
            "public_holiday": lambda s: float(s.get("hours_public_holiday") or 0),
            "deliveries": lambda s: int(s.get("deliveries") or 0),
            "total": lambda s: float(s.get("hours_total") or 0),
            "age": lambda s: int(s.get("age") or 0),
        }

        if sort_by in sort_keys:
            summaries.sort(key=sort_keys[sort_by], reverse=sort_desc)

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=24,
            bottomMargin=36,
        )

        elements = []
        styles = getSampleStyleSheet()

        generated_time = datetime.now().strftime("%d %b %Y %H:%M:%S")
        start_fmt = datetime.strptime(start, "%Y-%m-%d").strftime("%d %b %Y")
        end_fmt = datetime.strptime(end, "%Y-%m-%d").strftime("%d %b %Y")

        elements = []
        styles = getSampleStyleSheet()

        # Header
        elements.append(
            Paragraph(f"Account Summary Report — {store.name}", styles["Title"])
        )
        elements.append(Spacer(1, 12))
        meta_line = (
            f"<b>Date Range:</b> {start_fmt} → {end_fmt} &nbsp;&nbsp;&nbsp; "
            f"<b>Store:</b> {store.code} &nbsp;&nbsp;&nbsp; "
            f"<b>Generated:</b> {generated_time}"
        )

        elements.append(Paragraph(meta_line, styles["Normal"]))
        elements.append(Spacer(1, 12))

        if ignore_no_hours:
            elements.append(
                Paragraph("Ignored employees with no hours worked", styles["Normal"])
            )

        if filter_list:
            elements.append(
                Paragraph(
                    f"Filtered Employees: {', '.join(filter_list)}",
                    styles["Normal"],
                )
            )

        elements.append(Spacer(1, 12))

        # Table header
        table_data = [
            [
                "Staff Name",
                "Weekday Hrs",
                "Weekend Hrs",
                "Public Hol Hrs",
                "Deliveries",
                "Total Hours",
                "Age",
            ]
        ]

        total_weekday = 0.0
        total_weekend = 0.0
        total_public = 0.0
        total_deliveries = 0
        total_hours = 0.0
        # Rows
        for summary in summaries:

            weekday = float(summary.get("hours_weekday") or 0)
            weekend = float(summary.get("hours_weekend") or 0)
            public_hol = float(summary.get("hours_public_holiday") or 0)
            deliveries = int(summary.get("deliveries") or 0)
            total = float(summary.get("hours_total") or 0)

            # accumulate totals
            total_weekday += weekday
            total_weekend += weekend
            total_public += public_hol
            total_deliveries += deliveries
            total_hours += total

            table_data.append(
                [
                    summary.get("name", "-"),
                    summary.get("hours_weekday", 0),
                    summary.get("hours_weekend", 0),
                    summary.get("hours_public_holiday", 0),
                    summary.get("deliveries", 0),
                    summary.get("hours_total", 0),
                    summary.get("age", "N/A"),
                ]
            )

        table_data.append(
            [
                "TOTAL",
                f"{total_weekday:.2f}",
                f"{total_weekend:.2f}",
                f"{total_public:.2f}",
                total_deliveries,
                f"{total_hours:.2f}",
                "",
            ]
        )

        if len(table_data) == 1:
            table_data.append(["No records found", "", "", "", "", "", ""])

        table = Table(
            table_data,
            repeatRows=1,
            colWidths=[100, 80, 80, 90, 60, 90, 50],
        )

        table.setStyle(
            TableStyle(
                [
                    # --- HEADER STYLING ---
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor("#1a73e8"),
                    ),  # Google blue tone
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 11),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                    ("TOPPADDING", (0, 0), (-1, 0), 6),
                    # --- ROW STYLING ---
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#222222")),
                    ("ALIGN", (0, 1), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 1), (-1, -1), "MIDDLE"),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.25,
                        colors.HexColor("#CCCCCC"),
                    ),
                    # --- ZEBRA STRIPING (alternating row shading) ---
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                    (
                        "BACKGROUND",
                        (0, 2),
                        (-1, -1),
                        colors.HexColor("#f7faff"),
                    ),  # pale blue tint
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [
                            colors.white,
                            colors.HexColor("#f7faff"),  # alternate striping
                        ],
                    ),
                    # --- CELL SPACING + PAD LOOK ---
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        elements.append(table)

        doc.build(
            elements,
            onFirstPage=lambda c, d: draw_page_meta(c, d, store.code),
            onLaterPages=lambda c, d: draw_page_meta(c, d, store.code),
        )

        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes

    except Exception as e:
        logger.critical(f"Account Summary PDF build failure: {e}")
        raise ReportBuildError("Failed to generate Account Summary PDF.")


def build_weekly_roster_matrix(
    store_id, week, filter_names=None, hide_resigned=False, roles_filter=None
):
    """
    Converts API roster structure into printable matrix with role info.
    """
    store = Store.objects.get(pk=store_id)

    filter_names = filter_names or []

    data = controllers.get_all_store_schedules(
        store=store,
        week=week,
        offset=0,
        limit=200,
        include_deleted=False,
        hide_deactivated=False,
        hide_resigned=False,
        sort_field="name",
        filter_names=filter_names,
        filter_roles=roles_filter or None,
    )

    schedule_map = data.get("schedule", {})
    week_start = data.get("week_start")

    week_dates = [week_start + timedelta(days=i) for i in range(7)]

    daily_totals = {
        "Mon": 0.0,
        "Tue": 0.0,
        "Wed": 0.0,
        "Thu": 0.0,
        "Fri": 0.0,
        "Sat": 0.0,
        "Sun": 0.0,
    }

    roster = []

    for full_name, info in schedule_map.items():

        row = {
            "name": full_name,
            "Mon": "-",
            "Tue": "-",
            "Wed": "-",
            "Thu": "-",
            "Fri": "-",
            "Sat": "-",
            "Sun": "-",
        }

        emp_roster = info.get("roster", {})

        for d in week_dates:
            day_key = d.isoformat()
            shift_list = emp_roster.get(day_key, [])

            if shift_list:
                formatted = []
                for s in shift_list:
                    start_t = datetime.strptime(s["start_time"], "%H:%M")
                    end_t = datetime.strptime(s["end_time"], "%H:%M")

                    hours = (end_t - start_t).total_seconds() / 3600

                    day_name = d.strftime("%a")
                    daily_totals[day_name] += hours

                    time_part = f"{s['start_time']}–{s['end_time']}"

                    if s.get("role_name"):
                        formatted.append(f"{time_part}\n<i>{s['role_name']}</i>")
                    else:
                        formatted.append(time_part)

                row[d.strftime("%a")] = "\n".join(formatted)

        roster.append(row)

    return roster, week_start, week_start + timedelta(days=6), daily_totals


def build_roster_report_pdf(store, week, filter_names, roles_filter) -> bytes:
    try:
        roster, week_start, week_end, daily_totals = build_weekly_roster_matrix(
            store.id, week, filter_names=filter_names, roles_filter=roles_filter
        )

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=24,
            leftMargin=24,
            topMargin=24,
            bottomMargin=30,
        )

        # --- HEADER ---
        generated_time = datetime.now().strftime("%d %b %Y %H:%M:%S")
        week_start_fmt = week_start.strftime("%d %b %Y")
        week_end_fmt = week_end.strftime("%d %b %Y")

        elements = []
        styles = getSampleStyleSheet()

        # Header
        elements.append(
            Paragraph(f"Account Summary Report — {store.name}", styles["Title"])
        )
        elements.append(Spacer(1, 12))
        meta_line = (
            f"<b>Week:</b> {week_start_fmt} → {week_end_fmt} &nbsp;&nbsp;&nbsp; "
            f"<b>Store:</b> {store.code} &nbsp;&nbsp;&nbsp; "
            f"<b>Generated:</b> {generated_time}"
        )

        elements.append(Paragraph(meta_line, styles["Normal"]))
        elements.append(Spacer(1, 12))

        # --- TABLE DATA ---
        week_dates = [week_start + timedelta(days=i) for i in range(7)]

        header = ["Employee"]

        for d in week_dates:
            day_label = d.strftime("%a")
            date_label = d.strftime("%d/%m")
            header.append(f"{day_label}\n{date_label}")

        data = [header]

        for emp in roster:
            row = [
                Paragraph(
                    f"<b>{emp['name']}</b>",
                    styles["Normal"],
                )
            ]
            for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
                row.append(
                    Paragraph(
                        emp[day].replace("\n", "<br/>") or "-",
                        styles["Normal"],
                    )
                )
            data.append(row)

        weekly_total = sum(daily_totals.values())

        totals_row = [Paragraph("<b>Total Hours</b>", styles["Normal"])]

        for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            totals_row.append(
                Paragraph(f"<b>{daily_totals[day]:.2f}</b>", styles["Normal"])
            )

        data.append(totals_row)

        table = Table(
            data,
            repeatRows=1,
            colWidths=[120] + [95] * 7,
        )

        table.setStyle(
            TableStyle(
                [
                    # --- HEADER ---
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a73e8")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 11),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, 0), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    # --- BODY ---
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    # --- GRID ---
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.25,
                        colors.HexColor("#cccccc"),
                    ),
                    # --- ZEBRA STRIPING ---
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [
                            colors.white,
                            colors.HexColor("#f7faff"),
                        ],
                    ),
                    # --- CELL PADDING ---
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 1), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
                ]
            )
        )

        elements.append(table)

        elements.append(Spacer(1, 10))
        elements.append(
            Paragraph(
                f"<b>Weekly Total:</b> {weekly_total:.2f} hrs",
                styles["Normal"],
            )
        )

        doc.build(
            elements,
            onFirstPage=lambda c, d: draw_page_meta(c, d, store.code),
            onLaterPages=lambda c, d: draw_page_meta(c, d, store.code),
        )

        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data

    except Exception as e:
        logger.critical(f"Roster PDF build failure: {e}")
        raise ReportBuildError("Failed to generate Roster report PDF.")
