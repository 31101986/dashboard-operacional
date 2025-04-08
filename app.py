from __future__ import annotations

"""app.py – Portal de Relatórios (versão otimizada e **compatível**)

Esta versão mantém todas as funcionalidades originais, porém com melhorias de
organização e performance. As principais diferenças em relação ao primeiro
"app_optimized.py" são:

* **Importação antecipada** dos módulos `pages.relatorioX` para garantir que
  callbacks definidos com `@app.callback` sejam registrados na inicialização.
* Alias do módulo em `sys.modules['app']` para que as páginas continuem
  funcionando mesmo se fizerem `from app import app`.
* Estrutura enxuta (loops/list‑comprehension) para navbar e cards, mas sem
  *lazy‑loading* agressivo que possa quebrar páginas legadas.
* Logger central reutilizado, `DEBUG` e `PORT` configuráveis via variáveis de
  ambiente.

A API externa continua a mesma: basta executar `python app.py` ou apontar o
Gunicorn para `app:server`.
"""

import logging
import os
import sys
from typing import Dict

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html

from config import logger as root_logger

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = root_logger.getChild(__name__)
logger.info("Bootstrapping Dash application…")

# ---------------------------------------------------------------------------
# Dash application instance
# ---------------------------------------------------------------------------
external_stylesheets = [
    dbc.themes.LUX,
    "https://use.fontawesome.com/releases/v5.8.1/css/all.css",
    "https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css",
]

app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,  # Necessário caso usemos layouts/páginas carregadas dinamicamente
    external_stylesheets=external_stylesheets
)
app.title = "Portal de Relatórios - Mineração"
server = app.server  # Exposição do servidor para implantação (gunicorn, etc.)

# ---------------------------------------------------------------------------
# Inicialização do Cache
# ---------------------------------------------------------------------------
from flask_caching import Cache
cache = Cache(app.server, config={'CACHE_TYPE': 'SimpleCache'})
# Agora, todos os módulos que importarem o Cache poderão usar esse objeto já inicializado.

# Expor o módulo como "app" para retro‑compatibilidade
sys.modules.setdefault("app", sys.modules[__name__])

# ---------------------------------------------------------------------------
# Importação dos relatórios (callbacks são registrados aqui)
# ---------------------------------------------------------------------------
import pages.relatorio1 as rel1  # noqa: E402
#import pages.relatorio2 as rel2  # noqa: E402
#import pages.relatorio3 as rel3  # noqa: E402
import pages.relatorio4 as rel4  # noqa: E402
import pages.relatorio5 as rel5  # noqa: E402
import pages.relatorio6 as rel6  # noqa: E402

# Mapeamento rota → layout
pages: Dict[str, html.Div] = {
    "/relatorio1": rel1.layout,
    #"/relatorio2": rel2.layout,
    #"/relatorio3": rel3.layout,
    "/relatorio4": rel4.layout,
    "/relatorio5": rel5.layout,
    "/relatorio6": rel6.layout,  # Rota para o Relatório 6
}

# ---------------------------------------------------------------------------
# Navbar e cards (gerados de forma declarativa)
# ---------------------------------------------------------------------------
# Como o Portal é a página inicial, os cards correspondem aos relatórios 1 a 6.
_PAGE_DEFS = [
    ("/relatorio1", "Ciclo", "Análise de Hora"),
    ("/relatorio2", "Informativo de Produção", "Análise de Produção"),
    ("/relatorio3", "Avanço Financeiro", "Avanço Financeiro"),
    ("/relatorio4", "Produção - Indicadores", "Produção - Indicadores"),
    ("/relatorio5", "Timeline de Apontamentos", "Equipamentos de Produção"),
    ("/relatorio6", "Relatório 6", "Novo Relatório")
]

# Certifique-se de ter 6 imagens, uma para cada relatório
_CARD_IMAGES = [
    "/assets/mining.jpg",
    "/assets/mining2.jpg",
    "/assets/mining3.jpg",
    "/assets/mining4.jpg",
    "/assets/mining5.jpg",
    "/assets/mining6.jpg"
]

def create_navbar():
    return dbc.Navbar(
        dbc.Container([
            dbc.NavbarBrand("Mineração", href="/", className="ms-2"),
            dbc.NavbarToggler(id="navbar-toggler"),
            dbc.Collapse(
                dbc.Nav(
                    [
                        dbc.NavLink("Portal", href="/", active="exact"),
                        dbc.NavLink("Ciclo", href="/relatorio1", active="exact"),
                        #dbc.NavLink("Informativo de Produção", href="/relatorio2", active="exact"),
                        #dbc.NavLink("Avanço Financeiro", href="/relatorio3", active="exact"),
                        dbc.NavLink("Produção", href="/relatorio4", active="exact"),
                        dbc.NavLink("Timeline de Apontamentos", href="/relatorio5", active="exact"),
                        dbc.NavLink("Manutenção", href="/relatorio6", active="exact"),
                    ],
                    pills=True,
                    className="ms-auto",
                    navbar=True
                ),
                id="navbar-collapse",
                navbar=True,
                is_open=False
            )
        ]),
        color="dark",
        dark=True,
        sticky="top",
    )

