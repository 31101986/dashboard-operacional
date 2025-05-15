from __future__ import annotations

"""
app.py – Portal de Relatórios (versão otimizada)

Mantém todas as funcionalidades originais do portal de mineração, com melhorias em performance e organização.
As datas são manipuladas em UTC no backend, com conversão para o fuso local no frontend via JavaScript,
garantindo que o horário exibido seja o do usuário.
Adiciona seleção de projetos na página inicial para alternar entre 5 bancos de dados.

Otimizações de performance:
- Cache aplicado ao layout da página inicial e navbar.
- Intervalo de atualização do horário movido para navbar e reduzido para 5s.
- Timeout do cache aumentado para 30 minutos.
- Sugestões para relatórios: cache em callbacks, filtros iniciais, paginação, agregação de dados.
"""

# ============================================================
# IMPORTAÇÕES
# ============================================================
import logging
import os
import sys
from typing import Dict
from datetime import datetime, timedelta, timezone

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html
from flask_caching import Cache

from config import logger as root_logger, TIMEZONE, PROJECTS_CONFIG, PROJECT_LABELS

# ============================================================
# CONFIGURAÇÕES INICIAIS
# ============================================================

# Configuração de logging
logger = root_logger.getChild(__name__)
logger.info("Inicializando aplicação Dash...")

# Variáveis globais de data (em UTC)
DAY_END: datetime = datetime.now(timezone.utc)
DAY_START: datetime = DAY_END - timedelta(days=3)

# Configuração da aplicação Dash
EXTERNAL_STYLESHEETS = [
    dbc.themes.LUX,
    "https://use.fontawesome.com/releases/v5.8.1/css/all.css",
    "https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css",
]

app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=EXTERNAL_STYLESHEETS,
    title="Portal de Relatórios - Mineração"
)
server = app.server

# Configuração do cache (timeout aumentado para 30 minutos)
cache = Cache(app.server, config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 1800})

# Expor o módulo como "app" para compatibilidade
sys.modules.setdefault("app", sys.modules[__name__])

# Importação dos relatórios (restaurada como no original)
import pages.relatorio1 as rel1
#import pages.relatorio2 as rel2
#import pages.relatorio3 as rel3
import pages.relatorio4 as rel4
import pages.relatorio5 as rel5
import pages.relatorio6 as rel6
import pages.relatorio7 as rel7

# ============================================================
# DEFINIÇÕES DE PÁGINAS E CARDS
# ============================================================

# Mapeamento de rotas para layouts
PAGES: Dict[str, html.Div] = {
    "/relatorio1": rel1.layout,
    #"/relatorio2": rel2.layout,
    #"/relatorio3": rel3.layout,
    "/relatorio4": rel4.layout,
    "/relatorio5": rel5.layout,
    "/relatorio6": rel6.layout,
    "/relatorio7": rel7.layout,
}

# Definições de cards (rota, título, subtítulo)
PAGE_DEFS = [
    ("/relatorio1", "Ciclo", "Análise de Hora"),
    #("/relatorio2", "Informativo de Produção", "Análise de Produção"),
    #("/relatorio3", "Avanço Financeiro", "Avanço Financeiro"),
    ("/relatorio4", "Produção - Indicadores", "Produção - Indicadores"),
    ("/relatorio5", "Timeline de Apontamentos", "Equipamentos de Produção"),
    ("/relatorio6", "Manutenção", "Novo Relatório"),
    ("/relatorio7", "Produção Acumulada", "Análise de Produção"),
]

# Imagens dos cards
CARD_IMAGES = [
    "/assets/mining.jpg",
    "/assets/mining2.jpg",
    "/assets/mining3.jpg",
    "/assets/mining4.jpg",
    "/assets/mining5.jpg",
    "/assets/mining6.jpg",
    "/assets/mining7.jpg",
]

# Ícones para links da navbar
NAVBAR_ICONS = {
    "/": "fa-home",
    "/relatorio1": "fa-clock",
    #"/relatorio2": "fa-industry",
    #"/relatorio3": "fa-dollar-sign",
    "/relatorio4": "fa-chart-bar",
    "/relatorio5": "fa-stream",
    "/relatorio6": "fa-wrench",
    "/relatorio7": "fa-chart-pie",
}

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def profile_time(func):
    """
    Decorador para medir o tempo de execução de funções e registrar no log.

    Args:
        func: Função a ser perfilada.

    Returns:
        Função embrulhada com medição de tempo.
    """
    import time
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = func(*args, **kwargs)
        t1 = time.perf_counter()
        logger.info(f"[Profile] {func.__name__} executada em {t1 - t0:.4f} segundos")
        return result
    return wrapper

