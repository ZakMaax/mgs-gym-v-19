from odoo import models, fields, api  # type: ignore
from odoo.exceptions import UserError  # type: ignore
from datetime import timedelta


class GymMembership(models.Model):
    _name = "mgs_gym.membership"
    _description = "Gym Membership"
    _inherit = ["mail.activity.mixin", "mail.tracking.duration.mixin"]

    _track_duration_field = "state_id"

    name = fields.Char(string="Name", default="/", required=True, readonly=True)
    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        string="Client",
        domain=[("is_gym_member", "=", True)],
    )
    branch_id = fields.Many2one(
        "mgs_gym.branch",
        string="Branch",
        tracking=True,
    )
    active = fields.Boolean(default=True)
    gender = fields.Selection(related="partner_id.gender", store=True, readonly=True)
    shift_id = fields.Many2one(
        "mgs_gym.shift",
        string="Shift",
        required=True,
        tracking=True,
        domain="[('branch_id', '=', branch_id), ('gender', '=', gender)]",
    )

    recurrence_unit = fields.Selection(
        [
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("yearly", "Yearly"),
        ],
        string="Recurrence Unit",
        default="monthly",
        required=True,
    )

    recurrence_interval = fields.Integer(
        string="Recurrence Interval",
        default=1,
        help="Every X recurrence unit(s)",
    )

    service_id = fields.Many2one(
        "product.template",
        domain="[('type', '=', 'service')]",
        string="Base Service Product",
        readonly=True,
    )

    recurrence_product_id = fields.Many2one(
        "product.product",
        string="Membership Service",
        readonly=True,
        help="Selected automatically based on the recurrence unit.",
    )

    amount = fields.Monetary(
        string="Amount",
        currency_field="company_currency_id",
        tracking=True,
        readonly=True,
    )

    start_date = fields.Date(
        string="Start Date",
        required=True,
        default=fields.Date.today,
    )

    next_invoice_date = fields.Date(
        string="Next Invoice Date",
        help="The next scheduled invoice generation date.",
    )

    auto_invoice = fields.Boolean(
        string="Auto Generate Invoice",
        default=True,
    )

    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, readonly=True
    )

    company_currency_id = fields.Many2one(
        related="company_id.currency_id",
        readonly=True,
    )

    state_id = fields.Many2one(
        "mgs_gym.membership_state",
        string="State",
        index=True,
        store=True,
        default=lambda self: self._default_state_id(),
        group_expand="_read_group_state_ids",
        tracking=True,
        copy=False,
        ondelete="restrict",
    )
    state = fields.Char(
        related="state_id.name", string="State", store=True, translate=True
    )

    # -------------------------------
    # Default and state methods
    # -------------------------------
    @api.model
    def _read_group_state_ids(self, states, domain):
        return self.env["mgs_gym.membership_state"].search([], order="sequence, id")

    def _default_state_id(self):
        return self.env["mgs_gym.membership_state"].search(
            [], limit=1, order="sequence"
        )

    # -------------------------------
    # Onchange methods
    # -------------------------------
    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        for record in self:
            record.branch_id = (
                record.partner_id.branch_id.id if record.partner_id.branch_id else False
            )

    @api.onchange("shift_id", "recurrence_unit")
    def _onchange_shift_or_unit(self):
        """Compute recurrence product and amount whenever shift or unit changes."""
        self._compute_recurrence_product_and_amount()

    # -------------------------------
    # Helper method for recurrence
    # -------------------------------
    def _compute_recurrence_product_and_amount(self):
        variant_map = {
            "weekly": "Weekly",
            "monthly": "Monthly",
            "quarterly": "Quarterly",
            "yearly": "Yearly",
        }

        for record in self:
            if not record.shift_id:
                record.recurrence_product_id = False
                record.amount = 0
                record.service_id = False
                continue

            record.service_id = record.shift_id.service_id.id
            base_price = record.shift_id.service_id.list_price or 0
            variant_name = variant_map.get(record.recurrence_unit)

            variant = record.shift_id.service_id.product_variant_ids.filtered(
                lambda p: any(
                    v.name == variant_name
                    for v in p.product_template_attribute_value_ids
                )
            )

            if variant:
                record.recurrence_product_id = variant[0].id
                unit_price = variant[0].lst_price
            else:
                record.recurrence_product_id = record.shift_id.service_id.id
                unit_price = base_price

            interval = record.recurrence_interval or 1
            record.amount = unit_price * interval

    # -------------------------------
    # Billing logic
    # -------------------------------
    @api.onchange("recurrence_unit", "recurrence_interval", "start_date")
    def _onchange_billing(self):
        for record in self:
            if not record.start_date:
                continue

            unit = record.recurrence_unit
            interval = record.recurrence_interval or 1
            next_date = record.start_date

            if unit == "weekly":
                next_date += timedelta(weeks=interval)
            elif unit == "monthly":
                next_date = fields.Date.add(next_date, months=interval)
            elif unit == "quarterly":
                next_date = fields.Date.add(next_date, months=3 * interval)
            elif unit == "yearly":
                next_date = fields.Date.add(next_date, years=interval)

            record.next_invoice_date = next_date

    # -------------------------------
    # Create override
    # -------------------------------
    @api.model
    def create(self, vals_list):
        for vals in vals_list:
            shift_id = vals.get("shift_id")
            if shift_id:
                shift = self.env["mgs_gym.shift"].browse(shift_id)
                if shift.capacity and shift.capacity > 0:
                    # Count active memberships in this shift
                    current_count = self.search_count(
                        [("shift_id", "=", shift.id), ("active", "=", True)]
                    )
                    if current_count >= shift.capacity:
                        raise UserError(
                            f"Shift '{shift.name}' is full ({shift.capacity} members)."
                        )
            if vals.get("name", "/") == "/":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("mgs_gym.membership") or "/"
                )
        recs = super().create(vals_list)
        for membership in recs:
            membership._compute_recurrence_product_and_amount()
            # Generate the first invoice immediately
            if membership.auto_invoice:
                membership._generate_first_invoice()
            # Calculate next invoice date after first invoice
            membership._onchange_billing()

        return recs

    # -------------------------------
    # Cron job for recurring invoices
    # -------------------------------
    @api.model
    def generate_recurring_invoice(self):
        today = fields.Date.today()
        memberships = self.search(
            [
                ("auto_invoice", "=", True),
                ("state", "=", "Active"),
                ("next_invoice_date", "<=", today),
            ]
        )

        for membership in memberships:
            product = membership.recurrence_product_id or membership.service_id
            if not product:
                continue

            invoice_vals = {
                "partner_id": membership.partner_id.id,
                "move_type": "out_invoice",
                "invoice_date": membership.next_invoice_date,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "quantity": 1,
                            "price_unit": membership.amount,
                        },
                    )
                ],
            }

            invoice = self.env["account.move"].create(invoice_vals)
            invoice.action_post()
            self._update_next_invoice_date(membership)

    def _update_next_invoice_date(self, membership):
        if not membership.start_date:
            return

        unit = membership.recurrence_unit
        interval = membership.recurrence_interval or 1
        next_date = membership.next_invoice_date or membership.start_date

        if unit == "weekly":
            next_date += timedelta(weeks=interval)
        elif unit == "monthly":
            next_date = fields.Date.add(next_date, months=interval)
        elif unit == "quarterly":
            next_date = fields.Date.add(next_date, months=3 * interval)
        elif unit == "yearly":
            next_date = fields.Date.add(next_date, years=interval)

        membership.write({"next_invoice_date": next_date})

    def _generate_first_invoice(self):
        """Generate the invoice immediately upon membership creation."""
        product = self.recurrence_product_id or self.service_id
        if not product:
            return

        invoice_vals = {
            "partner_id": self.partner_id.id,
            "move_type": "out_invoice",
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "quantity": 1,
                        "price_unit": self.amount,
                    },
                )
            ],
        }

        invoice = self.env["account.move"].create(invoice_vals)
        invoice.action_post()

        # Update next_invoice_date AFTER this first invoice
        self._update_next_invoice_date(self)
