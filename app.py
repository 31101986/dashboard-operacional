import dash 
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output  # type: ignore
import logging

# Import das páginas (relatórios)
import pages.relatorio1 as rel1
import pages.relatorio2 as rel2
import pages.relatorio3 as rel3
import pages.relatorio4 as rel4
import pages.relatorio5 as rel5

# ---------------------------------------------------------------------------
# Configuração de log
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
logger_format = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
console_handler.setFormatter(logger_format)
logger.addHandler(console_handler)

logger.info("Iniciando a aplicação Dash...")

# ---------------------------------------------------------------------------
# Configurações de estilo externas – tema LUX, Font Awesome e animate.css
# ---------------------------------------------------------------------------
external_stylesheets = [
    dbc.themes.LUX,
    "https://use.fontawesome.com/releases/v5.8.1/css/all.css",
    "https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css",
]

# ---------------------------------------------------------------------------
# Criação do app Dash
# ---------------------------------------------------------------------------
app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=external_stylesheets
)

app.title = "Portal de Relatórios - Mineração"
server = app.server

# ---------------------------------------------------------------------------
# Navbar responsiva com toggler para dispositivos móveis
# ---------------------------------------------------------------------------
navbar = dbc.Navbar(
    dbc.Container([
        dbc.NavbarBrand("Mineração", href="/", className="ms-2"),
        dbc.NavbarToggler(id="navbar-toggler"),
        dbc.Collapse(
            dbc.Nav(
                [
                    dbc.NavLink("Portal", href="/", active="exact"),
                    dbc.NavLink("Ciclo", href="/relatorio1", active="exact"),
                    dbc.NavLink("Informativo de Produção", href="/relatorio2", active="exact"),
                    dbc.NavLink("Avanço Financeiro", href="/relatorio3", active="exact"),
                    dbc.NavLink("Produção", href="/relatorio4", active="exact"),
                    dbc.NavLink("Timeline de Apontamentos", href="/relatorio5", active="exact"),
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

# Callback para abrir/fechar a navbar em telas pequenas
@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [dash.State("navbar-collapse", "is_open")],
)
def toggle_navbar(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open

# ---------------------------------------------------------------------------
# Layout da página inicial (Portal) com cards aprimorados
# ---------------------------------------------------------------------------
home_layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.H1("Portal de Relatórios para Mineração", className="text-center my-4"),
                width=12
            )
        ),
        # Linha com os 4 primeiros cards
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardImg(
                                src="/assets/mining.jpg",
                                top=True,
                                style={"height": "180px", "objectFit": "cover"}
                            ),
                            dbc.CardBody(
                                [
                                    html.H4("Ciclo", className="card-title"),
                                    html.P("Análise de Hora", className="card-text"),
                                    dcc.Link("Visualizar", href="/relatorio1", className="btn btn-primary")
                                ]
                            )
                        ],
                        style={"maxWidth": "18rem", "width": "100%", "margin": "auto"},
                        className="card-hover animate__animated animate__fadeInUp"
                    ),
                    width=12, md=3
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardImg(
                                src="/assets/mining2.jpg",
                                top=True,
                                style={"height": "180px", "objectFit": "cover"}
                            ),
                            dbc.CardBody(
                                [
                                    html.H4("Informativo de Produção", className="card-title"),
                                    html.P("Análise de Produção", className="card-text"),
                                    dcc.Link("Visualizar", href="/relatorio2", className="btn btn-primary")
                                ]
                            )
                        ],
                        style={"maxWidth": "18rem", "width": "100%", "margin": "auto"},
                        className="card-hover animate__animated animate__fadeInUp"
                    ),
                    width=12, md=3
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardImg(
                                src="/assets/mining3.jpg",
                                top=True,
                                style={"height": "180px", "objectFit": "cover"}
                            ),
                            dbc.CardBody(
                                [
                                    html.H4("Avanço Financeiro", className="card-title"),
                                    html.P("Avanço Financeiro", className="card-text"),
                                    dcc.Link("Visualizar", href="/relatorio3", className="btn btn-primary")
                                ]
                            )
                        ],
                        style={"maxWidth": "18rem", "width": "100%", "margin": "auto"},
                        className="card-hover animate__animated animate__fadeInUp"
                    ),
                    width=12, md=3
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardImg(
                                src="/assets/mining4.jpg",
                                top=True,
                                style={"height": "180px", "objectFit": "cover"}
                            ),
                            dbc.CardBody(
                                [
                                    html.H4("Produção - Indicadores", className="card-title"),
                                    html.P("Produção - Indicadores", className="card-text"),
                                    dcc.Link("Visualizar", href="/relatorio4", className="btn btn-primary")
                                ]
                            )
                        ],
                        style={"maxWidth": "18rem", "width": "100%", "margin": "auto"},
                        className="card-hover animate__animated animate__fadeInUp"
                    ),
                    width=12, md=3
                ),
            ],
            className="my-4 justify-content-center"
        ),
        # Linha com o card do Relatório 5
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardImg(
                            src="/assets/mining5.jpg",
                            top=True,
                            style={"height": "180px", "objectFit": "cover"}
                        ),
                        dbc.CardBody(
                            [
                                html.H4("Timeline Apontamentos", className="card-title"),
                                html.P("Equipamentos de Produção", className="card-text"),
                                dcc.Link("Visualizar", href="/relatorio5", className="btn btn-primary")
                            ]
                        )
                    ],
                    style={"maxWidth": "18rem", "width": "100%", "margin": "auto"},
                    className="card-hover animate__animated animate__fadeInUp"
                ),
                width=12, md=3,
                className="mt-4"
            ),
            className="justify-content-center"
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

# ---------------------------------------------------------------------------
# Layout principal com dcc.Location e Spinner (feedback de carregamento)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Callback para trocar conteúdo da página com base na URL
# ---------------------------------------------------------------------------
@app.callback(Output("page-content", "children"), [Input("url", "pathname")])
def display_page(pathname):
    logger.info(f"Navegando para {pathname}")
    if pathname == "/relatorio1":
        return rel1.layout
    elif pathname == "/relatorio2":
        return rel2.layout
    elif pathname == "/relatorio3":
        return rel3.layout
    elif pathname == "/relatorio4":
        return rel4.layout
    elif pathname == "/relatorio5":
        return rel5.layout
    else:
        return home_layout

# ---------------------------------------------------------------------------
# Execução do servidor local
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Executando o servidor no modo debug...")
    app.run_server(debug=True, host="0.0.0.0", port=8050)