@cache.memoize()
def create_navbar() -> dbc.Navbar:
    """
    Cria a navbar com links, ícones, horário local e gradiente suave.
    Inclui dcc.Interval para atualizar o horário local a cada 5s.

    Returns:
        dbc.Navbar: Componente de navegação.
    """
    nav_links = [
        dbc.NavLink([
            html.I(className=f"fas {NAVBAR_ICONS[path]} mr-1"),
            title
        ], href=path, active="exact", className="mx-1", style={"transition": "all 0.3s"})
        for path, title in [
            ("/", "Portal"),
            ("/relatorio1", "Ciclo"),
            #("/relatorio2", "Informativo"),
            #("/relatorio3", "Financeiro"),
            ("/relatorio4", "Produção"),
            ("/relatorio5", "Timeline"),
            ("/relatorio6", "Manutenção"),
            ("/relatorio7", "Acumulada"),
        ]
    ]

    return dbc.Navbar(
        [
            dbc.Container([
                dbc.NavbarBrand([
                    html.I(className="fas fa-chart-line mr-2"),
                    "Mineração"
                ], href="/", className="ms-2 d-flex align-items-center", style={"fontSize": "1.1rem"}),
                html.Div([
                    html.Span(id="local-time", style={
                        "fontWeight": "bold",
                        "fontSize": "0.85rem",
                        "backgroundColor": "rgba(255,255,255,0.1)",
                        "padding": "4px 8px",
                        "borderRadius": "12px",
                        "color": "#fff"
                    })
                ], className="ms-auto me-3 d-flex align-items-center"),
                dbc.NavbarToggler(id="navbar-toggler"),
                dbc.Collapse(
                    dbc.Nav(nav_links, pills=True, className="ms-auto", navbar=True),
                    id="navbar-collapse",
                    navbar=True,
                    is_open=False
                )
            ], fluid=True),
            dcc.Interval(id="time-interval", interval=5000, n_intervals=0)  # Restaurado para 5s
        ],
        color="dark",
        dark=True,
        sticky="top",
        style={
            "background": "linear-gradient(90deg, #343a40, #495057)",
            "borderBottom": "1px solid rgba(255,255,255,0.1)",
            "padding": "0.5rem 0",
            "fontSize": "0.9rem"
        }
    )

# Definir navbar como constante global para evitar recriação
NAVBAR = create_navbar()

@cache.memoize()
def create_card(img_src: str, title: str, subtitle: str, link_text: str, href: str) -> dbc.Card:
    """
    Cria um card com imagem, título, subtítulo e botão de navegação.

    Args:
        img_src (str): URL da imagem do card.
        title (str): Título do card.
        subtitle (str): Subtítulo do card.
        link_text (str): Texto do botão.
        href (str): URL de destino.

    Returns:
        dbc.Card: Componente de card.
    """
    return dbc.Card(
        [
            dbc.CardImg(
                src=img_src,
                top=True,
                style={"height": "150px", "objectFit": "cover", "borderTopLeftRadius": "12px", "borderTopRightRadius": "12px"}
            ),
            dbc.CardBody(
                [
                    html.H4(title, className="card-title", style={"fontSize": "1.1rem", "fontWeight": "500"}),
                    html.P(subtitle, className="card-text", style={"fontSize": "0.85rem", "color": "#6c757d"}),
                    dcc.Link([
                        html.I(className="fas fa-eye mr-1"),
                        link_text
                    ], href=href, className="btn btn-primary btn-sm", style={
                        "borderRadius": "10px",
                        "background": "linear-gradient(45deg, #007bff, #00aaff)",
                        "transition": "all 0.3s",
                        "padding": "6px 12px"
                    })
                ],
                style={"padding": "0.8rem"}
            )
        ],
        style={
            "width": "100%",
            "maxWidth": "95vw",
            "margin": "0.5rem auto",
            "borderRadius": "12px",
            "border": "none"
        },
        className="card-hover animate__animated animate__zoomIn shadow-md"
    )

# ============================================================
# LAYOUT DA PÁGINA INICIAL
# ============================================================

