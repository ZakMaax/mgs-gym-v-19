from odoo import models, fields  # type: ignore
from odoo.exceptions import UserError  # type: ignore


class SaleReport(models.TransientModel):
    _name = "mgs_sale.sale_report"
    _description = "Sale Report"

    date_from = fields.Date(
        default=fields.Date.today().replace(day=1), string="Date from", required=True
    )
    date_to = fields.Date(default=fields.Date.today(), string="Date to", required=True)
    user_id = fields.Many2one("res.users", string="User")
    partner_id = fields.Many2one("res.partner", "Partner")
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, string="Company"
    )
    team_id = fields.Many2one("crm.team", string="Sales Team")
    currency_id = fields.Many2one("res.currency", string="Currency")
    sales_tag_ids = fields.Many2many("crm.tag", string="Tags")
    product_id = fields.Many2one("product.product", string="Product")
    categ_id = fields.Many2one("product.category", string="Product category")
    parent_categ_id = fields.Many2one("product.category", string="Parent Category")
    report_type = fields.Selection(
        [("summary", "Summary"), ("detail", "Detail")],
        default="summary",
        string="Report type",
        required=True,
    )
    group_by = fields.Selection(
        [("customer", "Customer"), ("item", "Item")],
        default="customer",
        string="Group by",
        required=True,
    )

    def get_detailed_sales_data(self):
        SaleOrderLine = self.env["sale.order.line"]
        final_data = []

        # --- 1️⃣ Validate date range ---
        if self.date_from > self.date_to:
            raise UserError("The start date cannot be after the end date.")

        # --- 2️⃣ Build domain ---

        domain = [
            ("order_id.date_order", ">=", self.date_from),
            ("order_id.date_order", "<=", self.date_to),
            ("order_id.state", "in", ["sale", "done"]),
        ]

        if self.user_id:
            domain.append(("order_id.user_id", "=", self.user_id.id))
        if self.company_id:
            domain.append(("order_id.company_id", "=", self.company_id.id))
        if self.team_id:
            domain.append(("order_id.team_id", "=", self.team_id.id))
        if self.partner_id:
            domain.append(("order_id.partner_id", "=", self.partner_id.id))
        if self.product_id:
            domain.append(("product_id", "=", self.product_id.id))
        if self.categ_id:
            domain.append(("product_id.categ_id", "=", self.categ_id.id))
        if self.parent_categ_id:
            domain.append(
                ("product_id.categ_id.parent_id", "=", self.parent_categ_id.id)
            )

        # --- 3️⃣ Define grouping ---
        group_field = (
            "order_partner_id" if self.group_by == "customer" else "product_id"
        )

        grouped_data = SaleOrderLine.read_group(
            domain,
            fields=["price_subtotal:sum", group_field],
            groupby=[group_field],
            lazy=False,
        )

        # --- 4️⃣ Process grouped data ---
        for group in grouped_data:
            group_value = group.get(group_field)
            group_name = (
                group_value[1]
                if group_value
                else (
                    "Undefined Customer"
                    if self.group_by == "customer"
                    else "Undefined Product"
                )
            )
            group_domain = group["__domain"]

            # Search all order lines for this group
            order_lines = SaleOrderLine.search(group_domain)

            # Compute totals
            total_amount = sum(order_lines.mapped("price_subtotal"))
            total_ordered_qty = sum(order_lines.mapped("product_uom_qty"))
            total_delivered_qty = sum(order_lines.mapped("qty_delivered"))
            total_to_invoice_qty = sum(order_lines.mapped("qty_to_invoice"))
            total_invoiced_qty = sum(order_lines.mapped("qty_invoiced"))

            # Structure section (include totals)
            section = {
                "group": group_name,
                "total_amount": total_amount,
                "total_ordered_qty": total_ordered_qty,
                "total_delivered_qty": total_delivered_qty,
                "total_to_invoice_qty": total_to_invoice_qty,
                "total_invoiced_qty": total_invoiced_qty,
                "orders": [],
            }

            for line in order_lines:
                order = line.order_id
                section["orders"].append(
                    {
                        "order_date": order.date_order.date(),
                        "order_name": order.name,
                        "customer": order.partner_id.name,
                        "product": line.product_id.display_name,
                        "ordered_qty": line.product_uom_qty,
                        "delivered_qty": line.qty_delivered,
                        "rate": line.price_unit,
                        "amount": line.price_subtotal,
                        "to_invoice_qty": line.qty_to_invoice,
                        "invoiced_qty": line.qty_invoiced,
                    }
                )

            final_data.append(section)

        return final_data

    def get_summary_sales_data(self):
        SaleOrderLine = self.env["sale.order.line"]

        # --- 1️⃣ Validation ---
        if self.date_from > self.date_to:
            raise UserError("The start date cannot be after the end date.")

        # --- 2️⃣ Build Domain (same as detailed report) ---
        domain = [
            ("order_id.date_order", ">=", self.date_from),
            ("order_id.date_order", "<=", self.date_to),
            ("order_id.state", "in", ["sale", "done"]),
        ]

        # Apply filters (User, Company, Team, Partner, Product, Category)
        if self.user_id:
            domain.append(("order_id.user_id", "=", self.user_id.id))
        if self.company_id:
            domain.append(("order_id.company_id", "=", self.company_id.id))
        if self.team_id:
            domain.append(("order_id.team_id", "=", self.team_id.id))
        if self.partner_id:
            domain.append(("order_id.partner_id", "=", self.partner_id.id))
        if self.product_id:
            domain.append(("product_id", "=", self.product_id.id))
        if self.categ_id:
            domain.append(("product_id.categ_id", "=", self.categ_id.id))
        if self.parent_categ_id:
            domain.append(
                ("product_id.categ_id.parent_id", "=", self.parent_categ_id.id)
            )

        # --- 3️⃣ Define Grouping and Aggregation Fields ---
        group_field = (
            "order_partner_id" if self.group_by == "customer" else "product_id"
        )

        aggregate_fields = [
            group_field,
            "price_subtotal:sum",
            "product_uom_qty:sum",
            "qty_delivered:sum",
            "qty_to_invoice:sum",
            "qty_invoiced:sum",
        ]

        # Perform the aggregation using read_group
        grouped_data = SaleOrderLine.read_group(
            domain,
            fields=aggregate_fields,
            groupby=[group_field],
            lazy=False,
        )

        # --- 4️⃣ Format Data for Report ---
        final_data = []

        for group in grouped_data:
            group_value = group.get(group_field)
            group_name = group_value[1] if group_value else "Undefined"

            final_data.append(
                {
                    # Renaming the group field for template consistency
                    "group_name": group_name,
                    # Direct sums from read_group
                    "total_amount": group.get("price_subtotal", 0.0),
                    "total_ordered_qty": group.get("product_uom_qty", 0.0),
                    "total_delivered_qty": group.get("qty_delivered", 0.0),
                    "total_to_invoice_qty": group.get("qty_to_invoice", 0.0),
                    "total_invoiced_qty": group.get("qty_invoiced", 0.0),
                }
            )

        return final_data

    def action_print_report(self):
        if self.report_type == "detail":
            return self.env.ref(
                "mgs_sale.action_report_mgs_sale_detailed"
            ).report_action(self)
        elif self.report_type == "summary":
            return self.env.ref(
                "mgs_sale.action_report_mgs_sale_summary"
            ).report_action(self)
