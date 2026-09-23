import datetime
from odoo import api, fields, models, Command
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval


class CommandCustomRunnerWizard(models.TransientModel):
    _name = 'command.custom.runner.wizard'
    _description = 'Custom ORM Command Runner Wizard'

    playground_id = fields.Many2one(
        'command.playground',
        string='Playground Session',
        required=True,
        default=lambda self: self.env.context.get('active_id'),
    )

    target_field = fields.Selection([
        ('line_ids', 'One2many: line_ids (Item Lines)'),
        ('tag_ids', 'Many2many: tag_ids (Tags / Categories)'),
    ], string='Target Relation Field', default='line_ids', required=True)

    command_type = fields.Selection([
        ('0', 'Command 0: Create record baru dengan custom vals'),
        ('1', 'Command 1: Update record yang ada dengan custom vals'),
        ('2', 'Command 2: Delete record dari DB (Hard Delete)'),
        ('3', 'Command 3: Unlink relasi (Tanpa hapus record master)'),
        ('4', 'Command 4: Link record master yang sudah ada'),
        ('5', 'Command 5: Clear / Kosongkan seluruh isi relasi'),
        ('6', 'Command 6: Set / Replace All dengan list ID tertentu'),
        ('raw', 'Custom Raw Python / Tuple Expression'),
    ], string='Command Operation', default='0', required=True)

    # --- INPUTS UNTUK COMMAND 0 (CREATE) ---
    line_name = fields.Char(string='Item Description', default='Custom Input Product')
    line_qty = fields.Integer(string='Quantity', default=5)
    line_price = fields.Float(string='Unit Price', default=30000.0)

    tag_name = fields.Char(string='New Tag Name', default='Custom Tag')
    tag_color = fields.Integer(string='Color Index', default=3)

    # --- INPUTS UNTUK COMMAND 1 (UPDATE) ---
    target_line_id = fields.Many2one(
        'command.playground.line', string='Select Line to Update',
        domain="[('playground_id', '=', playground_id)]",
    )
    target_tag_id = fields.Many2one(
        'command.playground.tag', string='Select Tag to Update / Unlink',
        domain="[('id', 'in', playground_tag_ids)]",
    )
    new_line_name = fields.Char(string='Updated Item Name')
    new_line_qty = fields.Integer(string='Updated Quantity', default=10)
    new_line_price = fields.Float(string='Updated Price', default=45000.0)

    # --- INPUTS UNTUK COMMAND 2 (DELETE) ---
    delete_line_id = fields.Many2one(
        'command.playground.line', string='Select Line to DELETE',
        domain="[('playground_id', '=', playground_id)]",
    )

    # --- INPUTS UNTUK COMMAND 4 (LINK) ---
    available_tag_id = fields.Many2one(
        'command.playground.tag', string='Select Master Tag to LINK'
    )

    # --- INPUTS UNTUK COMMAND 6 (SET / REPLACE ALL) ---
    set_tag_ids = fields.Many2many(
        'command.playground.tag', string='Select Tags for REPLACE ALL'
    )

    # --- INPUTS UNTUK RAW PYTHON EXPR ---
    raw_expression = fields.Text(
        string='Raw Python Command Expression',
        default="[Command.create({'name': 'Raw Item', 'quantity': 1, 'price': 10000})]",
        help="Contoh: [Command.create({'name': 'X', 'quantity': 2})] atau [(0, 0, {'name': 'Y'})]"
    )

    # Related fields untuk domain filter
    playground_tag_ids = fields.Many2many(related='playground_id.tag_ids')

    code_preview = fields.Text(
        string='Live Code Preview',
        compute='_compute_code_preview'
    )

    @api.onchange('target_line_id')
    def _onchange_target_line_id(self):
        if self.target_line_id:
            self.new_line_name = self.target_line_id.name
            self.new_line_qty = self.target_line_id.quantity
            self.new_line_price = self.target_line_id.price

    # =========================================================================
    # PREVIEW GENERATOR
    # =========================================================================
    @api.depends(
        'target_field', 'command_type', 'line_name', 'line_qty', 'line_price',
        'tag_name', 'tag_color', 'target_line_id', 'target_tag_id',
        'new_line_name', 'new_line_qty', 'new_line_price', 'delete_line_id',
        'available_tag_id', 'set_tag_ids', 'raw_expression'
    )
    def _compute_code_preview(self):
        for rec in self:
            field_name = rec.target_field or 'line_ids'
            cmd = rec.command_type or '0'
            modern = ""
            tuple_fmt = ""

            if cmd == '0':
                if field_name == 'line_ids':
                    vals_dict = {'name': rec.line_name or 'Item', 'quantity': rec.line_qty or 1, 'price': rec.line_price or 0.0}
                    modern = f"Command.create({vals_dict})"
                    tuple_fmt = f"(0, 0, {vals_dict})"
                else:
                    vals_dict = {'name': rec.tag_name or 'Tag', 'color': rec.tag_color or 1}
                    modern = f"Command.create({vals_dict})"
                    tuple_fmt = f"(0, 0, {vals_dict})"

            elif cmd == '1':
                if field_name == 'line_ids':
                    lid = rec.target_line_id.id if rec.target_line_id else '<line_id>'
                    vals_dict = {'name': rec.new_line_name or 'Item', 'quantity': rec.new_line_qty or 1, 'price': rec.new_line_price or 0.0}
                    modern = f"Command.update({lid}, {vals_dict})"
                    tuple_fmt = f"(1, {lid}, {vals_dict})"
                else:
                    tid = rec.target_tag_id.id if rec.target_tag_id else '<tag_id>'
                    vals_dict = {'name': 'Updated Tag Name', 'color': 2}
                    modern = f"Command.update({tid}, {vals_dict})"
                    tuple_fmt = f"(1, {tid}, {vals_dict})"

            elif cmd == '2':
                lid = rec.delete_line_id.id if rec.delete_line_id else '<line_id>'
                modern = f"Command.delete({lid})"
                tuple_fmt = f"(2, {lid}, 0)"

            elif cmd == '3':
                tid = rec.target_tag_id.id if rec.target_tag_id else '<tag_id>'
                modern = f"Command.unlink({tid})"
                tuple_fmt = f"(3, {tid}, 0)"

            elif cmd == '4':
                tid = rec.available_tag_id.id if rec.available_tag_id else '<tag_id>'
                modern = f"Command.link({tid})"
                tuple_fmt = f"(4, {tid}, 0)"

            elif cmd == '5':
                modern = "Command.clear()"
                tuple_fmt = "(5, 0, 0)"

            elif cmd == '6':
                tids = rec.set_tag_ids.ids if rec.set_tag_ids else []
                modern = f"Command.set({tids})"
                tuple_fmt = f"(6, 0, {tids})"

            elif cmd == 'raw':
                modern = rec.raw_expression or "[]"
                tuple_fmt = "(Custom Expression)"

            rec.code_preview = (
                f"# --- Modern Class Syntax ---\n"
                f"self.write({{\n"
                f"    '{field_name}': [{modern}]\n"
                f"}})\n\n"
                f"# --- Classic Tuple Syntax ---\n"
                f"self.write({{\n"
                f"    '{field_name}': [{tuple_fmt}]\n"
                f"}})"
            )

    # =========================================================================
    # EKSEKUSI COMMAND
    # =========================================================================
    def action_execute_custom_command(self):
        """Menjalankan Command dengan nilai custom yang diinputkan pengguna."""
        self.ensure_one()
        playground = self.playground_id
        if not playground:
            raise UserError("Session Playground tidak ditemukan.")

        field_name = self.target_field
        cmd = self.command_type
        now_str = datetime.datetime.now().strftime('%H:%M:%S')

        command_list = []
        log_detail = ""

        # ---------------------------------------------------------------------
        # 1. COMMAND 0 (CREATE)
        # ---------------------------------------------------------------------
        if cmd == '0':
            if field_name == 'line_ids':
                vals = {
                    'name': self.line_name or 'Custom Line',
                    'quantity': self.line_qty or 1,
                    'price': self.line_price or 0.0,
                }
                command_list = [Command.create(vals)]
                log_detail = f"Membuat Line baru '{vals['name']}' (Qty: {vals['quantity']}, Price: Rp{vals['price']:,.0f})"
            else:
                vals = {
                    'name': self.tag_name or 'Custom Tag',
                    'color': self.tag_color or 1,
                }
                command_list = [Command.create(vals)]
                log_detail = f"Membuat Tag baru '{vals['name']}' (Color: {vals['color']})"

        # ---------------------------------------------------------------------
        # 2. COMMAND 1 (UPDATE)
        # ---------------------------------------------------------------------
        elif cmd == '1':
            if field_name == 'line_ids':
                if not self.target_line_id:
                    raise UserError("Silakan pilih Line yang ingin di-update!")
                vals = {
                    'name': self.new_line_name or self.target_line_id.name,
                    'quantity': self.new_line_qty,
                    'price': self.new_line_price,
                }
                command_list = [Command.update(self.target_line_id.id, vals)]
                log_detail = f"Mengupdate Line ID {self.target_line_id.id} menjadi '{vals['name']}' (Qty: {vals['quantity']})"
            else:
                if not self.target_tag_id:
                    raise UserError("Silakan pilih Tag yang ingin di-update!")
                vals = {'name': f"{self.target_tag_id.name} (Updated)"}
                command_list = [Command.update(self.target_tag_id.id, vals)]
                log_detail = f"Mengupdate Tag ID {self.target_tag_id.id} nama menjadi '{vals['name']}'"

        # ---------------------------------------------------------------------
        # 3. COMMAND 2 (DELETE)
        # ---------------------------------------------------------------------
        elif cmd == '2':
            if not self.delete_line_id:
                raise UserError("Silakan pilih Line yang ingin dihapus (Hard Delete)!")
            lid = self.delete_line_id.id
            lname = self.delete_line_id.name
            command_list = [Command.delete(lid)]
            log_detail = f"Menghapus (Hard Delete) Line '{lname}' (ID {lid}) dari database"

        # ---------------------------------------------------------------------
        # 4. COMMAND 3 (UNLINK)
        # ---------------------------------------------------------------------
        elif cmd == '3':
            if not self.target_tag_id:
                raise UserError("Silakan pilih Tag yang ingin di-unlink!")
            tid = self.target_tag_id.id
            tname = self.target_tag_id.name
            command_list = [Command.unlink(tid)]
            log_detail = f"Melepas relasi Tag '{tname}' (ID {tid}) tanpa menghapus master datanya"

        # ---------------------------------------------------------------------
        # 5. COMMAND 4 (LINK)
        # ---------------------------------------------------------------------
        elif cmd == '4':
            if not self.available_tag_id:
                raise UserError("Silakan pilih Master Tag yang ingin di-link!")
            tid = self.available_tag_id.id
            tname = self.available_tag_id.name
            command_list = [Command.link(tid)]
            log_detail = f"Menghubungkan Master Tag '{tname}' (ID {tid}) ke Many2many"

        # ---------------------------------------------------------------------
        # 6. COMMAND 5 (CLEAR)
        # ---------------------------------------------------------------------
        elif cmd == '5':
            command_list = [Command.clear()]
            log_detail = f"Mengosongkan seluruh isi relasi '{field_name}'"

        # ---------------------------------------------------------------------
        # 7. COMMAND 6 (SET / REPLACE ALL)
        # ---------------------------------------------------------------------
        elif cmd == '6':
            if not self.set_tag_ids:
                raise UserError("Silakan pilih minimal 1 Tag untuk di-set!")
            tids = self.set_tag_ids.ids
            command_list = [Command.set(tids)]
            log_detail = f"Replace All: Mengganti seluruh isi tag menjadi ID list {tids}"

        # ---------------------------------------------------------------------
        # 8. RAW PYTHON EXPRESSION
        # ---------------------------------------------------------------------
        elif cmd == 'raw':
            try:
                eval_context = {'Command': Command}
                command_list = safe_eval(self.raw_expression, eval_context)
                log_detail = f"Mengeksekusi Raw Expression: {self.raw_expression}"
            except Exception as eval_err:
                raise UserError(f"Gagal mengevaluasi ekspresi Python: {eval_err}")

        # Jalankan write pada playground
        playground.write({
            field_name: command_list,
            'last_command': f"Wizard Custom Command {cmd.upper()} on {field_name}",
            'code_snippet': self.code_preview,
            'execution_log': f"[{now_str}] SUKSES: {log_detail}",
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'command.playground',
            'res_id': playground.id,
            'view_mode': 'form',
            'target': 'current',
        }

