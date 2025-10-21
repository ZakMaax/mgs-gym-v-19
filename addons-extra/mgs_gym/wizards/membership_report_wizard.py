from odoo import models, api, fields  # type: ignore
from odoo.exceptions import UserError  # type: ignore
from io import BytesIO
import xlsxwriter  # type: ignore
import base64


class GymMembershipReportWizard(models.TransientModel):
    _name = "mgs_gym.membership_report_wizard"
    _description = "Membership Report Wizard"

    branch_id = fields.Many2one(
        "mgs_gym.branch",
        string="Branch",
        domain=lambda self: [("id", "in", self.env.user.branch_ids.ids)],
    )
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

    @api.model
    def create(self, vals_list):
        """Require branch for non-admin users."""
        user = self.env.user
        is_admin = user.has_group("base.group_system")

        for vals in vals_list:
            # If user is not admin and did not select a branch, raise error
            if not is_admin and not vals.get("branch_id"):
                raise UserError("You must select a branch to generate this report.")

        return super(GymMembershipReportWizard, self).create(vals_list)

    def action_print_report(self):
        domain = [("state", "!=", "Draft")]

        if self.branch_id:
            domain.append(("branch_id", "=", self.branch_id.id))

        if self.shift_id:
            domain.append(("shift_id", "=", self.shift_id.id))

        if self.state_id:
            domain.append(("state_id", "=", self.state_id.id))

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
            sheet.write(row, col, rec.branch_id.gender or "", text_fmt)
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

            amount_val = float(rec.amount or 0.0)

            # --- START FIX: Correctly determine discounted_val (collected revenue) ---
            if rec.discount_percent and rec.discount_percent > 0.0:
                # Calculate discounted price
                discounted_val = round(
                    amount_val - (amount_val * rec.discount_percent / 100.0), 2
                )
            else:
                # If no discount, the collected amount is the full original amount
                discounted_val = amount_val
            # --- END FIX ---

            sheet.write_number(row, col, discounted_val or 0.0, num_fmt)
            total_discounted += discounted_val or 0.0
            col += 1

            # refunded amount: use refund_due
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

        # Totals row (Grand Total for Amount, Discounted Amount, and Refunded Amount)
        total_fmt = workbook.add_format(
            {"bold": True, "border": 1, "bg_color": "#d9e3f1"}
        )

        # Merge cells A to G for "Grand Total" label
        sheet.merge_range(row, 0, row, 6, "Grand Total", total_fmt)

        # Write totals
        sheet.write_number(row, 7, total_amount, num_fmt)
        sheet.write_number(row, 8, total_discounted, num_fmt)
        sheet.write_number(row, 9, total_refunded, num_fmt)

        # Write blank formatted cell for the last column
        sheet.write_blank(row, 10, None, num_fmt)

        # Net profit row: revenue after discounts minus refunds.
        net_profit = (total_discounted or 0.0) - (total_refunded or 0.0)

        profit_fmt = workbook.add_format(
            {
                "bold": True,
                "border": 1,
                "num_format": "#,##0.00",
                "font_color": "#0b8457",  # Dark Green
                "bg_color": "#e2f0d9",  # Light Green Background
                "align": "right",
            }
        )

        profit_row = row + 1

        # Merge cells A to G (0 to 6) for the "Net Profit" label
        sheet.merge_range(
            profit_row,
            0,
            profit_row,
            6,
            "Net Profit (Collected Revenue - Refunds)",
            profit_fmt,
        )

        # Write the Net Profit value under the "Amount" column (Index 7)
        sheet.write_number(profit_row, 7, net_profit, profit_fmt)

        # Write blank formatted cells for the remaining columns (Index 8, 9, 10)
        sheet.write_blank(profit_row, 8, None, profit_fmt)
        sheet.write_blank(profit_row, 9, None, profit_fmt)
        sheet.write_blank(profit_row, 10, None, profit_fmt)

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
