from odoo import models  # type: ignore


class ResCompany(models.Model):
    _inherit = "res.company"

    def _get_sms_api_class(self):
        """Redirect SMS sending to our Telesom gateway."""
        from odoo.addons.mgs_sms_gateway.models.sms_api_custom import SmsApiCustom  # type: ignore

        return SmsApiCustom
