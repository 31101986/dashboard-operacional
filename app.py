import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output

# Import das páginas (relatórios)
import pages.relatorio1 as rel1
import pages.relatorio2 as rel2
import pages.relatorio3 as rel3
import pages.relatorio4 as rel4  # Relatório 4

# External stylesheets – utilizando tema LUX, Font Awesome e animate.css para modernidade
external_stylesheets = [
    dbc.themes.LUX,
    "https://use.fontawesome.com/releases/v5.8.1/css/all.css",
    "https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css"
]

# Criação do app com supressão de exceções de callback (para páginas dinâmicas)
app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=external_stylesheets
)
server = app.server  # WSGI callable para deploy (Gunicorn, etc.)

# Navbar – um menu simples para navegação entre as páginas
navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dcc.Link("Portal", href="/", className="nav-link")),
        dbc.NavItem(dcc.Link("Ciclo", href="/relatorio1", className="nav-link")),
        dbc.NavItem(dcc.Link("Informático de Produção", href="/relatorio2", className="nav-link")),
        dbc.NavItem(dcc.Link("Avanço Financeiro", href="/relatorio3", className="nav-link")),
        dbc.NavItem(dcc.Link("Produção", href="/relatorio4", className="nav-link")),
    ],
    brand="Mineração",
    brand_href="/",
    color="dark",
    dark=True,
    sticky="top"
)

# Layout do Portal – página inicial com cards responsivos para cada relatório
home_layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.H1("Portal de Relatórios para Mineração", className="text-center my-4"),
                width=12
            )
        ),
        dbc.Row(
            [
                # Card Relatório 1
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardImg(src="/assets/mining.jpg", top=True, style={"height": "180px", "objectFit": "cover"}),
                            dbc.CardBody(
                                [
                                    html.H4("Ciclo", className="card-title"),
                                    html.P("Análise de Hora", className="card-text"),
                                    dcc.Link("Visualizar", href="/relatorio1", className="btn btn-primary")
                                ]
                            )
                        ],
                        style={"width": "18rem", "margin": "auto"}
                    ),
                    width=12, md=3
                ),
                # Card Relatório 2
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardImg(src="/assets/mining2.jpg", top=True, style={"height": "180px", "objectFit": "cover"}),
                            dbc.CardBody(
                                [
                                    html.H4("Informativo de Produção", className="card-title"),
                                    html.P("Análise de Produção", className="card-text"),
                                    dcc.Link("Visualizar", href="/relatorio2", className="btn btn-primary")
                                ]
                            )
                        ],
                        style={"width": "18rem", "margin": "auto"}
                    ),
                    width=12, md=3
                ),
                # Card Relatório 3
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardImg(src="/assets/mining3.jpg", top=True, style={"height": "180px", "objectFit": "cover"}),
                            dbc.CardBody(
                                [
                                    html.H4("Avanço Financeiro", className="card-title"),
                                    html.P("Avanço Financeiro", className="card-text"),
                                    dcc.Link("Visualizar", href="/relatorio3", className="btn btn-primary")
                                ]
                            )
                        ],
                        style={"width": "18rem", "margin": "auto"}
                    ),
                    width=12, md=3
                ),
                # Card Relatório 4
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardImg(src="/assets/mining4.jpg", top=True, style={"height": "180px", "objectFit": "cover"}),
                            dbc.CardBody(
                                [
                                    html.H4("Produção - Indicadores", className="card-title"),
                                    html.P("Produção - Indicadores", className="card-text"),
                                    dcc.Link("Visualizar", href="/relatorio4", className="btn btn-primary")
                                ]
                            )
                        ],
                        style={"width": "18rem", "margin": "auto"}
                    ),
                    width=12, md=3
                ),
            ],
            className="my-4 justify-content-center"
        ),
        dbc.Row(
            dbc.Col(
                html.Footer("© 2025 Mineração XYZ", className="text-center text-muted my-4"),
                width=12
            )
        )
    ],
    fluid=True
)

# Layout principal com dcc.Location para navegação e um Spinner para feedback visual
app.layout = html.Div(
    [
        dcc.Location(id="url", refresh=False),
        navbar,
        dbc.Spinner(html.Div(id="page-content"), size="lg", color="primary", fullscreen=True)
    ]
)

# Callback para trocar o conteúdo da página com base na URL
@app.callback(Output("page-content", "children"), [Input("url", "pathname")])
def display_page(pathname):
    if pathname == "/relatorio1":
        return rel1.layout
    elif pathname == "/relatorio2":
        return rel2.layout
    elif pathname == "/relatorio3":
        return rel3.layout
    elif pathname == "/relatorio4":
        return rel4.layout
    else:
        return home_layout

if __name__ == "__main__":
    app.run_server(debug=True)
