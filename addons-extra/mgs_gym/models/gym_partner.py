from odoo import models, api, fields  # type: ignore


class GymPartner(models.Model):
    _inherit = "res.partner"

    is_gym_member = fields.Boolean(default=True, string="Is GYM Client")
    branch_id = fields.Many2one(
        "mgs_gym.branch",
        string="Branch",
        domain=lambda self: [("id", "in", self.env.user.branch_ids.ids)],
        default=lambda self: self.env.user.default_branch_id,
    )
    gender = fields.Selection(related="branch_id.gender", store=True, readonly=True)
    company_id = fields.Many2one(
        "res.company", compute="_compute_company_id", store=True, readonly=True
    )

    @api.depends("branch_id")
    def _compute_company_id(self):
        for partner in self:
            partner.company_id = partner.branch_id.company_id or self.env.company

    def _queue_sms_message(self, mobile, message, partner):
        """Helper to create an sms.sms record for queuing."""
        if not mobile:
            # Post a warning in the chatter of the partner record
            partner.message_post(
                body="SMS not queued: Recipient mobile number is missing.",
                subject="SMS Queuing Failed",
                message_type="notification",
                subtype_xmlid="mail.mt_note",
            )
            return

        self.env["sms.sms"].create(
            {
                "body": message,
                "number": mobile,
                "partner_id": partner.id,
                "state": "outgoing",  # Queues the message for processing by the sms cron
            }
        )

    def action_send_promotional_sms(self):
        """
        Server action to send a promotional SMS to the selected partners.
        This is triggered by the list view action button.
        """
        # We search for the template that applies to the res.partner model
        # (or whatever model this action runs on)
        template = self.env["mgs_sms_gateway.template"].search(
            [("model_id.model", "=", self._name), ("usage", "=", "promotional")],
            limit=1,
        )

        if not template:
            # Use action to display notification
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "SMS Error",
                    "message": f"Promotional SMS Template not found for model {self._name}. Please create one.",
                    "sticky": False,
                    "type": "warning",
                },
            }

        sent_count = 0
        for partner in self:
            mobile = partner.phone

            if not mobile:
                partner.message_post(
                    body=f"Skipped Promotional SMS: Mobile number missing for {partner.name}.",
                    subject="Promotional SMS Skipped",
                    message_type="notification",
                    subtype_xmlid="mail.mt_note",
                )
                continue

            # Render the message using the partner record
            rendered_message = self.env["mgs_sms_gateway.template"].render_template(
                template.id, partner
            )

            self._queue_sms_message(mobile, rendered_message, partner)
            sent_count += 1

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Promotional SMS Queued",
                "message": f"{sent_count} promotional messages have been successfully queued for sending.",
                "sticky": False,
                "type": "success",
            },
        }
