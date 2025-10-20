from odoo import api, fields, models  # type: ignore


class GymEquipment(models.Model):
    _name = "mgs_gym.equipment"
    _description = "Gym Equipment"

    name = fields.Char(string="Name", required=True)
    reference = fields.Char(string="Reference", readonly=True)
    image_1920 = fields.Image(string="Image")
    branch_id = fields.Many2one("mgs_gym.branch", string="Branch")
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )
    cost = fields.Monetary(string="Cost", currency_field="company_currency_id")
    count = fields.Integer("Count")
    purchase_date = fields.Date(string="Date of Purchase")

    company_currency_id = fields.Many2one(
        related="company_id.currency_id", readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("reference"):
                vals["reference"] = self.env["ir.sequence"].next_by_code(
                    "mgs_gym.equipment"
                )
        return super().create(vals_list)
