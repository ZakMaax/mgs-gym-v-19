from odoo import models  # type: ignore


class ReportMeasurement(models.AbstractModel):
    _name = "report.mgs_gym.measurement_report"
    _description = "Measurement Report"

    def _get_report_values(self, docids, data=None):
        Measurement = self.env["mgs_gym.measurement"]

        # Try to get the documents by docids
        docs = Measurement.browse(docids).exists()

        # If empty, rebuild domain from `data`
        if not docs and data:
            domain = []
            if data.get("partner_name"):
                partner = self.env["res.partner"].search(
                    [("name", "=", data["partner_name"])], limit=1
                )
                if partner:
                    domain.append(("partner_id", "=", partner.id))
            if data.get("date_from"):
                domain.append(("date", ">=", data["date_from"]))
            if data.get("date_to"):
                domain.append(("date", "<=", data["date_to"]))
            docs = Measurement.search(domain, order="date desc")

        return {
            "doc_ids": docs.ids,
            "doc_model": "mgs_gym.measurement",
            "docs": docs,
            "data": data or {},
        }
