import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output  # Certifique-se de importar Input e Output
import pages.relatorio1 as rel1
import pages.relatorio2 as rel2
import pages.relatorio3 as rel3   # Importa o Relatório 3

# External stylesheets: Inclui o tema LUX, Font Awesome e animate.css
external_stylesheets = [
    dbc.themes.LUX,
    "https://use.fontawesome.com/releases/v5.8.1/css/all.css",
    "https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css"
]

app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=external_stylesheets
)
server = app.server  # Para deploy, por exemplo, no Heroku

# Navbar
navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dcc.Link("Portal", href="/", className="nav-link")),
        dbc.NavItem(dcc.Link("Relatório 1", href="/relatorio1", className="nav-link")),
        dbc.NavItem(dcc.Link("Relatório 2", href="/relatorio2", className="nav-link")),
        dbc.NavItem(dcc.Link("Relatório 3", href="/relatorio3", className="nav-link")),  # Link para Relatório 3
    ],
    brand="Mineração XYZ",
    brand_href="/",
    color="dark",
    dark=True,
    sticky="top",
)

# Layout da página inicial (Portal)
home_layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.H1("Portal de Relatórios para Mineração", className="text-center my-4"),
                width=12,
            )
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardImg(
                                src="/assets/mining.jpg",
                                top=True,
                                style={"height": "180px", "objectFit": "cover"},
                            ),
                            dbc.CardBody(
                                [
                                    html.H4("Relatório 1", className="card-title"),
                                    html.P("Análise de Hora", className="card-text"),
                                    dcc.Link("Visualizar", href="/relatorio1", className="btn btn-primary"),
                                ]
                            ),
                        ],
                        style={"width": "18rem", "margin": "auto"},
                    ),
                    width=12,
                    md=4,
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardImg(
                                src="/assets/mining2.jpg",
                                top=True,
                                style={"height": "180px", "objectFit": "cover"},
                            ),
                            dbc.CardBody(
                                [
                                    html.H4("Relatório 2", className="card-title"),
                                    html.P("Análise de Produção", className="card-text"),
                                    dcc.Link("Visualizar", href="/relatorio2", className="btn btn-primary"),
                                ]
                            ),
                        ],
                        style={"width": "18rem", "margin": "auto"},
                    ),
                    width=12,
                    md=4,
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardImg(
                                src="/assets/mining3.jpg",  # Certifique-se de ter esta imagem em assets
                                top=True,
                                style={"height": "180px", "objectFit": "cover"},
                            ),
                            dbc.CardBody(
                                [
                                    html.H4("Relatório 3", className="card-title"),
                                    html.P("Novo Relatório", className="card-text"),
                                    dcc.Link("Visualizar", href="/relatorio3", className="btn btn-primary"),
                                ]
                            ),
                        ],
                        style={"width": "18rem", "margin": "auto"},
                    ),
                    width=12,
                    md=4,
                ),
            ],
            className="my-4 justify-content-center",
        ),
        dbc.Row(
            [
                dbc.Col(
                    html.Footer("© 2025 Mineração XYZ", className="text-center text-muted my-4"),
                    width=12,
                )
            ]
        ),
    ],
    fluid=True,
)

# Layout principal com Location (para rotas) + Navbar
app.layout = html.Div(
    [
        dcc.Location(id="url", refresh=False),
        navbar,
        dbc.Spinner(html.Div(id="page-content"), size="lg", color="primary", fullscreen=True),
    ]
)

# Callback para trocar o conteúdo da página conforme a URL
@app.callback(Output("page-content", "children"), [Input("url", "pathname")])
def display_page(pathname):
    if pathname == "/relatorio1":
        return rel1.layout  # layout definido em pages/relatorio1.py
    elif pathname == "/relatorio2":
        return rel2.layout  # layout definido em pages/relatorio2.py
    elif pathname == "/relatorio3":
        return rel3.layout  # layout definido em pages/relatorio3.py
    else:
        return home_layout  # Página inicial/portal

if __name__ == "__main__":
    app.run_server(debug=True)
