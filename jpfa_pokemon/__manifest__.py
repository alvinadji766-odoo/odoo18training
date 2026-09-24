{
    'name': 'Pokemon Pokédex (REST API Client)',
    'version': '18.0.1.0.0',
    'category': 'Extra Tools',
    'summary': 'Contoh modul sederhana integrasi REST API PokeAPI ke Odoo',
    'description': """
        Modul latihan untuk memahami pemanggilan External REST API (PokeAPI):
        - Mengambil data Pokemon dari https://pokeapi.co/api/v2/pokemon/{name}
        - Wizard pencarian sederhana & download gambar sprite
        - Menyimpan data stat dan atribut Pokemon ke dalam Odoo
        - Mock Offline Fallback jika tanpa koneksi internet
    """,
    'author': 'JPFA Training Team',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/pokemon_views.xml',
        'wizards/pokemon_fetch_wizard_views.xml',
        'views/menu.xml',
    ],
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}
