from odoo import models, fields  # type: ignore
import xlsxwriter  # type: ignore
import base64
from io import BytesIO
from odoo.exceptions import UserError  # type: ignore


class SaleReport(models.TransientModel):
    _name = "mgs_sale.sale_report"
    _description = "Sale Report"

    date_from = fields.Date(
        default=fields.Date.today().replace(day=1), string="Date from", required=True
    )
    date_to = fields.Date(default=fields.Date.today(), string="Date to", required=True)
    user_id = fields.Many2one("res.users", string="User")
    partner_id = fields.Many2one("res.partner", "Partner")
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, string="Company"
    )
    team_id = fields.Many2one("crm.team", string="Sales Team")
    currency_id = fields.Many2one("res.currency", string="Currency")
    sales_tag_ids = fields.Many2many("crm.tag", string="Tags")
    product_id = fields.Many2one("product.product", string="Product")
    categ_id = fields.Many2one("product.category", string="Product category")
    parent_categ_id = fields.Many2one("product.category", string="Parent Category")
    report_type = fields.Selection(
        [("summary", "Summary"), ("detail", "Detail")],
        default="summary",
        string="Report type",
        required=True,
    )
    group_by = fields.Selection(
        [("customer", "Customer"), ("item", "Item")],
        default="customer",
        string="Group by",
        required=True,
    )

    datas = fields.Binary("File", readonly=True)
    datas_fname = fields.Char("Filename", readonly=True)

    # HELPER METHOD TO GET THE BASE DOMAIN

    def _get_base_domain(self):
        if self.date_from > self.date_to:
            raise UserError("The start date cannot be after the end date.")

        domain = [
            ("date_order", ">=", self.date_from),
            ("date_order", "<=", self.date_to),
        ]

        if self.user_id:
            domain.append(("user_id", "=", self.user_id.id))
        if self.company_id:
            domain.append(("company_id", "=", self.company_id.id))
        if self.team_id:
            domain.append(("team_id", "=", self.team_id.id))
        if self.partner_id:
            domain.append(("partner_id", "=", self.partner_id.id))
        if self.product_id:
            domain.append(("product_id", "=", self.product_id.id))
        if self.categ_id:
            domain.append(("product_id.categ_id", "=", self.categ_id.id))
        if self.parent_categ_id:
            domain.append(
                ("product_id.categ_id.parent_id", "=", self.parent_categ_id.id)
            )

        return domain

    # DETAILED CUSTOMER/ITEM REPORT GENERATOR

    def get_detailed_sales_data(self):
        CombinedReport = self.env["mgs_sale.combined_report"]
        final_data = []
        domain = self._get_base_domain()

        group_field = "partner_id" if self.group_by == "customer" else "product_id"

        grouped_data = CombinedReport.read_group(
            domain,
            fields=["price_subtotal:sum", group_field],
            groupby=[group_field],
            lazy=False,
        )

        for group in grouped_data:
            group_value = group.get(group_field)
            group_name = (
                group_value[1]
                if group_value
                else (
                    "Undefined Customer"
                    if self.group_by == "customer"
                    else "Undefined Product"
                )
            )

            group_domain = group["__domain"]
            order_lines = CombinedReport.search(group_domain)

            total_amount = sum(order_lines.mapped("price_subtotal"))
            total_ordered_qty = sum(order_lines.mapped("product_uom_qty"))
            total_delivered_qty = sum(order_lines.mapped("qty_delivered"))
            total_invoiced_qty = sum(order_lines.mapped("qty_invoiced"))

            section = {
                "group": group_name,
                "total_amount": total_amount,
                "total_ordered_qty": total_ordered_qty,
                "total_delivered_qty": total_delivered_qty,
                "total_invoiced_qty": total_invoiced_qty,
                "orders": [],
            }

            for line in order_lines:
                section["orders"].append(
                    {
                        "order_date": line.date_order.date()
                        if line.date_order
                        else None,
                        "order_name": line.order_ref or line.id,
                        "customer": line.partner_id.name or "",
                        "product": line.product_id.display_name or "",
                        "ordered_qty": line.product_uom_qty,
                        "delivered_qty": line.qty_delivered,
                        "invoiced_qty": line.qty_invoiced,
                        "rate": line.price_unit,
                        "amount": line.price_subtotal,
                        "cost": (line.product_id.standard_price * line.product_uom_qty)
                        if line.product_id
                        else 0.0,
                        "margin": getattr(line, "margin", 0.0),
                    }
                )

            final_data.append(section)

        return final_data

    # ITEM/CUSTOMER SUMMARY REPORT GENERATOR

    def get_summary_sales_data(self):
        CombinedReport = self.env["mgs_sale.combined_report"]
        domain = self._get_base_domain()
        group_field = "partner_id" if self.group_by == "customer" else "product_id"

        aggregate_fields = [
            group_field,
            "price_subtotal:sum",
            "product_uom_qty:sum",
            "qty_delivered:sum",
            "qty_invoiced:sum",
        ]

        grouped_data = CombinedReport.read_group(
            domain, fields=aggregate_fields, groupby=[group_field], lazy=False
        )

        final_data = []
        for group in grouped_data:
            group_val = group.get(group_field)
            group_name = group_val[1] if group_val else "Undefined"

            final_data.append(
                {
                    "group_name": group_name,
                    "total_amount": group.get("price_subtotal", 0.0),
                    "total_ordered_qty": group.get("product_uom_qty", 0.0),
                    "total_delivered_qty": group.get("qty_delivered", 0.0),
                    "total_invoiced_qty": group.get("qty_invoiced", 0.0),
                }
            )

        return final_data

    # PRINT REPORT METHOD, CALLS DETAIL/SUMMARY REPORT ACTIONS

    def action_print_report(self):
        if self.report_type == "detail":
            return self.env.ref(
                "mgs_sale.action_report_mgs_sale_detailed"
            ).report_action(self)
        elif self.report_type == "summary":
            return self.env.ref(
                "mgs_sale.action_report_mgs_sale_summary"
            ).report_action(self)

    # METHOD TO GENERATE EXCEL REPORT
    def action_generate_excel(self):
        # Fetch data
        if self.report_type == "summary":
            data = self.get_summary_sales_data()
        else:
            data = self.get_detailed_sales_data()

        if not data:
            raise UserError("No data found for the selected filters.")

        show_cost_margin = self.env.user.has_group("account.group_account_manager")

        fp = BytesIO()
        workbook = xlsxwriter.Workbook(fp)
        sheet = workbook.add_worksheet("Sales Report")

        # Formats
        header_fmt = workbook.add_format(
            {"bold": True, "bg_color": "#D8DCE0", "border": 1, "align": "center"}
        )
        text_fmt = workbook.add_format({"border": 1})
        num_fmt = workbook.add_format(
            {"num_format": "#,##0.00", "border": 1, "align": "right"}
        )
        total_num_fmt = workbook.add_format(
            {
                "num_format": "#,##0.00",
                "border": 1,
                "align": "right",
                "bg_color": "#F70C0C",
                "font_color": "white",
            }
        )
        group_hdr = workbook.add_format(
            {"bold": True, "bg_color": "#B2B9F7", "border": 1}
        )
        date_fmt = workbook.add_format({"num_format": "yyyy-mm-dd", "border": 1})

        # Columns and headers similar to PDF
        if self.report_type == "summary":
            headers = ["Name", "Ordered Qty", "Delivered Qty", "Invoiced Qty", "Amount"]
            sheet.set_column("A:A", 40)
            sheet.set_column("B:E", 15)
        else:
            headers = [
                "Order Date",
                "Order #",
                ("Item" if self.group_by == "customer" else "Customer"),
                "Ordered Qty",
                "Delivered Qty",
                "Invoiced Qty",
                "Rate",
                "Amount",
            ]
            if show_cost_margin:
                headers.extend(["Cost", "Margin"])  # shown per-line only
            # column widths
            sheet.set_column("A:A", 12)
            sheet.set_column("B:B", 12)
            sheet.set_column("C:C", 30)
            sheet.set_column("D:K", 12)

        # --- Report header (company, title, date range) ---
        last_col = len(headers) - 1
        company_name = (
            self.company_id.name if self.company_id else self.env.company.name
        )
        title = f"{self.group_by.capitalize()} Sales {self.report_type.title()} Report"
        date_range = f"From {self.date_from or '...'} To {self.date_to or '...'}"

        company_fmt = workbook.add_format({"bold": True, "font_size": 14})
        title_fmt = workbook.add_format({"bold": True, "font_size": 12})
        range_fmt = workbook.add_format({"italic": True, "font_size": 10})

        sheet.merge_range(0, 0, 0, last_col, company_name, company_fmt)
        sheet.merge_range(1, 0, 1, last_col, title, title_fmt)
        sheet.merge_range(2, 0, 2, last_col, date_range, range_fmt)

        # headers start after a blank row
        header_row = 4
        for col, h in enumerate(headers):
            sheet.write(header_row, col, h, header_fmt)

        row = header_row + 1
        grand = {"ordered": 0, "delivered": 0, "invoiced": 0, "amount": 0.0}

        if self.report_type == "summary":
            for line in data:
                sheet.write(row, 0, line.get("group_name") or "N/A", text_fmt)
                sheet.write_number(row, 1, line.get("total_ordered_qty", 0), num_fmt)
                sheet.write_number(row, 2, line.get("total_delivered_qty", 0), num_fmt)
                sheet.write_number(row, 3, line.get("total_invoiced_qty", 0), num_fmt)
                sheet.write_number(row, 4, line.get("total_amount", 0.0), num_fmt)

                grand["ordered"] += line.get("total_ordered_qty", 0)
                grand["delivered"] += line.get("total_delivered_qty", 0)
                grand["invoiced"] += line.get("total_invoiced_qty", 0)
                grand["amount"] += line.get("total_amount", 0.0)

                row += 1

        else:
            for section in data:
                group_name = section.get("group")
                # group header (single row, merged across all columns)
                sheet.merge_range(
                    row,
                    0,
                    row,
                    last_col,
                    f"{('Customer' if self.group_by == 'customer' else 'Item')}: {group_name}",
                    group_hdr,
                )
                row += 1

                for line in section.get("orders", []):
                    col = 0
                    od = line.get("order_date")
                    sheet.write(
                        row,
                        col,
                        od.strftime("%Y-%m-%d")
                        if hasattr(od, "strftime")
                        else (str(od) if od else ""),
                        date_fmt,
                    )
                    col += 1
                    sheet.write(row, col, line.get("order_name") or "", text_fmt)
                    col += 1
                    other = (
                        line.get("product")
                        if self.group_by == "customer"
                        else line.get("customer")
                    )
                    sheet.write(row, col, other or "", text_fmt)
                    col += 1

                    sheet.write_number(row, col, line.get("ordered_qty", 0), num_fmt)
                    col += 1
                    sheet.write_number(row, col, line.get("delivered_qty", 0), num_fmt)
                    col += 1
                    sheet.write_number(row, col, line.get("invoiced_qty", 0), num_fmt)
                    col += 1
                    sheet.write_number(row, col, line.get("rate", 0.0), num_fmt)
                    col += 1
                    sheet.write_number(row, col, line.get("amount", 0.0), num_fmt)
                    col += 1

                    if show_cost_margin:
                        sheet.write_number(row, col, line.get("cost", 0.0), num_fmt)
                        col += 1
                        sheet.write_number(row, col, line.get("margin", 0.0), num_fmt)
                        col += 1

                    grand["ordered"] += line.get("ordered_qty", 0)
                    grand["delivered"] += line.get("delivered_qty", 0)
                    grand["invoiced"] += line.get("invoiced_qty", 0)
                    grand["amount"] += line.get("amount", 0.0)
                    row += 1

                # --- Group Totals Row (once per group) ---
                total_label = f"Total ({group_name})"
                total_label_col = 0
                merge_until_col = 2  # Stretch label across first 3 columns (A:C)
                first_total_col = 3  # Ordered Qty starts at column D

                # Merge first 3 columns for the total label
                sheet.merge_range(
                    row,
                    total_label_col,
                    row,
                    merge_until_col,
                    total_label,
                    total_num_fmt,
                )

                # Fill the rest of the row (numeric totals) with same red background + white font
                sheet.write_number(
                    row,
                    first_total_col,
                    section.get("total_ordered_qty", 0),
                    total_num_fmt,
                )
                sheet.write_number(
                    row,
                    first_total_col + 1,
                    section.get("total_delivered_qty", 0),
                    total_num_fmt,
                )
                sheet.write_number(
                    row,
                    first_total_col + 2,
                    section.get("total_invoiced_qty", 0),
                    total_num_fmt,
                )
                sheet.write_number(
                    row,
                    first_total_col + 3,
                    section.get("total_amount", 0.0),
                    total_num_fmt,
                )

                # Optional: extend to cost/margin columns if visible
                if show_cost_margin:
                    sheet.write_blank(row, first_total_col + 4, None, total_num_fmt)
                    sheet.write_blank(row, first_total_col + 5, None, total_num_fmt)

                row += 2

        # grand totals
        sheet.write(row, 0, "Grand Total", header_fmt)
        sheet.write_number(row, 1, grand["ordered"], total_num_fmt)
        sheet.write_number(row, 2, grand["delivered"], total_num_fmt)
        sheet.write_number(row, 3, grand["invoiced"], total_num_fmt)
        sheet.write_number(row, 4, grand["amount"], total_num_fmt)

        workbook.close()
        out = base64.b64encode(fp.getvalue())
        filename = f"{self.group_by.capitalize()}_{self.report_type.capitalize()}_Sales_Report.xlsx"
        self.write({"datas": out, "datas_fname": filename})
        fp.close()

        return {
            "type": "ir.actions.act_url",
            "target": "self",
            "url": f"/web/content/?model={self._name}&id={self.id}&field=datas&download=true&filename={filename}",
        }
