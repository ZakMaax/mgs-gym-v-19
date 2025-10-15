from odoo import models, fields  # type: ignore


class GymMealPlan(models.Model):
    _name = "mgs_gym.meal_plan"
    _description = "Member Meal Plan"

    member_id = fields.Many2one("res.partner", string="Client", required=True)
    coach_id = fields.Many2one("res.users", string="Coach", required=True)
    date_from = fields.Date("Date from", required=True)
    date_to = fields.Date("Date to", required=True)
    plan_text = fields.Text(string="Plan", required=True)
