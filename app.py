from __future__ import annotations

"""
app.py – Portal de Relatórios (versão otimizada e compatível)

Esta versão mantém todas as funcionalidades originais, com melhorias de organização, performance,
gerenciamento de recursos e profiling. Nesta versão, as datas são manipuladas em UTC no backend
e a conversão para o fuso local é feita no front‑end via JavaScript, garantindo que o horário exibido 
no Render (ou em qualquer navegador) seja o horário local do usuário.
    
Para executar:
  - Basta executar `python app.py`
  - Ou apontar o Gunicorn para `app:server`
"""

import logging
import os
import sys
from typing import Dict

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html

from config import logger as root_logger, TIMEZONE  # TIMEZONE pode continuar sendo usado para outros cálculos

# ---------------------------------------------------------------------------
# OBS.: Nesta versão não forçamos a alteração de timezone via os.environ nem time.tzset(),
# pois queremos que o backend trabalhe em UTC e o front‑end converta para o fuso local do usuário.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = root_logger.getChild(__name__)
logger.info("Bootstrapping Dash application…")

# ---------------------------------------------------------------------------
# Definir variáveis de data para cálculos internos (em UTC ou convertendo conforme TIMEZONE se necessário)
# ---------------------------------------------------------------------------
from datetime import datetime, timezone, timedelta
# Exemplo: obtém a data atual em UTC e, se necessário, outros cálculos podem usar TIMEZONE.
DAY_END: datetime = datetime.now(timezone.utc)
DAY_START: datetime = DAY_END - timedelta(days=3)

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

# Mapeamento de rota → layout
pages: Dict[str, html.Div] = {
    "/relatorio1": rel1.layout,
    #"/relatorio2": rel2.layout,
    #"/relatorio3": rel3.layout,
    "/relatorio4": rel4.layout,
    "/relatorio5": rel5.layout,
    "/relatorio6": rel6.layout,  # Rota para o Relatório 6
}

# ---------------------------------------------------------------------------
# Decorador de Profiling
# ---------------------------------------------------------------------------
def profile_time(func):
    """
    Decorador para medir o tempo de execução da função e registrar essa informação no log.
    """
    import time
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = func(*args, **kwargs)
        t1 = time.perf_counter()
        logger.info(f"[Profile] {func.__name__} executed in {t1 - t0:.4f} seconds")
        return result
    return wrapper

# ---------------------------------------------------------------------------
# Navbar e cards (gerados de forma declarativa)
# ---------------------------------------------------------------------------
_PAGE_DEFS = [
    ("/relatorio1", "Ciclo", "Análise de Hora"),
    ("/relatorio2", "Informativo de Produção", "Análise de Produção"),
    ("/relatorio3", "Avanço Financeiro", "Avanço Financeiro"),
    ("/relatorio4", "Produção - Indicadores", "Produção - Indicadores"),
    ("/relatorio5", "Timeline de Apontamentos", "Equipamentos de Produção"),
    ("/relatorio6", "Relatório 6", "Novo Relatório")
]

_CARD_IMAGES = [
    "/assets/mining.jpg",
    "/assets/mining2.jpg",
    "/assets/mining3.jpg",
    "/assets/mining4.jpg",
    "/assets/mining5.jpg",
    "/assets/mining6.jpg"
]

def create_navbar() -> dbc.Navbar:
    """Cria e retorna uma navbar para o portal."""
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

@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")]
)
def toggle_navbar(n_clicks: int, is_open: bool) -> bool:
    """
    Callback que controla a abertura/fechamento do menu em dispositivos móveis.
    """
    if n_clicks:
        return not is_open
    return is_open

def create_card(img_src: str, title: str, subtitle: str, link_text: str, href: str) -> dbc.Card:
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

# Layout da página inicial (Portal) com cards e exibição do horário local
home_layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.H1("Portal de Relatórios para Mineração", className="text-center my-4"),
                width=12
            )
        ),
        # Linha para exibição dinâmica do horário local (no fuso do navegador)
        dbc.Row(
            dbc.Col(
                html.Div([
                    html.H5("Horário Local:"),
                    html.Div(id="local-time", style={"fontWeight": "bold", "fontSize": "1.2rem"})
                ], className="text-center my-2"),
                width=12
            )
        ),
        # Intervalo para atualizar o horário a cada 1 segundo
        dcc.Interval(id="time-interval", interval=1000, n_intervals=0),
        # Primeira linha: 4 cards
        dbc.Row(
            [
                dbc.Col(
                    create_card(_CARD_IMAGES[0], "Ciclo", "Análise de Hora", "Visualizar", "/relatorio1"),
                    width=12, md=3
                ),
                #dbc.Col(
                    #create_card(_CARD_IMAGES[1], "Informativo de Produção", "Análise de Produção", "Visualizar", "/relatorio2"),
                    #width=12, md=3
                #),
                #dbc.Col(
                    #create_card(_CARD_IMAGES[2], "Avanço Financeiro", "Avanço Financeiro", "Visualizar", "/relatorio3"),
                    #width=12, md=3
                #),
                dbc.Col(
                    create_card(_CARD_IMAGES[3], "Produção - Indicadores", "Produção - Indicadores", "Visualizar", "/relatorio4"),
                    width=12, md=3
                ),
            ],
            className="my-4 justify-content-center"
        ),
        # Segunda linha: 2 cards
        dbc.Row(
            [
                dbc.Col(
                    create_card(_CARD_IMAGES[4], "Timeline de Apontamentos", "Equipamentos de Produção", "Visualizar", "/relatorio5"),
                    width=12, md=3,
                    className="mt-4"
                ),
                dbc.Col(
                    create_card(_CARD_IMAGES[5], "Manutenção", "Novo Relatório", "Visualizar", "/relatorio6"),
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
    fluid=True
)

# Layout principal com dcc.Location e Spinner (feedback de carregamento)
app.layout = html.Div(
    [
        dcc.Location(id="url", refresh=False),
        navbar,
        # Aqui o horário local é exibido de forma dinâmica em todas as páginas
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
    "/relatorio6": rel6.layout,  # Rota para o Relatório 6
}

@profile_time
@app.callback(Output("page-content", "children"), [Input("url", "pathname")])
def display_page(pathname: str) -> html.Div:
    """
    Callback para renderizar o layout conforme o path da URL.
    Retorna o layout correspondente ou o layout principal (home_layout).
    """
    logger.info(f"Navegando para {pathname}")
    return pages.get(pathname, home_layout)

# ---------------------------------------------------------------------------
# Callback clientside para atualizar dinamicamente o horário local
# ---------------------------------------------------------------------------
app.clientside_callback(
    """
    function(n_intervals) {
         var now = new Date();
         return now.toLocaleString();
    }
    """,
    Output("local-time", "children"),
    [Input("time-interval", "n_intervals")]
)

if __name__ == "__main__":
    debug_mode: bool = os.environ.get("DEBUG", "True").lower() in ("true", "1", "yes")
    port: int = int(os.environ.get("PORT", 8050))
    logger.info("Executando o servidor no modo debug…" if debug_mode else "Executando o servidor...")
    app.run_server(debug=debug_mode, host="0.0.0.0", port=port)
