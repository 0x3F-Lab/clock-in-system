from io import BytesIO
from datetime import datetime, timedelta
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import api.controllers as controllers
from auth_app.models import Store


class ReportBuildError(Exception):

    pass


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
            "login": lambda r: r.get("login_timestamp") or "",
            "logout": lambda r: r.get("logout_timestamp") or "",
        }

        if sort_by in sort_keys:
            results.sort(key=sort_keys[sort_by], reverse=sort_desc)

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=54,
            bottomMargin=36,
        )

        elements = []
        styles = getSampleStyleSheet()

        # Header
        elements.append(Paragraph(f"Shift Logs Report — {store.name}", styles["Title"]))
        elements.append(Paragraph(f"Date Range: {start} to {end}", styles["Normal"]))
        elements.append(Paragraph(f"Store Code: {store.code}"))
        elements.append(Spacer(1, 20))

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
        # Timestamp footer
        generated_time = datetime.now().strftime("%d %b %Y %H:%M:%S")
        timestamp = f"<font size='8' color='#888888'>Generated: {generated_time}</font>"
        elements.append(Paragraph(timestamp, styles["Normal"]))

        doc.build(elements)

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
            topMargin=54,
            bottomMargin=36,
        )

        elements = []
        styles = getSampleStyleSheet()

        elements.append(
            Paragraph(f"Account Summary Report — {store.name}", styles["Title"])
        )
        elements.append(Paragraph(f"Date Range: {start} to {end}", styles["Normal"]))
        elements.append(Paragraph(f"Store Code: {store.code}"))

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

        # Rows
        for summary in summaries:
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

        if len(table_data) == 1:
            table_data.append(["No records found", "", "", "", "", "", ""])

        table = Table(
            table_data,
            repeatRows=1,
            colWidths=[100, 80, 80, 90, 60, 90, 50],  # adjust as needed
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

        # Footer timestamp
        generated_time = datetime.now().strftime("%d %b %Y %H:%M:%S")
        elements.append(
            Paragraph(
                f"<font size=8 color='#888888'>Generated: {generated_time}</font>",
                styles["Normal"],
            )
        )

        doc.build(elements)

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
    week_start = data.get("week_start")  # always Monday

    week_dates = [week_start + timedelta(days=i) for i in range(7)]

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
                    time_part = f"{s['start_time']}–{s['end_time']}"

                    if s.get("role_name"):
                        formatted.append(f"{time_part}\n<i>{s['role_name']}</i>")
                    else:
                        formatted.append(time_part)

                row[d.strftime("%a")] = "\n".join(formatted)

        roster.append(row)

    return roster, week_start, week_start + timedelta(days=6)


def build_roster_report_pdf(store, week, filter_names, roles_filter) -> bytes:
    try:
        roster, week_start, week_end = build_weekly_roster_matrix(
            store.id, week, filter_names=filter_names, roles_filter=roles_filter
        )

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=24,
            leftMargin=24,
            topMargin=30,
            bottomMargin=30,
        )

        elements = []
        styles = getSampleStyleSheet()

        # --- HEADER ---
        elements.append(
            Paragraph(
                f"<b>Weekly Roster Report</b> — {store.name}",
                styles["Title"],
            )
        )
        elements.append(
            Paragraph(
                f"Week: {week_start.strftime('%d %b %Y')} → {week_end.strftime('%d %b %Y')}",
                styles["Normal"],
            )
        )
        elements.append(
            Paragraph(f"<font color='#555555'>Store Code: {store.code}</font>")
        )
        elements.append(Spacer(1, 18))

        # --- TABLE DATA ---
        data = [["Employee", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]]

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

        # --- FOOTER ---
        elements.append(Spacer(1, 14))
        generated = datetime.now().strftime("%d %b %Y %H:%M:%S")
        elements.append(
            Paragraph(
                f"<font size='8' color='#888888'>Generated: {generated}</font>",
                styles["Normal"],
            )
        )

        doc.build(elements)

        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data

    except Exception as e:
        logger.critical(f"Roster PDF build failure: {e}")
        raise ReportBuildError("Failed to generate Roster report PDF.")
