{
    'name': 'Odoo ORM Command Playground',
    'version': '18.0.1.0.0',
    'category': 'Technical/Training',
    'summary': 'Interactive Playground & Live Visualizer for Odoo ORM Commands (0 to 6)',
    'description': """
Odoo ORM Command Playground
===========================
Modul interaktif khusus pembelajaran developer Odoo untuk memahami dan bereksperimen
dengan 7 jenis Command ORM pada relasi One2many dan Many2many:

* Command 0: Command.create(vals) / (0, 0, vals) -> Create child record
* Command 1: Command.update(id, vals) / (1, id, vals) -> Update child record
* Command 2: Command.delete(id) / (2, id, 0) -> Delete child record from DB
* Command 3: Command.unlink(id) / (3, id, 0) -> Unlink relation (no delete)
* Command 4: Command.link(id) / (4, id, 0) -> Link existing record
* Command 5: Command.clear() / (5, 0, 0) -> Clear all relations
* Command 6: Command.set(ids) / (6, 0, ids) -> Replace all relations
    """,
    'author': 'JPFA Dev Training',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'data/playground_demo_data.xml',
        'views/command_playground_views.xml',
        'wizards/command_custom_runner_wizard_views.xml',
    ],
    'license': 'LGPL-3',
    'application': True,
    'installable': True,
}

