from odoo import api, fields, models, Command
from odoo.exceptions import UserError
import datetime


class CommandPlayground(models.Model):
    _name = 'command.playground'
    _description = 'Odoo ORM Command Playground Session'
    _order = 'id desc'

    name = fields.Char(string='Session Name', required=True, default='Command Playground Experiment')
    
    # 1. Relasi One2many untuk demonstrasi Command 0, 1, 2, 5
    line_ids = fields.One2many(
        'command.playground.line', 'playground_id',
        string='Lines (One2many Target)'
    )
    line_count = fields.Integer(compute='_compute_counts', string='Line Count')
    
    # 2. Relasi Many2many untuk demonstrasi Command 0, 3, 4, 5, 6
    tag_ids = fields.Many2many(
        'command.playground.tag', 'command_playground_tag_rel', 'playground_id', 'tag_id',
        string='Tags (Many2many Target)'
    )
    tag_count = fields.Integer(compute='_compute_counts', string='Tag Count')

    last_command = fields.Char(string='Last Command Executed', readonly=True)
    code_snippet = fields.Text(string='Executed Python Code', readonly=True)
    execution_log = fields.Text(string='Execution Log & Explanation', readonly=True)

    @api.depends('line_ids', 'tag_ids')
    def _compute_counts(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.tag_count = len(rec.tag_ids)

    def action_view_lines(self):
        """Action smart button untuk membuka daftar Lines pada session ini."""
        self.ensure_one()
        return {
            'name': f'Lines in {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'command.playground.line',
            'view_mode': 'list,form',
            'domain': [('playground_id', '=', self.id)],
            'context': {'default_playground_id': self.id},
        }

    def action_view_tags(self):
        """Action smart button untuk membuka daftar Tags pada session ini."""
        self.ensure_one()
        return {
            'name': f'Tags in {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'command.playground.tag',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.tag_ids.ids)],
        }

    def action_open_custom_wizard(self):
        """Membuka Wizard untuk mengisi parameter / values custom sendiri."""
        self.ensure_one()
        return {
            'name': 'Custom ORM Command Runner',
            'type': 'ir.actions.act_window',
            'res_model': 'command.custom.runner.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_playground_id': self.id},
        }

    # =========================================================================
    # 1. COMMAND 0: Command.create(vals) / (0, 0, vals)
    # =========================================================================
    def action_cmd_0_create_tag(self):
        """Membuat Tag baru dan langsung menghubungkannya ke Many2many."""
        self.ensure_one()
        now_str = datetime.datetime.now().strftime('%H:%M:%S')
        next_tag_num = self.env['command.playground.tag'].search_count([]) + 1
        new_tag_name = f"Tag @ {next_tag_num}"
        new_color = (next_tag_num % 10) + 1

        self.write({
            'tag_ids': [
                Command.create({
                    'name': new_tag_name,
                    'color': new_color,
                })
            ]
        })

        code = (
            "# --- Modern Class Syntax (Odoo 15+) ---\n"
            "self.write({\n"
            "    'tag_ids': [\n"
            f"        Command.create({{'name': '{new_tag_name}', 'color': {new_color}}})\n"
            "    ]\n"
            "})\n\n"
            "# --- Classic Tuple Syntax ---\n"
            "self.write({\n"
            "    'tag_ids': [\n"
            f"        (0, 0, {{'name': '{new_tag_name}', 'color': {new_color}}})\n"
            "    ]\n"
            "})"
        )

        self.last_command = "Command 0: CREATE TAG INTO M2M (0, 0, vals)"
        self.code_snippet = code
        self.execution_log = (
            f"[{now_str}] BERHASIL: Membuat Tag master baru '{new_tag_name}' sekaligus me-link ke Many2many 'tag_ids'.\n"
            "Fungsi: Menunjukkan bahwa Command 0 (Create) bekerja sama baiknya pada Many2many maupun One2many!"
        )
    def action_cmd_0_create(self):
        """Menambahkan record child baru ke One2many & Many2many."""
        self.ensure_one()
        now_str = datetime.datetime.now().strftime('%H:%M:%S')
        new_item_name = f"Item Created @ {now_str}"

        # Eksekusi write dengan Command.create / (0, 0, vals)
        self.write({
            'line_ids': [
                Command.create({
                    'name': new_item_name,
                    'quantity': 2,
                    'price': 15000.0,
                })
            ]
        })

        code = (
            "# --- Modern Class Syntax (Odoo 15+) ---\n"
            "self.write({\n"
            "    'line_ids': [\n"
            f"        Command.create({{'name': '{new_item_name}', 'quantity': 2, 'price': 15000.0}})\n"
            "    ]\n"
            "})\n\n"
            "# --- Classic Tuple Syntax ---\n"
            "self.write({\n"
            "    'line_ids': [\n"
            f"        (0, 0, {{'name': '{new_item_name}', 'quantity': 2, 'price': 15000.0}})\n"
            "    ]\n"
            "})"
        )

        self.last_command = "Command 0: CREATE (0, 0, vals)"
        self.code_snippet = code
        self.execution_log = (
            f"[{now_str}] BERHASIL: Menambahkan record baru '{new_item_name}' ke One2many 'line_ids'.\n"
            "Fungsi: Membuat record child baru di database dan langsung menghubungkannya ke parent ini."
        )

    # =========================================================================
    # 2. COMMAND 1: Command.update(id, vals) / (1, id, vals)
    # =========================================================================
    def action_cmd_1_update(self):
        """Mengupdate data record child yang sudah ada di One2many."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError("Belum ada line untuk di-update! Klik 'Command 0: Create' terlebih dahulu.")

        target_line = self.line_ids[0]
        now_str = datetime.datetime.now().strftime('%H:%M:%S')
        new_qty = target_line.quantity + 1

        self.write({
            'line_ids': [
                Command.update(target_line.id, {
                    'quantity': new_qty,
                    'name': f"{target_line.name.split(' (Updated')[0]} (Updated {now_str})",
                })
            ]
        })

        code = (
            "# --- Modern Class Syntax (Odoo 15+) ---\n"
            "self.write({\n"
            "    'line_ids': [\n"
            f"        Command.update({target_line.id}, {{'quantity': {new_qty}}})\n"
            "    ]\n"
            "})\n\n"
            "# --- Classic Tuple Syntax ---\n"
            "self.write({\n"
            "    'line_ids': [\n"
            f"        (1, {target_line.id}, {{'quantity': {new_qty}}})\n"
            "    ]\n"
            "})"
        )

        self.last_command = "Command 1: UPDATE (1, id, vals)"
        self.code_snippet = code
        self.execution_log = (
            f"[{now_str}] BERHASIL: Mengupdate Line ID {target_line.id} (Quantity menjadi {new_qty}).\n"
            "Fungsi: Mengubah nilai field pada record child yang sudah ada tanpa membuat baris baru."
        )

    # =========================================================================
    # 3. COMMAND 2: Command.delete(id) / (2, id, 0)
    # =========================================================================
    def action_cmd_2_delete(self):
        """Menghapus record child dari database (Hard Delete) dan memutus relasi."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError("Tidak ada line untuk dihapus! Klik 'Command 0: Create' terlebih dahulu.")

        target_line = self.line_ids[-1]
        line_id = target_line.id
        line_name = target_line.name
        now_str = datetime.datetime.now().strftime('%H:%M:%S')

        self.write({
            'line_ids': [
                Command.delete(line_id)
            ]
        })

        code = (
            "# --- Modern Class Syntax (Odoo 15+) ---\n"
            "self.write({\n"
            "    'line_ids': [\n"
            f"        Command.delete({line_id})\n"
            "    ]\n"
            "})\n\n"
            "# --- Classic Tuple Syntax ---\n"
            "self.write({\n"
            "    'line_ids': [\n"
            f"        (2, {line_id}, 0)\n"
            "    ]\n"
            "})"
        )

        self.last_command = "Command 2: DELETE (2, id, 0)"
        self.code_snippet = code
        self.execution_log = (
            f"[{now_str}] BERHASIL: Menghapus record '{line_name}' (ID {line_id}) dari DATABASE.\n"
            "PERHATIAN: Command 2 melakukan HARD DELETE pada database, record benar-benar terhapus!"
        )

    # =========================================================================
    # 4. COMMAND 4: Command.link(id) / (4, id, 0)
    # =========================================================================
    def action_cmd_4_link(self):
        """Menghubungkan record Many2many yang sudah ada di database ke parent ini."""
        self.ensure_one()
        now_str = datetime.datetime.now().strftime('%H:%M:%S')

        # Cari master tag yang sudah ada di database tetapi belum terhubung
        available_tags = self.env['command.playground.tag'].search([])
        unlinked_tags = available_tags.filtered(lambda t: t.id not in self.tag_ids.ids)
        if not unlinked_tags:
            raise UserError(
                "Semua Tag yang ada di database sudah terhubung ke sesi ini!\n\n"
                "💡 Penjelasan Edukasi:\n"
                "Command 4: Link (4, id, 0) hanya bertugas menghubungkan data master yang SUDAH ADA di database.\n"
                "Jika ingin membuat tag baru, gunakan tombol '0: Create Tag (M2M)' atau tambahkan melalui menu 'Master Data Tags (M2M)'."
            )
        
        target_tag = unlinked_tags[0]

        self.write({
            'tag_ids': [
                Command.link(target_tag.id)
            ]
        })

        code = (
            "# --- Modern Class Syntax (Odoo 15+) ---\n"
            "self.write({\n"
            "    'tag_ids': [\n"
            f"        Command.link({target_tag.id})\n"
            "    ]\n"
            "})\n\n"
            "# --- Classic Tuple Syntax ---\n"
            "self.write({\n"
            "    'tag_ids': [\n"
            f"        (4, {target_tag.id}, 0)\n"
            "    ]\n"
            "})"
        )

        self.last_command = "Command 4: LINK (4, id, 0)"
        self.code_snippet = code
        self.execution_log = (
            f"[{now_str}] BERHASIL: Menghubungkan Tag '{target_tag.name}' (ID {target_tag.id}) ke Many2many.\n"
            "Fungsi: Menyambungkan record master data yang sudah ada tanpa membuat duplikat."
        )

    # =========================================================================
    # 5. COMMAND 3: Command.unlink(id) / (3, id, 0)
    # =========================================================================
    def action_cmd_3_unlink(self):
        """Melepas hubungan Many2many (Record master TIDAK dihapus dari database)."""
        self.ensure_one()
        if not self.tag_ids:
            raise UserError("Tidak ada Tag untuk di-unlink! Hubungkan Tag terlebih dahulu via Command 4.")

        target_tag = self.tag_ids[0]
        tag_id = target_tag.id
        tag_name = target_tag.name
        now_str = datetime.datetime.now().strftime('%H:%M:%S')

        self.write({
            'tag_ids': [
                Command.unlink(tag_id)
            ]
        })

        code = (
            "# --- Modern Class Syntax (Odoo 15+) ---\n"
            "self.write({\n"
            "    'tag_ids': [\n"
            f"        Command.unlink({tag_id})\n"
            "    ]\n"
            "})\n\n"
            "# --- Classic Tuple Syntax ---\n"
            "self.write({\n"
            "    'tag_ids': [\n"
            f"        (3, {tag_id}, 0)\n"
            "    ]\n"
            "})"
        )

        self.last_command = "Command 3: UNLINK (3, id, 0)"
        self.code_snippet = code
        self.execution_log = (
            f"[{now_str}] BERHASIL: Melepas relasi Tag '{tag_name}' (ID {tag_id}).\n"
            "CATATAN: Record Tag tersebut MASIH ADA di database tabel 'command.playground.tag', hanya relasinya yang dilepas."
        )

    # =========================================================================
    # 6. COMMAND 6: Command.set(ids) / (6, 0, ids)
    # =========================================================================
    def action_cmd_6_set(self):
        """Replace All: Mengganti seluruh isi relasi Many2many dengan list ID baru."""
        self.ensure_one()
        now_str = datetime.datetime.now().strftime('%H:%M:%S')

        # Ambil 2 tag pertama atau buat jika kurang
        tags = self.env['command.playground.tag'].search([], limit=3)
        if len(tags) < 2:
            t1 = self.env['command.playground.tag'].create({'name': 'Alpha', 'color': 1})
            t2 = self.env['command.playground.tag'].create({'name': 'Beta', 'color': 2})
            tags = t1 | t2

        target_ids = tags.ids

        self.write({
            'tag_ids': [
                Command.set(target_ids)
            ]
        })

        code = (
            "# --- Modern Class Syntax (Odoo 15+) ---\n"
            "self.write({\n"
            "    'tag_ids': [\n"
            f"        Command.set({target_ids})\n"
            "    ]\n"
            "})\n\n"
            "# --- Classic Tuple Syntax ---\n"
            "self.write({\n"
            "    'tag_ids': [\n"
            f"        (6, 0, {target_ids})\n"
            "    ]\n"
            "})"
        )

        self.last_command = "Command 6: SET / REPLACE ALL (6, 0, ids)"
        self.code_snippet = code
        self.execution_log = (
            f"[{now_str}] BERHASIL: Mengganti seluruh relasi Tag dengan ID {target_ids}.\n"
            "Fungsi: Memastikan isi Many2many persis sama dengan list ID yang diberikan (replace all)."
        )

    # =========================================================================
    # 7. COMMAND 5: Command.clear() / (5, 0, 0)
    # =========================================================================
    def action_cmd_5_clear(self):
        """Mengosongkan seluruh relasi Many2many atau One2many (Unlink All)."""
        self.ensure_one()
        now_str = datetime.datetime.now().strftime('%H:%M:%S')

        self.write({
            'tag_ids': [
                Command.clear()
            ]
        })

        code = (
            "# --- Modern Class Syntax (Odoo 15+) ---\n"
            "self.write({\n"
            "    'tag_ids': [\n"
            "        Command.clear()\n"
            "    ]\n"
            "})\n\n"
            "# --- Classic Tuple Syntax ---\n"
            "self.write({\n"
            "    'tag_ids': [\n"
            "        (5, 0, 0)\n"
            "    ]\n"
            "})"
        )

        self.last_command = "Command 5: CLEAR / EMPTY ALL (5, 0, 0)"
        self.code_snippet = code
        self.execution_log = (
            f"[{now_str}] BERHASIL: Mengosongkan seluruh relasi Many2many 'tag_ids'.\n"
            "Fungsi: Memutus seluruh link relasi sekaligus."
        )

    # =========================================================================
    # RESET SAMPLE DATA
    # =========================================================================
    def action_reset_playground(self):
        """Mereset data playground ke state awal untuk eksperimen baru."""
        self.ensure_one()
        t1 = self.env['command.playground.tag'].search([('name', '=', 'Urgent')], limit=1)
        if not t1:
            t1 = self.env['command.playground.tag'].create({'name': 'Urgent', 'color': 1})
        t2 = self.env['command.playground.tag'].search([('name', '=', 'Training')], limit=1)
        if not t2:
            t2 = self.env['command.playground.tag'].create({'name': 'Training', 'color': 4})

        # Kosongkan line lama lalu buat 2 baru
        self.line_ids.unlink()

        self.write({
            'line_ids': [
                Command.create({'name': 'Sample Product A', 'quantity': 3, 'price': 25000.0}),
                Command.create({'name': 'Sample Product B', 'quantity': 1, 'price': 75000.0}),
            ],
            'tag_ids': [
                Command.set([t1.id, t2.id])
            ],
            'last_command': 'Playground Reset to Default State',
            'code_snippet': '# Playground telah di-reset ke data sampel awal.',
            'execution_log': 'Data telah di-reset. Anda dapat mencoba menekan tombol Command di atas!'
        })


