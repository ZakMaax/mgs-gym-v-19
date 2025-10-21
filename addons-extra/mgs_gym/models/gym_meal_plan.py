from odoo import models, api, fields  # type: ignore


class GymMealPlan(models.Model):
    _name = "mgs_gym.meal_plan"
    _description = "Member Meal Plan"

    name = fields.Char(readonly=True, compute="_compute_name")
    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        string="Client",
        domain=lambda self: [
            ("branch_id", "in", self.env.user.branch_ids.ids),
            ("is_gym_member", "=", True),
        ],
    )
    coach_id = fields.Many2one("res.users", string="Coach", required=True)
    date_from = fields.Date("Date from", required=True)
    date_to = fields.Date("Date to", required=True)
    plan_text = fields.Html("Plan", sanitize=True)

    @api.depends("partner_id")
    def _compute_name(self):
        for rec in self:
            partner_name = rec.partner_id.name or "Unknown"
            date_str = fields.Date.today()
            rec.name = f"{partner_name}/{date_str}"
