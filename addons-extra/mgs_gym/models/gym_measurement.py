from odoo import models, api, fields  # type: ignore


class GymMeasurement(models.Model):
    _name = "mgs_gym.measurement"
    _description = "Member Measurements"
    _inherit = ["mail.thread", "mail.activity.mixin"]

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
    date = fields.Date(
        "Date",
        required=True,
        tracking=True,
        default=fields.Date.today(),
    )
    weight = fields.Float(
        "Weight (kg)",
        required=True,
        tracking=True,
    )
    height = fields.Float(
        "Height (cm)",
        required=True,
        tracking=True,
    )
    bmi = fields.Float(compute="_compute_bmi", string="BMI Numerical", digits=(16, 2))
    bmi_text = fields.Char(
        compute="_compute_bmi_text", string="BMI Desc", help="BMI Description"
    )
    body_fat_percentage = fields.Float(
        "Body Fat %",
        tracking=True,
    )
    muscle_mass = fields.Float(
        string="Muscle Mass",
        tracking=True,
    )
    note = fields.Text(string="Additional observations")

    @api.depends("weight", "height")
    def _compute_bmi(self):
        for rec in self:
            rec.bmi = rec.weight / ((rec.height / 100) ** 2) if rec.height else 0.0

    @api.depends("partner_id", "date")
    def _compute_name(self):
        for rec in self:
            partner_name = rec.partner_id.name or "Unknown"
            date_str = rec.date or fields.Date.today()
            rec.name = f"{partner_name}/{date_str}"

    @api.depends("bmi")
    def _compute_bmi_text(self):
        for rec in self:
            if rec.bmi < 18.5:
                rec.bmi_text = "Underweight"
            elif rec.bmi >= 18.5 and rec.bmi <= 24.9:
                rec.bmi_text = "Normal"
            elif rec.bmi >= 25.0 and rec.bmi <= 29.9:
                rec.bmi_text = "Overweight"
            elif rec.bmi >= 30.0:
                rec.bmi_text = "Obese"