class CommandPlaygroundLine(models.Model):
    _name = 'command.playground.line'
    _description = 'Command Playground Child Line'
    _order = 'id'

    playground_id = fields.Many2one('command.playground', required=True, ondelete='cascade')
    name = fields.Char(string='Description / Item Name', required=True)
    quantity = fields.Integer(string='Quantity', default=1)
    price = fields.Float(string='Unit Price', default=0.0)
    subtotal = fields.Float(string='Subtotal', compute='_compute_subtotal')

    @api.depends('quantity', 'price')
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = rec.quantity * rec.price


class CommandPlaygroundTag(models.Model):
    _name = 'command.playground.tag'
    _description = 'Command Playground Tag'
    _order = 'name'

    name = fields.Char(string='Tag Name', required=True)
    color = fields.Integer(string='Color Index', default=0)
    playground_ids = fields.Many2many(
        'command.playground', 'command_playground_tag_rel', 'tag_id', 'playground_id',
        string='Playground Sessions',
    )
    playground_count = fields.Integer(compute='_compute_playground_count', string='Session Count')

    @api.depends('playground_ids')
    def _compute_playground_count(self):
        for rec in self:
            rec.playground_count = len(rec.playground_ids)

    def action_view_playgrounds(self):
        """Action smart button untuk membuka daftar session playground yang menggunakan tag ini."""
        self.ensure_one()
        return {
            'name': f'Playground Sessions with Tag {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'command.playground',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.playground_ids.ids)],
        }



