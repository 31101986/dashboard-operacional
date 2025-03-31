import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State  # type: ignore
import logging

# Import das páginas (relatórios)
import pages.relatorio1 as rel1
#import pages.relatorio2 as rel2
#import pages.relatorio3 as rel3
import pages.relatorio4 as rel4
import pages.relatorio5 as rel5


def setup_logger():
    """
    Configura e retorna um logger para a aplicação.
    Garante que não sejam adicionados múltiplos handlers em execuções repetidas.
    """
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        logger_format = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
        console_handler.setFormatter(logger_format)
        logger.addHandler(console_handler)
    return logger


logger = setup_logger()
logger.info("Iniciando a aplicação Dash...")

# ----------------------------------------------------------------------------
# Configurações de estilo externas – tema LUX, Font Awesome e animate.css
# ----------------------------------------------------------------------------
external_stylesheets = [
    dbc.themes.LUX,
    "https://use.fontawesome.com/releases/v5.8.1/css/all.css",
    "https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css",
]

# ----------------------------------------------------------------------------
# Criação do app Dash
# ----------------------------------------------------------------------------
app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,  # Necessário caso usemos layouts/páginas carregadas dinamicamente
    external_stylesheets=external_stylesheets
)
app.title = "Portal de Relatórios - Mineração"
server = app.server  # Exposição do servidor para implantação (gunicorn, etc.)

# ----------------------------------------------------------------------------
# Navbar responsiva com toggler para dispositivos móveis
# ----------------------------------------------------------------------------
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

# ----------------------------------------------------------------------------
# Função auxiliar para criação de cards
# ----------------------------------------------------------------------------
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

# ----------------------------------------------------------------------------
# Layout da página inicial (Portal) com cards
# ----------------------------------------------------------------------------
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
                    create_card("/assets/mining.jpg", "Ciclo", "Análise de Hora", "Visualizar", "/relatorio1"),
                    width=12, md=3
                ),
                #dbc.Col(
                    #create_card("/assets/mining2.jpg", "Informativo de Produção", "Análise de Produção", "Visualizar", "/relatorio2"),
                    #width=12, md=3
                #),
                #dbc.Col(
                   # create_card("/assets/mining3.jpg", "Avanço Financeiro", "Avanço Financeiro", "Visualizar", "/relatorio3"),
                    #width=12, md=3
              #  ),
                dbc.Col(
                    create_card("/assets/mining4.jpg", "Produção - Indicadores", "Produção - Indicadores", "Visualizar", "/relatorio4"),
                    width=12, md=3
                ),
            ],
            className="my-4 justify-content-center"
        ),
        # Linha com o card do Relatório 5
        dbc.Row(
            dbc.Col(
                create_card("/assets/mining5.jpg", "Timeline Apontamentos", "Equipamentos de Produção", "Visualizar", "/relatorio5"),
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

# ----------------------------------------------------------------------------
# Layout principal com dcc.Location e Spinner (feedback de carregamento)
# ----------------------------------------------------------------------------
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

# ----------------------------------------------------------------------------
# Mapeamento de páginas para facilitar a manutenção do callback de roteamento
# ----------------------------------------------------------------------------
pages = {
    "/relatorio1": rel1.layout,
    #"/relatorio2": rel2.layout,
    #"/relatorio3": rel3.layout,
    "/relatorio4": rel4.layout,
    "/relatorio5": rel5.layout,
}

@app.callback(Output("page-content", "children"), [Input("url", "pathname")])
def display_page(pathname):
    """
    Callback para renderizar o layout conforme o path da URL.
    """
    logger.info(f"Navegando para {pathname}")
    # Retorna o layout correspondente ou o layout principal (home_layout)
    return pages.get(pathname, home_layout)

# ----------------------------------------------------------------------------
# Execução do servidor
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    # Para performance em produção, geralmente desativamos debug (debug=False).
    # Aqui mantemos debug=True para desenvolvimento, conforme o original.
    logger.info("Executando o servidor no modo debug...")
    app.run_server(debug=True, host="0.0.0.0", port=8050)