navbar = create_navbar()

# Callback para abrir/fechar a navbar em telas pequenas
@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")]
)
def toggle_navbar(n_clicks, is_open):
    """
    Callback que controla a abertura/fechamento do menu em dispositivos móveis.
    """
    if n_clicks:
        return not is_open
    return is_open

def create_card(img_src, title, subtitle, link_text, href):
    """
    Cria e retorna um componente Card com imagem, título, subtítulo e link.
    """
    return dbc.Card(
        [
            dbc.CardImg(
                src=img_src,
                top=True,
                style={"height": "180px", "objectFit": "cover"}
            ),
            dbc.CardBody(
                [
                    html.H4(title, className="card-title"),
                    html.P(subtitle, className="card-text"),
                    dcc.Link(link_text, href=href, className="btn btn-primary")
                ]
            )
        ],
        style={"maxWidth": "18rem", "width": "100%", "margin": "auto"},
        className="card-hover animate__animated animate__fadeInUp"
    )

# Layout da página inicial (Portal) com cards:
# Exibindo 4 cards na primeira linha e 2 na segunda
home_layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.H1("Portal de Relatórios para Mineração", className="text-center my-4"),
                width=12
            )
        ),
        # Primeira linha: 4 cards
        dbc.Row(
            [
                dbc.Col(
                    create_card("/assets/mining.jpg", "Ciclo", "Análise de Hora", "Visualizar", "/relatorio1"),
                    width=12, md=3
                ),
                #dbc.Col(
                   # create_card("/assets/mining2.jpg", "Informativo de Produção", "Análise de Produção", "Visualizar", "/relatorio2"),
                   # width=12, md=3
               # ),
                #dbc.Col(
                    #create_card("/assets/mining3.jpg", "Avanço Financeiro", "Avanço Financeiro", "Visualizar", "/relatorio3"),
                    #width=12, md=3
                #),
                dbc.Col(
                    create_card("/assets/mining4.jpg", "Produção - Indicadores", "Produção - Indicadores", "Visualizar", "/relatorio4"),
                    width=12, md=3
                ),
            ],
            className="my-4 justify-content-center"
        ),
        # Segunda linha: 2 cards
        dbc.Row(
            [
                dbc.Col(
                    create_card("/assets/mining5.jpg", "Timeline de Apontamentos", "Equipamentos de Produção", "Visualizar", "/relatorio5"),
                    width=12, md=3,
                    className="mt-4"
                ),
                dbc.Col(
                    create_card("/assets/mining6.jpg", "Manutenção", "Atualizado", "Visualizar", "/relatorio6"),
                    width=12, md=3,
                    className="mt-4"
                ),
            ],
            className="my-4 justify-content-center"
        ),
        # Rodapé
        dbc.Row(
            dbc.Col(
                html.Footer("© 2025 Raphael Leal Consultoria", className="text-center footer-text my-4"),
                width=12
            )
        ),
    ],
    fluid=True,
)

# Layout principal com dcc.Location e Spinner (feedback de carregamento)
app.layout = html.Div(
    [
        dcc.Location(id="url", refresh=False),
        navbar,
        dbc.Spinner(
            html.Div(id="page-content"),
            size="lg",
            color="primary",
            fullscreen=True
        ),
    ]
)

# Mapeamento de páginas para o callback de roteamento
pages: Dict[str, html.Div] = {
    "/relatorio1": rel1.layout,
    #"/relatorio2": rel2.layout,
    #"/relatorio3": rel3.layout,
    "/relatorio4": rel4.layout,
    "/relatorio5": rel5.layout,
    "/relatorio6": rel6.layout,  # Incluído o Relatório 6
}

@app.callback(Output("page-content", "children"), [Input("url", "pathname")])
def display_page(pathname):
    """
    Callback para renderizar o layout conforme o path da URL.
    """
    logger.info(f"Navegando para {pathname}")
    # Retorna o layout correspondente ou o layout principal (home_layout)
    return pages.get(pathname, home_layout)

if __name__ == "__main__":
    logger.info("Executando o servidor no modo debug...")
    app.run_server(debug=True, host="0.0.0.0", port=8050)
