from odoo import http  # type: ignore
from odoo.http import request  # type: ignore
import io
import xlsxwriter  # type: ignore
from datetime import datetime


class SalesReportExcelController(http.Controller):
    @http.route("/sales_report/excel", type="http", auth="user")
    def export_sales_report_excel(
        self, group_by=None, report_type=None, date_from=None, date_to=None
    ):
        SaleReport = request.env["mgs_sale.sale_report"].sudo()

        # --- 1️⃣ Collect filters ---
        wizard_vals = {
            "group_by": group_by,
            "report_type": report_type,
            "date_from": date_from,
            "date_to": date_to,
        }

        optional_fields = [
            "user_id",
            "partner_id",
            "company_id",
            "team_id",
            "product_id",
            "categ_id",
            "parent_categ_id",
        ]

        for field in optional_fields:
            value = request.params.get(field)
            if value:
                wizard_vals[field] = int(value)

        wizard = SaleReport.create(wizard_vals)

        # --- 2️⃣ Select data method ---
        if report_type == "detail":
            data = wizard.get_detailed_sales_data()
        elif report_type == "summary":
            data = wizard.get_summary_sales_data()
        else:
            return request.make_response("Invalid report type provided.")

        if not data:
            return request.make_response("No data found for the given filters.")

        # --- 3️⃣ Setup Excel ---
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Sales Report")

        # --- 4️⃣ Formats ---
        header_format = workbook.add_format(
            {"bold": True, "bg_color": "#DCE6F1", "border": 1, "align": "center"}
        )
        text_format = workbook.add_format({"border": 1})
        number_format = workbook.add_format({"num_format": "#,##0.00", "border": 1})
        bold_format = workbook.add_format({"bold": True, "border": 1})
        group_format = workbook.add_format(
            {"bold": True, "bg_color": "#E6E6E6", "border": 1}
        )

        # --- 5️⃣ Column widths ---
        sheet.set_column("A:A", 12)
        sheet.set_column("B:B", 18)
        sheet.set_column("C:C", 22)
        sheet.set_column("D:H", 14)

        # --- 6️⃣ Report header ---
        company = request.env.company.name
        title = f"Sales {report_type.title()} Report (By {group_by.capitalize()})"  # type: ignore
        date_range = f"From {date_from or '...'} To {date_to or '...'}"

        sheet.merge_range(
            "A1:H1", company, workbook.add_format({"bold": True, "font_size": 14})
        )
        sheet.merge_range(
            "A2:H2", title, workbook.add_format({"bold": True, "font_size": 12})
        )
        sheet.merge_range(
            "A3:H3", date_range, workbook.add_format({"italic": True, "font_size": 10})
        )
        row = 5

        # --- 7️⃣ Write headers ---
        if report_type == "detail":
            headers = [
                "Order Date",
                "Order",
                "Customer",
                "Product",
                "Ordered Qty",
                "Delivered Qty",
                "Invoiced",
                "Rate",
                "Amount",
            ]
        else:
            headers = [
                group_by.capitalize(),  # type: ignore
                "Ordered Qty",
                "Delivered Qty",
                "Invoiced",
                "Amount",
            ]

        for col, header in enumerate(headers):
            sheet.write(row, col, header, header_format)
        row += 1

        # --- 8️⃣ Populate rows ---
        grand_totals = {
            "amount": 0,
            "ordered": 0,
            "delivered": 0,
            "invoiced": 0,
        }

        if report_type == "detail":
            for section in data:
                group_name = section["group"]

                # Group title
                sheet.merge_range(
                    row,
                    0,
                    row,
                    len(headers) - 1,
                    f"{group_by.title()}: {group_name}",  # type: ignore
                    group_format,
                )
                row += 1

                group_totals = {
                    "amount": 0,
                    "ordered": 0,
                    "delivered": 0,
                    "invoiced": 0,
                }

                for line in section["orders"]:
                    sheet.write(row, 0, str(line["order_date"]), text_format)
                    sheet.write(row, 1, line["order_name"], text_format)
                    sheet.write(row, 2, line["customer"], text_format)
                    sheet.write(row, 3, line["product"], text_format)
                    sheet.write_number(row, 4, line["ordered_qty"], number_format)
                    sheet.write_number(row, 5, line["delivered_qty"], number_format)
                    sheet.write_number(row, 6, line["invoiced_qty"], number_format)
                    sheet.write_number(row, 7, line["rate"], number_format)
                    sheet.write_number(row, 8, line["amount"], number_format)

                    # Update group totals
                    group_totals["amount"] += line["amount"]
                    group_totals["ordered"] += line["ordered_qty"]
                    group_totals["delivered"] += line["delivered_qty"]
                    group_totals["invoiced"] += line["invoiced_qty"]
                    row += 1

                # --- Group subtotal ---
                sheet.write(row, 3, "Group Total", bold_format)
                sheet.write_number(row, 4, group_totals["ordered"], number_format)
                sheet.write_number(row, 5, group_totals["delivered"], number_format)
                sheet.write_number(row, 6, group_totals["invoiced"], number_format)
                sheet.write_number(
                    row,
                    7,
                    group_totals["rate"] if "rate" in group_totals else 0,
                    number_format,
                )
                sheet.write_number(row, 8, group_totals["amount"], number_format)
                row += 2

                # Accumulate grand totals
                for k in grand_totals:
                    grand_totals[k] += group_totals[k]

        else:  # summary
            for section in data:
                group_name = section["group_name"]
                sheet.write(row, 0, group_name, text_format)
                sheet.write_number(row, 1, section["total_ordered_qty"], number_format)
                sheet.write_number(
                    row, 2, section["total_delivered_qty"], number_format
                )
                sheet.write_number(row, 3, section["total_invoiced_qty"], number_format)
                sheet.write_number(row, 4, section["total_amount"], number_format)

                # Update grand totals
                grand_totals["amount"] += section["total_amount"]
                grand_totals["ordered"] += section["total_ordered_qty"]
                grand_totals["delivered"] += section["total_delivered_qty"]
                grand_totals["invoiced"] += section["total_invoiced_qty"]

                row += 1

        # --- 9️⃣ Grand total ---
        sheet.write(
            row, 0 if report_type == "summary" else 3, "Grand Total", bold_format
        )
        col_offset = 1 if report_type == "summary" else 4
        sheet.write_number(row, col_offset + 0, grand_totals["ordered"], number_format)
        sheet.write_number(
            row, col_offset + 1, grand_totals["delivered"], number_format
        )
        sheet.write_number(row, col_offset + 2, grand_totals["invoiced"], number_format)
        sheet.write_number(row, col_offset + 3, grand_totals["amount"], number_format)

        # --- 10️⃣ Finalize ---
        workbook.close()
        output.seek(0)

        if date_from:
            date_from_dt = datetime.strptime(date_from, "%Y-%m-%d")
            date_from_str = date_from_dt.strftime("%Y_%b_%d")
        else:
            date_from_str = "start"

        if date_to:
            date_to_dt = datetime.strptime(date_to, "%Y-%m-%d")
            date_to_str = date_to_dt.strftime("%Y_%b_%d")
        else:
            date_to_str = "end"

        filename = f"{group_by.capitalize()}_sales_{report_type}_report_from_{date_from_str}_to_{date_to_str}.xlsx"  # type:ignore

        headers = [
            (
                "Content-Type",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            ("Content-Disposition", f'attachment; filename="{filename}"'),
        ]
        return request.make_response(output.read(), headers=headers)
