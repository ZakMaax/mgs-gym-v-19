from odoo import models, fields  # type: ignore
from odoo.exceptions import UserError  # type: ignore
from io import BytesIO
import xlsxwriter  # type: ignore
import base64


class MeasurementReportWizard(models.TransientModel):
    _name = "mgs_gym.measurement_report_wizard"
    _description = "Measurements Report Wizard"

    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        string="Client",
        domain=[("is_gym_member", "=", True)],
    )
    date_from = fields.Date(string="Date from")
    date_to = fields.Date(string="Date to")

    def action_print_report(self):
        self.ensure_one()

        domain = [("partner_id", "=", self.partner_id.id)]

        if self.date_from:
            domain.append(("date", ">=", self.date_from))

        if self.date_to:
            domain.append(("date", "<=", self.date_to))

        measurements = self.env["mgs_gym.measurement"].search(domain, order="date desc")

        if not measurements:
            raise UserError("No Measurements found for the selected criteria.")

        report_action_xml_id = "mgs_gym.action_measurement_report"

        data = {
            "date_from": self.date_from,
            "date_to": self.date_to,
            "partner_name": self.partner_id.name,
            "branch_name": self.partner_id.branch_id.name
            if self.partner_id.branch_id
            else "N/A",
        }
        return self.env.ref(report_action_xml_id).report_action(measurements, data=data)

    def action_generate_excel(self):
        """Generate an Excel file with measurement records for the selected partner and date range."""
        self.ensure_one()

        domain = [("partner_id", "=", self.partner_id.id)]
        if self.date_from:
            domain.append(("date", ">=", self.date_from))
        if self.date_to:
            domain.append(("date", "<=", self.date_to))

        measurements = self.env["mgs_gym.measurement"].search(domain, order="date desc")

        if not measurements:
            raise UserError("No Measurements found for the selected criteria.")

        fp = BytesIO()
        workbook = xlsxwriter.Workbook(fp)
        sheet = workbook.add_worksheet("Measurements")

        # formats
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
        date_fmt = workbook.add_format({"num_format": "yyyy-mm-dd", "border": 1})

        headers = ["Ref", "Date", "Weight", "Height", "BMI", "BMI Desc"]
        sheet.set_column("A:A", 20)
        sheet.set_column("B:B", 14)
        sheet.set_column("C:D", 12)
        sheet.set_column("E:E", 10)
        sheet.set_column("F:F", 20)

        for col, h in enumerate(headers):
            sheet.write(0, col, h, header_fmt)

        row = 1
        for rec in measurements:
            sheet.write(row, 0, rec.name or "", text_fmt)
            sheet.write(row, 1, rec.date or "", date_fmt if rec.date else text_fmt)
            sheet.write(row, 2, rec.weight or 0.0, text_fmt)
            sheet.write(row, 3, rec.height or 0.0, text_fmt)
            sheet.write(row, 4, rec.bmi or "", text_fmt)
            sheet.write(row, 5, rec.bmi_text or "", text_fmt)
            row += 1

        workbook.close()
        out = base64.b64encode(fp.getvalue())
        fp.close()

        filename = f"measurements_{self.partner_id.name or 'report'}_{fields.Date.context_today(self).strftime('%Y%m%d')}.xlsx"

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
