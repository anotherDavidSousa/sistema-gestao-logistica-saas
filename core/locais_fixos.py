"""
Locais fixos — areas importantes para rastreamento de frota.
Definidos em codigo, nao alteraveis pelos usuarios.

Para adicionar: inclua uma entrada na lista LOCAIS_FIXOS e faca deploy.

Formato:
    id       — slug unico (sem espacos ou acentos)
    nome     — nome exibido nos cards e no mapa
    cor      — cor hexadecimal da area
    icone    — classes Font Awesome 5
    poligono — lista de [lat, lng] definindo os vertices (sentido horario ou anti-horario)
"""

LOCAIS_FIXOS = [
    # Adicione os locais aqui quando tiver as coordenadas.
    # Exemplo de formato:
    # {
    #     "id": "usiminas_ipatinga",
    #     "nome": "Usiminas — Ipatinga",
    #     "cor": "#ef4444",
    #     "icone": "fas fa-industry",
    #     "poligono": [
    #         [-19.470, -42.530],
    #         [-19.470, -42.510],
    #         [-19.490, -42.510],
    #         [-19.490, -42.530],
    #     ],
    # },
]