@cache.memoize()
def create_home_layout() -> dbc.Container:
    """
    Cria o layout da página inicial com cards para navegação e seleção de projetos.
    Cacheado para reduzir tempo de renderização.

    Returns:
        dbc.Container: Layout do portal.
    """
    card_rows = [
        dbc.Row(
            [
                dbc.Col(
                    create_card(img_src, title, subtitle, "Visualizar", href),
                    className="col-12 col-sm-6 col-md-3 mb-2"  # Ajustado para classes Bootstrap fixas
                )
                for (href, title, subtitle), img_src in zip(PAGE_DEFS[i:i+4], CARD_IMAGES[i:i+4])
            ],
            className="my-2 justify-content-center"
        )
        for i in range(0, len(PAGE_DEFS), 4)
    ]

    return dbc.Container(
        [
            dbc.Row(
                dbc.Col(
                    html.H1("Portal de Relatórios para Mineração", className="text-center my-4", style={"fontSize": "1.6rem", "fontWeight": "500"}),
                    className="col-12"  # Ajustado para classe Bootstrap fixa
                )
            ),
            dbc.Row(
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardBody(
                                [
                                    html.Label(
                                        "Selecionar Obra",
                                        style={"fontSize": "1rem", "fontWeight": "500", "color": "#495057", "marginBottom": "0.5rem"}
                                    ),
                                    dbc.Select(
                                        id='projeto-dropdown',
                                        options=[
                                            {'value': projeto, 'label': PROJECT_LABELS[projeto]}
                                            for projeto in PROJECTS_CONFIG.keys()
                                        ],
                                        value=None,
                                        placeholder="Selecione uma obra",
                                        className="form-control-lg",
                                        style={
                                            "borderRadius": "6px",
                                            "borderColor": "#17a2b8",
                                            "backgroundColor": "#fff",
                                            "fontSize": "1rem",
                                            "fontWeight": "400",
                                            "transition": "all 0.4s ease",
                                            "cursor": "pointer"
                                        }
                                    )
                                ],
                                style={"padding": "0.75rem"}
                            )
                        ],
                        style={
                            "maxWidth": "400px",
                            "marginLeft": "20px",
                            "marginBottom": "30px",
                            "borderRadius": "6px",
                            "border": "1px solid #dee2e6",
                            "boxShadow": "0 2px 8px rgba(0,0,0,0.1)",
                            "transition": "transform 0.4s ease, box-shadow 0.4s ease",
                            "backgroundColor": "#f8f9fa"
                        },
                        className="animate__animated animate__fadeInUp"
                    ),
                    className="col-12 col-sm-6 col-md-4"  # Ajustado para classes Bootstrap fixas
                ),
                justify="start"
            ),
            *card_rows,
            dbc.Row(
                dbc.Col(
                    html.Footer([
                        html.I(className="fas fa-copyright mr-1"),
                        " 2025 Raphael Leal Sistemas e Soluções para Mineração"
                    ], className="text-center py-3", style={
                        "background": "linear-gradient(90deg, #f8f9fa, #e9ecef)",
                        "color": "#495057",
                        "fontSize": "0.9rem"
                    }),
                    className="col-12"  # Ajustado para classe Bootstrap fixa
                )
            )
        ],
        fluid=True,
        className="p-0"  # Garantido como string
    )

# ============================================================
# LAYOUT PRINCIPAL E CALLBACKS
# ============================================================

app.layout = html.Div(
    [
        dcc.Location(id="url", refresh=False),
        NAVBAR,  # Usar navbar pré-renderizada
        dcc.Store(id='projeto-store', data=None),  # Armazena o projeto selecionado globalmente
        dbc.Spinner(
            html.Div(id="page-content"),
            size="sm",
            color="primary",
            fullscreen=False,
            spinnerClassName=None
        ),
    ]
)

@profile_time
@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def render_page_content(pathname: str) -> html.Div:
    """
    Renderiza o conteúdo da página com base na URL.

    Args:
        pathname (str): Caminho da URL.

    Returns:
        html.Div: Layout da página correspondente.
    """
    logger.info(f"Navegando para {pathname}")
    return PAGES.get(pathname, create_home_layout())

@app.callback(
    Output("navbar-collapse", "is_open"),
    Input("navbar-toggler", "n_clicks"),
    State("navbar-collapse", "is_open")
)
def toggle_navbar_collapse(n_clicks: int, is_open: bool) -> bool:
    """
    Alterna o estado de abertura do menu da navbar.

    Args:
        n_clicks (int): Número de cliques no toggler.
        is_open (bool): Estado atual do menu.

    Returns:
        bool: Novo estado do menu.
    """
    if n_clicks:
        return not is_open
    return is_open

@app.callback(
    Output("projeto-store", "data"),
    Input("projeto-dropdown", "value")
)
def update_projeto_store(projeto: str) -> str:
    """
    Atualiza o projeto selecionado no store.

    Args:
        projeto (str): Projeto selecionado no dropdown.

    Returns:
        str: Projeto selecionado ou None se não selecionado.
    """
    logger.debug(f"Projeto selecionado: {projeto}")
    return projeto

app.clientside_callback(
    """
    function(n_intervals) {
        var now = new Date();
        return now.toLocaleString();
    }
    """,
    Output("local-time", "children"),
    Input("time-interval", "n_intervals")
)

# ============================================================
# EXECUÇÃO DO SERVIDOR
# ============================================================

if __name__ == "__main__":
    debug_mode: bool = os.environ.get("DEBUG", "True").lower() in ("true", "1", "yes")
    port: int = int(os.environ.get("PORT", 8050))
    logger.info(f"Iniciando servidor {'no modo debug' if debug_mode else ''} na porta {port}...")
    app.run(debug=debug_mode, host="0.0.0.0", port=port)
    