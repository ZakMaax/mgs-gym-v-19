from odoo import models, fields, api  # type: ignore


class SMSTemplate(models.Model):
    _name = "mgs_sms_gateway.template"
    _description = "SMS Template"

    name = fields.Char(string="Template Name", required=True)
    model_id = fields.Many2one(
        "ir.model",
        string="Applies to Model",
        default=lambda self: self.env.ref(
            "mgs_gym.model_mgs_gym_membership", raise_if_not_found=False
        ).id,
        required=True,
        ondelete="cascade",
        help="The Odoo model this template is intended for (e.g., Gym Membership, Partner).",
    )

    usage = fields.Selection(
        [
            ("activation", "Membership Activation"),
            ("expiration", "Membership Expiration"),
            ("promotional", "Promotional Campaign"),
            ("other", "Other"),
        ],
        string="Message Type",
        required=True,
        help="When this specific template should be used.",
    )

    body = fields.Text(
        string="Message Body",
        required=True,
        help="Use dynamic placeholders like {{ object.name }}.",
    )

    @api.model
    def render_template(self, template_id, record):
        """Renders the SMS template body using the record's values (dynamic stuff)."""
        template = self.browse(template_id)
        if not template:
            return ""

        # Using Odoo's built-in rendering engine (mail.template helper)
        return self.env["mail.template"]._render_template(
            template.body,
            model=record._name,
            res_ids=record.ids,
            options={"post_process": True},
        )[record.id]
