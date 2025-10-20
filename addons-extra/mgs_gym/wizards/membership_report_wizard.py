from odoo import models, fields  # type: ignore
from odoo.exceptions import UserError  # type: ignore
from io import BytesIO
import xlsxwriter  # type: ignore
import base64


class GymMembership(models.Model):
    _name = "mgs_gym.membership_report_wizard"

    branch_id = fields.Many2one(
        "mgs_gym.branch",
        string="Branch",
    )
    gender = fields.Selection([("male", "Male"), ("female", "Female")])
    shift_id = fields.Many2one(
        "mgs_gym.shift",
        string="Shift",
        domain="[('branch_id', '=', branch_id)]",
    )

    recurrence_unit = fields.Selection(
        [
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("yearly", "Yearly"),
        ],
        string="Package",
    )
    state_id = fields.Many2one(
        "mgs_gym.membership_state", string="State", domain="[('name', '!=', 'Draft')]"
    )

    def action_print_report(self):
        domain = [("state", "!=", "Draft")]

        if self.branch_id:
            domain.append(("branch_id", "=", self.branch_id))

        if self.shift_id:
            domain.append(("shift_id", "=", self.shift_id))

        if self.state_id:
            domain.append(("state_id", "=", self.state_id))

        if self.gender:
            domain.append(("gender", "=", self.gender))

        if self.recurrence_unit:
            domain.append(("recurrence_unit", "=", self.recurrence_unit))

        memberships = self.env["mgs_gym.membership"].search(domain, order="id desc")

        if not memberships:
            raise UserError("No Memberships found for the selected criteria.")

        report_action_xml_id = "mgs_gym.action_membership_report"

        return self.env.ref(report_action_xml_id).report_action(memberships)

    def action_generate_excel(self):
        """Generate an Excel (.xlsx) file for the selected membership filters and return a download URL."""
        self.ensure_one()

        domain = [("state", "!=", "Draft")]

        if self.branch_id:
            domain.append(("branch_id", "=", self.branch_id.id))

        if self.shift_id:
            domain.append(("shift_id", "=", self.shift_id.id))

        if self.state_id:
            domain.append(("state_id", "=", self.state_id.id))

        if self.gender:
            domain.append(("gender", "=", self.gender))

        if self.recurrence_unit:
            domain.append(("recurrence_unit", "=", self.recurrence_unit))

        memberships = self.env["mgs_gym.membership"].search(domain, order="id desc")

        if not memberships:
            raise UserError("No Memberships found for the selected criteria.")

        # Prepare workbook
        fp = BytesIO()
        workbook = xlsxwriter.Workbook(fp)
        sheet = workbook.add_worksheet("Memberships")

        # Formats
        header_fmt = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#0d6efd",
                "font_color": "white",
                "border": 1,
                "align": "center",
            }
        )
        text_fmt = workbook.add_format({"border": 1})
        num_fmt = workbook.add_format(
            {"num_format": "#,##0.00", "border": 1, "align": "right"}
        )
        date_fmt = workbook.add_format({"num_format": "yyyy-mm-dd", "border": 1})

        # Headers (mirror the PDF columns in reports/membership_report.xml)
        headers = [
            "Ref",
            "Branch",
            "Shift",
            "Gender",
            "State",
            "Service",
            "Package",
            "Amount",
            "Discounted Amount",
            "Refunded Amount",
            "Date of Expiry",
        ]

        # Set column widths
        sheet.set_column("A:A", 20)
        sheet.set_column("B:B", 18)
        sheet.set_column("C:C", 14)
        sheet.set_column("D:D", 10)
        sheet.set_column("E:E", 14)
        sheet.set_column("F:F", 20)
        sheet.set_column("G:G", 12)
        sheet.set_column("H:J", 15)
        sheet.set_column("K:K", 14)

        # Write headers
        for col, h in enumerate(headers):
            sheet.write(0, col, h, header_fmt)

        row = 1
        total_amount = 0.0
        total_discounted = 0.0
        total_refunded = 0.0

        for rec in memberships:
            col = 0
            sheet.write(row, col, rec.name or "", text_fmt)
            col += 1
            sheet.write(row, col, rec.branch_id.name if rec.branch_id else "", text_fmt)
            col += 1
            sheet.write(row, col, rec.shift_id.name if rec.shift_id else "", text_fmt)
            col += 1
            sheet.write(row, col, rec.gender or "", text_fmt)
            col += 1
            sheet.write(
                row,
                col,
                rec.state_id.name if rec.state_id else rec.state or "",
                text_fmt,
            )
            col += 1
            sheet.write(
                row, col, rec.service_id.name if rec.service_id else "", text_fmt
            )
            col += 1
            sheet.write(row, col, rec.recurrence_unit or "", text_fmt)
            col += 1
            sheet.write_number(row, col, rec.amount or 0.0, num_fmt)
            total_amount += rec.amount or 0.0
            col += 1
            sheet.write_number(row, col, rec.discounted_amount or 0.0, num_fmt)
            total_discounted += rec.discounted_amount or 0.0
            col += 1
            # refunded amount: use refund_due if refunded (or show refund_due regardless)
            refunded_val = rec.refund_due or 0.0
            sheet.write_number(row, col, refunded_val, num_fmt)
            total_refunded += refunded_val
            col += 1
            # next_invoice_date
            if rec.next_invoice_date:
                sheet.write(row, col, rec.next_invoice_date, date_fmt)
            else:
                sheet.write(row, col, "", text_fmt)

            row += 1

        # Totals row
        sheet.write(row, 0, "Grand Total", header_fmt)
        # leave some merged cells or just write totals in numeric columns
        sheet.write_blank(row, 1, None, header_fmt)
        sheet.write_blank(row, 2, None, header_fmt)
        sheet.write_blank(row, 3, None, header_fmt)
        sheet.write_blank(row, 4, None, header_fmt)
        sheet.write_blank(row, 5, None, header_fmt)
        sheet.write_blank(row, 6, None, header_fmt)
        sheet.write_number(row, 7, total_amount, num_fmt)
        sheet.write_number(row, 8, total_discounted, num_fmt)
        sheet.write_number(row, 9, total_refunded, num_fmt)

        workbook.close()
        out = base64.b64encode(fp.getvalue())
        fp.close()

        filename = f"membership_report_{fields.Date.context_today(self).strftime('%Y%m%d')}.xlsx"

        attachment = self.env["ir.attachment"].create(
            {
                "name": filename,
                "type": "binary",
                "datas": out,
                "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
        )

        return {
            "type": "ir.actions.act_url",
            "target": "self",
            "url": f"/web/content/{attachment.id}?download=true",
        }
