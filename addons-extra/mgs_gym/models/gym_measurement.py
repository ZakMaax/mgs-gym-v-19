from odoo import models, api, fields  # type: ignore


class GymMeasurement(models.Model):
    _name = "mgs_gym.measurement"
    _description = "Member Measurements"

    member_id = fields.Many2one("res.partner", string="Client", required=True)
    date = fields.Date("Date", required=True)
    weight = fields.Float(string="Weight (kg)", required=True)
    height = fields.Float(string="Height (cm)", required=True)
    bmi = fields.Float(compute="_compute_bmi", string="BMI")
    body_fat_percentage = fields.Float("Body Fat %")
    muscle_mass = fields.Float(string="Muscle Mass")
    note = fields.Text(string="Additional observations")

    @api.depends("weight", "height")
    def _compute_bmi(self):
        for rec in self:
            rec.bmi = rec.weight / ((rec.height / 100) ** 2) if rec.height else 0.0
