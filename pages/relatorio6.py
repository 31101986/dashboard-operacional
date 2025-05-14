from datetime import datetime, timedelta
import logging
from typing import Tuple, List, Dict, Optional
import io

import pandas as pd
from dash import dcc, html, Input, Output, callback
import dash_bootstrap_components as dbc

from db import query_to_df
from app import cache
from config import PROJECTS_CONFIG, PROJECT_LABELS

# ============================================================
# CONFIGURAÇÕES
# ============================================================

# Configuração do log
logging.basicConfig(
    level=logging.INFO,
    filename="dashboard.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Período inicial para consulta: últimos 2 dias (ajustado dinamicamente)
DAY_END: datetime = datetime.now()
DAY_START: datetime = DAY_END - timedelta(days=2)

# Mapeamento de imagens por modelo
MODEL_IMAGES: Dict[str, str] = {
    "VOLVO FMX 500 8X4": "/assets/VOLVO FMX 500 8X4.jpg",
    "VOLVO FM 500 8X4": "/assets/VOLVO FMX 500 8X4.jpg",
    "Volvo FMX500 - CB": "/assets/VOLVO FMX 500 8X4.jpg",
    "MERCEDES BENZ AROCS 4851/45 8X4": "/assets/MERCEDES_BENZ_AROCS 4851_45_8X4.jpg",
    "MERCEDES BENZ ACTROS 4844K/45 8X4": "/assets/MERCEDES_BENZ_AROCS 4851_45_8X4.jpg",
    "MERCEDES BENZ AXOR 3344 6X4 (PIPA)": "/assets/MERCEDES BENZ AXOR 3344 6X4 (PIPA).jpg",
    "ESCAVADEIRA HIDRÁULICA CAT 374DL": "/assets/ESCAVADEIRA_HIDRAULICA_CAT_374DL.jpg",
    "ESCAVADEIRA HIDRÁULICA VOLVO EC750DL": "/assets/ESCAVADEIRA_HIDRAULICA_VOLVO_EC750DL.jpg",
    "ESCAVADEIRA HIDRÁULICA VOLVO EC700": "/assets/ESCAVADEIRA_HIDRAULICA_VOLVO_EC750DL.jpg",
    "PERFURATRIZ HIDRAULICA SANDVIK DP1500I": "/assets/PERFURATRIZ HIDRAULICA SANDVIK DP1500I.jpg",
    "PERFURATRIZ HIDRAULICA SANDVIK DX800": "/assets/PERFURATRIZ HIDRAULICA SANDVIK DP1500I.jpg",
    "TRATOR DE ESTEIRAS CAT D7": "/assets/TRATOR DE ESTEIRAS CAT D7.jpg",
    "TRATOR DE ESTEIRAS CAT D6T": "/assets/TRATOR DE ESTEIRAS CAT D7.jpg",
    "TRATOR DE ESTEIRAS CAT D8": "/assets/TRATOR DE ESTEIRAS CAT D7.jpg",
    "TRATOR DE ESTEIRAS KOMATSU D155": "/assets/TRATOR DE ESTEIRAS KOMATSU D155.jpg",
    "ESCAVADEIRA HIDRÁULICA CAT 320": "/assets/ESCAVADEIRAHIDRAULICACAT320.jpg",
    "Cat 320D - EH": "/assets/ESCAVADEIRAHIDRAULICACAT320.jpg",
    "ESCAVADEIRA HIDRÁULICA CAT 320NGX": "/assets/ESCAVADEIRAHIDRAULICACAT320.jpg",
    "ESCAVADEIRA HIDRÁULICA CAT 320 (ROMPEDOR)": "/assets/ESCAVADEIRAHIDRAULICACAT320(ROMPEDOR).jpg",
    "ESCAVADEIRA HIDRÁULICA CAT 352": "/assets/ESCAVADEIRAHIDRAULICACAT320.jpg",
    "ESCAVADEIRA HIDRÁULICA CAT 345GC": "/assets/ESCAVADEIRAHIDRAULICACAT320.jpg",
    "ESCAVADEIRA HIDRAULICA CAT 336NGX": "/assets/ESCAVADEIRAHIDRAULICACAT320.jpg",
    "ESCAVADEIRA HIDRÁULICA CAT 336NGX": "/assets/ESCAVADEIRAHIDRAULICACAT320.jpg",
    "Cat 336D - EH": "/assets/ESCAVADEIRAHIDRAULICACAT320.jpg",
    "ESCAVADEIRA HIDRAULICA SANY SY750H": "/assets/ESCAVADEIRA HIDRAULICA SANY SY750H.jpg",
    "ESCAVADEIRA HIDRÁULICA VOLVO EC480DL": "/assets/ESCAVADEIRAHIDRAULICAVOLVOEC480DL.jpg",
    "MOTONIVELADORA CAT 140K": "/assets/MOTONIVELADORA CAT 140K.jpg",
    "PÁ CARREGADEIRA CAT 966L": "/assets/PA CARREGADEIRA CAT 966L.jpg",
    "Cat 938 K - PC": "/assets/PA CARREGADEIRA CAT 966L.jpg",
    "Cat 950 L - PC": "/assets/PA CARREGADEIRA CAT 966L.jpg",
    "RETRO ESCAVADEIRA CAT 416F2": "/assets/RETRO ESCAVADEIRA CAT 416F2.jpg",
    "Cat CS54B - RC": "/assets/CatCS54BRC.jpg",
    "ROLO COMPACTADOR CAT CP54B": "/assets/CatCS54BRC.jpg",
    "Liebherr R954C - EH": "/assets/LiebherrR954CEH.jpg",
    "CAMINHÃO ARTICULADO VOLVO A30G - 6X6": "/assets/CAMINHAOARTICULADOVOLVOA30G6X6.jpg",
    "CAMINHÃO ARTICULADO VOLVO A30F - 6X6": "/assets/CAMINHAOARTICULADOVOLVOA30G6X6.jpg",
    "TRATOR AGRÍCOLA NEW HOLLAND T7 205": "/assets/TRATORAGRICOLANEWHOLLANDT7205.jpg",
}

# Tempo máximo para escala de cores (4 horas em segundos)
MAX_DURATION_SECONDS: int = 4 * 60 * 60

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def get_color_for_duration(duration: timedelta) -> Tuple[str, int]:
    """Retorna uma cor interpolada (amarelo a vermelho) com base na duração do estado."""
    seconds = duration.total_seconds()
    fraction = min(seconds / MAX_DURATION_SECONDS, 1)
    green = int(255 * (1 - fraction))
    return f"rgb(255, {green}, 0)", green

@cache.memoize(timeout=300)
def get_all_records_cached(start_date: str, end_date: str, projeto: str) -> pd.DataFrame:
    """
    Consulta a tabela fato_hora para o período e projeto especificados com cache.

    Args:
        start_date (str): Data inicial no formato 'dd/mm/yyyy HH:MM:SS'.
        end_date (str): Data final no formato 'dd/mm/yyyy HH:MM:SS'.
        projeto (str): ID do projeto (ex.: 'projeto1').

    Returns:
        pd.DataFrame: Dados de equipamentos ou DataFrame vazio em caso de erro.
    """
    logger.debug(f"[DEBUG] Consultando dados de {start_date} a {end_date} para projeto {projeto}")
    if projeto not in PROJECTS_CONFIG:
        logger.error(f"[DEBUG] Projeto {projeto} não encontrado em PROJECTS_CONFIG")
        return pd.DataFrame()
    
    logger.debug(f"[DEBUG] Configuração para {projeto}: server={PROJECTS_CONFIG[projeto]['server']}, database={PROJECTS_CONFIG[projeto]['database']}")
    query = (
        f"EXEC {PROJECTS_CONFIG[projeto]['database']}..usp_fato_hora "
        f"'{start_date}', '{end_date}'"
    )
    logger.debug(f"[DEBUG] Query executada: {query}")
    try:
        df = query_to_df(query, projeto=projeto)
        if df is None or df.empty:
            logger.debug("[DEBUG] Consulta retornou DataFrame vazio")
            return pd.DataFrame()
        if "dt_registro" in df.columns:
            df["dt_registro"] = pd.to_datetime(df["dt_registro"], errors="coerce")
        logger.debug(f"[DEBUG] Dados retornados: {len(df)} linhas")
        return df
    except Exception as e:
        logger.error(f"[DEBUG] Erro na consulta para projeto {projeto}: {str(e)}")
        return pd.DataFrame()

def get_all_records(projeto: str) -> pd.DataFrame:
    """Wrapper para obter registros com cache, usando datas atuais."""
    start_date = DAY_START.strftime("%d/%m/%Y %H:%M:%S")
    end_date = DAY_END.strftime("%d/%m/%Y %H:%M:%S")
    return get_all_records_cached(start_date, end_date, projeto)

def get_current_state_records(projeto: str) -> pd.DataFrame:
    """Retorna o registro mais recente por equipamento, com dt_registro_inicio, buscando nos últimos 2 dias ou 3 dias se vazio."""
    # Primeiro tenta os últimos 2 dias
    df = get_all_records(projeto)
    if df.empty:
        logger.debug(f"[DEBUG] Nenhum dado nos últimos 2 dias para projeto {projeto}, tentando últimos 3 dias")
        global DAY_START
        DAY_START = DAY_END - timedelta(days=3)
        df = get_all_records(projeto)
        if df.empty:
            logger.debug(f"[DEBUG] Nenhum dado nos últimos 3 dias para projeto {projeto}")
            return pd.DataFrame()

    df = df.dropna(subset=["nome_equipamento", "id_lancamento", "dt_registro"])
    dt_min = df.groupby(["nome_equipamento", "id_lancamento"], as_index=False)["dt_registro"].min()
    df_sorted = df.sort_values("dt_registro")
    latest = df_sorted.groupby("nome_equipamento", as_index=False).last()
    current_state = pd.merge(latest, dt_min, on=["nome_equipamento", "id_lancamento"], suffixes=("", "_inicio"))
    logger.debug(f"[DEBUG] Registros mais recentes para projeto {projeto}: {len(current_state)} linhas")
    return current_state

def create_tv_layout(df: pd.DataFrame, filter_values: Optional[List[str]] = None) -> html.Div:
    """
    Cria o layout de TV com cartões de equipamentos agrupados por estado e tipo.
    """
    if df.empty:
        logger.debug("[DEBUG] DataFrame vazio em create_tv_layout")
        return html.Div(
            "Sem dados para exibir. Verifique a disponibilidade de dados no banco ou a conexão.",
            className="text-center my-4"
        )

    # Remover registros do equipamento TRIMAK
    df = df[df["nome_equipamento"].str.upper() != "TRIMAK"]
    logger.debug(f"[DEBUG] Após remover TRIMAK: {len(df)} linhas")

    # Aplicar filtro de nome_tipo_estado, se fornecido
    if filter_values:
        filter_values_upper = [v.upper().strip() for v in filter_values]
        df = df[df["nome_tipo_estado"].str.upper().str.strip().isin(filter_values_upper)]
        logger.debug(f"[DEBUG] Após filtro por nome_tipo_estado: {len(df)} linhas")

    if df.empty:
        logger.debug("[DEBUG] Nenhum equipamento corresponde ao filtro")
        return html.Div(
            "Nenhum equipamento corresponde ao filtro selecionado.",
            className="text-center my-4"
        )

    # Ordenar dados
    df = df.sort_values(["nome_estado", "nome_tipo_estado", "nome_equipamento"])

    # Normalizar chaves do mapeamento de imagens
    normalized_model_images = {key.strip().upper(): url for key, url in MODEL_IMAGES.items()}

    # Cabeçalho
    header = dbc.Row(
        [
            dbc.Col(
                html.H5("Estado", className="text-white m-0", style={"padding": "10px"}),
                width=3,
                style={"background": "linear-gradient(90deg, #343a40, #495057)"}
            ),
            dbc.Col(
                html.H5("Equipamento", className="text-white m-0", style={"padding": "10px"}),
                width=9,
                style={"background": "linear-gradient(90deg, #343a40, #495057)"}
            )
        ],
        className="mb-2"
    )

    # Agrupar por estado e tipo
    group_cols = ["nome_estado", "nome_tipo_estado"]
    grouped = df.groupby(group_cols)

    rows = []
    now = datetime.now()
    for (estado, tipo), group_data in grouped:
        count_equip = len(group_data)
        left_col = [
            html.H6(estado, className="mb-0 text-white", style={"fontSize": "0.95rem"}),
            html.H6(tipo, className="mb-0 text-white", style={"fontSize": "0.9rem"}) if pd.notnull(tipo) else None,
            html.P(f"{count_equip} equipamento(s)", className="text-white", style={"fontSize": "0.85rem"})
        ]
        left_col = [c for c in left_col if c is not None]

        equip_cards = []
        for _, row in group_data.iterrows():
            equip_name = row["nome_equipamento"]
            model_name = row.get("nome_modelo", "")

            dt_val = row.get("dt_registro_inicio")
            if not isinstance(dt_val, pd.Timestamp):
                dt_val = pd.to_datetime(dt_val, errors="coerce")
            if pd.notnull(dt_val):
                duration = now - dt_val
                time_str = dt_val.strftime("%d/%m/%Y %H:%M:%S")
                band_color, green_val = get_color_for_duration(duration)
                text_color = "black" if green_val > 200 else "white"
            else:
                time_str = "N/A"
                band_color = "#CCCCCC"
                text_color = "white"

            img_url = normalized_model_images.get(model_name.strip().upper(), None) if pd.notnull(model_name) else None
            image_component = (
                html.Img(src=img_url, style={
                    "width": "120px", "height": "120px", "objectFit": "cover", "borderRadius": "4px"
                })
                if img_url else
                html.Div(style={
                    "width": "120px", "height": "120px", "backgroundColor": "#EEEEEE", "borderRadius": "4px"
                })
            )

            info_band = html.Div(
                [
                    html.Div(equip_name, style={"fontSize": "0.9rem", "fontWeight": "bold", "color": text_color}),
                    html.Div(time_str, style={"fontSize": "0.75rem", "color": text_color})
                ],
                style={
                    "backgroundColor": band_color,
                    "width": "100%",
                    "padding": "5px",
                    "textAlign": "center",
                    "borderRadius": "0 0 4px 4px"
                }
            )

            card = dbc.Card(
                dbc.CardBody(
                    html.Div(
                        [image_component, info_band],
                        style={"display": "flex", "flexDirection": "column", "alignItems": "center"}
                    )
                ),
                style={
                    "width": "180px",
                    "margin": "5px",
                    "padding": "0px",
                    "boxShadow": "0px 2px 4px rgba(0,0,0,0.1)",
                    "borderRadius": "8px",
                    "overflow": "hidden",
                    "backgroundColor": "#FFFFFF"
                },
                className="mb-2"  # Garantido como string
            )
            equip_cards.append(card)

        right_col = html.Div(equip_cards, style={"display": "flex", "flexWrap": "wrap", "gap": "10px"})

        row_layout = dbc.Row(
            [
                dbc.Col(
                    html.Div(left_col),
                    width=3,
                    style={"backgroundColor": "#343a40", "padding": "10px", "color": "white"}
                ),
                dbc.Col(
                    right_col,
                    width=9,
                    style={"backgroundColor": "#FFFFFF", "padding": "10px"}
                )
            ],
            className="mb-2"  # Garantido como string
        )
        rows.append(row_layout)

    logger.debug(f"[DEBUG] Layout criado com {len(rows)} grupos")
    return html.Div([header] + rows, className="mt-4")  # Garantido como string

# ============================================================
# LAYOUT PRINCIPAL
# ============================================================

NAVBAR = dbc.Navbar(
    dbc.Container([
        dbc.NavbarBrand([
            html.I(className="fas fa-cogs mr-2"),
            "Equipamentos por Estado"
        ], href="/relatorio6", className="ms-2 d-flex align-items-center", style={"fontSize": "1.1rem"}),
        dcc.Link([
            html.I(className="fas fa-home mr-1"),
            "Voltar"
        ], href="/", className="btn btn-sm", style={
            "borderRadius": "10px",
            "background": "linear-gradient(45deg, #007bff, #00aaff)",
            "color": "#fff",
            "padding": "6px 12px",
            "transition": "all 0.3s"
        }),
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
    ], fluid=True),
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

layout = dbc.Container([
    NAVBAR,
    dbc.Row(
        dbc.Col(
            html.H3(
                [html.I(className="fas fa-cogs mr-2"), "Equipamentos por Estado"],
                className="text-center mt-4 mb-4"
            ),
            width=12
        ),
        className="mb-3"
    ),
    dbc.Card([
        dbc.CardHeader(
            html.H5("Controle de Atualização", className="mb-0 text-white", style={
                "fontSize": "1.1rem",
                "fontWeight": "500",
                "fontFamily": "Arial, sans-serif"
            }),
            style={"background": "linear-gradient(90deg, #343a40, #495057)"}
        ),
        dbc.CardBody(
            dbc.Row([
                dbc.Col(
                    dbc.Button(
                        [html.I(className="fas fa-sync-alt mr-1"), "Atualizar"],
                        id="update-button",
                        className="w-100",
                        style={
                            "fontSize": "0.9rem",
                            "block": "8px",
                            "background": "linear-gradient(45deg, #28a745, #34c759)",
                            "color": "#fff",
                            "transition": "all 0.3s",
                            "padding": "6px 12px"
                        }
                    ),
                    width=4,
                    xs=12,
                    className="mb-2 mb-md-0"
                ),
                dbc.Col(
                    html.Div(
                        id="last-update",
                        style={
                            "fontFamily": "Arial, sans-serif",
                            "fontSize": "0.85rem",
                            "textAlign": "center",
                            "paddingTop": "6px",
                            "color": "#343a40"
                        }
                    ),
                    width=8,
                    xs=12
                )
            ]),
            style={"padding": "0.8rem"}
        )
    ], className="shadow-md mb-4 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none", "zIndex": "10"}),
    dbc.Card([
        dbc.CardHeader(
            html.H5("Filtrar Tipos de Estado (Opcional)", className="mb-0 text-white", style={
                "fontSize": "1.1rem",
                "fontWeight": "500",
                "fontFamily": "Arial, sans-serif"
            }),
            style={"background": "linear-gradient(90deg, #343a40, #495057)"}
        ),
        dbc.CardBody(
            dcc.Dropdown(
                id="filter-dropdown",
                multi=True,
                placeholder="Selecione os tipos de estado (deixe vazio para todos)...",
                clearable=True,
                style={
                    "fontFamily": "Arial, sans-serif",
                    "fontSize": "0.9rem",
                    "borderRadius": "8px",
                    "backgroundColor": "#f8f9fa",
                    "padding": "6px"
                }
            ),
            style={"padding": "0.8rem"}
        )
    ], className="shadow-md mb-4 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none", "zIndex": "10"}),
    dcc.Store(id="latest-data-store"),
    dcc.Interval(id="interval-component", interval=300000, n_intervals=0),  # 5 minutos
    dcc.Loading(
        id="loading-tv-layout",
        type="default",
        children=dbc.Card([
            dbc.CardHeader(
                html.H5("Estado Atual dos Equipamentos", className="mb-0 text-white", style={
                    "fontSize": "1.1rem",
                    "fontWeight": "500",
                    "fontFamily": "Arial, sans-serif"
                }),
                style={"background": "linear-gradient(90deg, #343a40, #495057)"}
            ),
            dbc.CardBody(
                html.Div(id="tv-layout"),
                style={"padding": "0.8rem"}
            )
        ], className="shadow-md mb-4 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none", "zIndex": "5"})
    ),
], fluid=True, style={"minHeight": "100vh"})

# ============================================================
# CALLBACKS
# ============================================================

@callback(
    Output("latest-data-store", "data"),
    Output("last-update", "children"),
    Input("update-button", "n_clicks"),
    Input("interval-component", "n_intervals"),
    Input("projeto-store", "data"),
    prevent_initial_call=False
)
def update_data(n_clicks: Optional[int], n_intervals: int, projeto: Optional[str]) -> Tuple[Optional[str], str]:
    """Atualiza os dados com os registros mais recentes por equipamento a cada 5 minutos ou clique."""
    logger.debug(f"[DEBUG] update_data disparado: n_clicks={n_clicks}, n_intervals={n_intervals}, projeto={projeto}")
    
    if not projeto or projeto not in PROJECTS_CONFIG:
        logger.debug("[DEBUG] Nenhum projeto selecionado ou projeto inválido")
        return None, "Selecione uma obra para visualizar os dados."
    
    # Recalcular datas dinamicamente para invalidar o cache a cada intervalo
    global DAY_END, DAY_START
    DAY_END = datetime.now()
    DAY_START = DAY_END - timedelta(days=2)
    
    # Forçar atualização do cache com base em n_intervals
    cache_key = f"{DAY_START.strftime('%d/%m/%Y %H:%M:%S')}_{DAY_END.strftime('%d/%m/%Y %H:%M:%S')}_{n_intervals}_{projeto}"
    try:
        latest = get_current_state_records(projeto)
    except Exception as e:
        logger.error(f"[DEBUG] Erro ao obter registros mais recentes para projeto {projeto}: {str(e)}")
        return None, f"Erro ao carregar dados para {PROJECT_LABELS.get(projeto, projeto)}: {str(e)}"

    if latest.empty:
        logger.debug(f"[DEBUG] Nenhum dado retornado por get_current_state_records para projeto {projeto}")
        return None, f"Sem dados para {PROJECT_LABELS.get(projeto, projeto)}. Verifique a disponibilidade de dados no banco."

    latest = latest[latest["nome_equipamento"].str.upper() != "TRIMAK"]
    logger.debug(f"[DEBUG] Após remover TRIMAK em update_data: {len(latest)} linhas")

    try:
        json_data = latest.to_json(orient="records", date_format="iso")
    except Exception as e:
        logger.error(f"[DEBUG] Erro ao serializar dados para JSON: {str(e)}")
        return None, f"Erro ao processar dados para {PROJECT_LABELS.get(projeto, projeto)}: {str(e)}"

    last_update_text = f"Última atualização: {DAY_END.strftime('%d/%m/%Y %H:%M:%S')} ({PROJECT_LABELS.get(projeto, projeto)})"
    logger.debug(f"[DEBUG] Dados atualizados: {len(latest)} linhas, cache_key={cache_key}")
    return json_data, last_update_text

@callback(
    Output("filter-dropdown", "options"),
    Output("filter-dropdown", "value"),
    Input("latest-data-store", "data")
)
def update_filter_options(json_data: Optional[str]) -> Tuple[List[Dict[str, str]], List[str]]:
    """Atualiza as opções do Dropdown de filtro e define valores padrão."""
    logger.debug("[DEBUG] update_filter_options disparado")
    if not json_data:
        logger.debug("[DEBUG] Nenhum dado em update_filter_options")
        return [], []

    try:
        # Usar StringIO para ler JSON literal
        df = pd.read_json(io.StringIO(json_data), orient="records")
    except Exception as e:
        logger.error(f"[DEBUG] Erro ao ler JSON em update_filter_options: {str(e)}")
        return [], []

    if df.empty or "nome_tipo_estado" not in df.columns:
        logger.debug("[DEBUG] DataFrame vazio ou sem nome_tipo_estado")
        return [], []

    df["nome_tipo_estado"] = df["nome_tipo_estado"].str.upper()
    tipos = sorted(df["nome_tipo_estado"].dropna().unique())
    options = [{"label": t, "value": t} for t in tipos]

    default_preselection = [
        "MANUTENÇÃO CORRETIVA",
        "MANUTENÇÃO PREVENTIVA",
        "MANUTENÇÃO OPERACIONAL",
        "FORA DE FROTA"
    ]
    default_value = [t for t in default_preselection if t in tipos]
    logger.debug(f"[DEBUG] Valores predefinidos aplicados: {default_value}")

    return options, default_value

@callback(
    Output("tv-layout", "children"),
    Input("latest-data-store", "data"),
    Input("filter-dropdown", "value")
)
def render_tv_layout(json_data: Optional[str], filter_values: Optional[List[str]]) -> html.Div:
    """Renderiza o layout de TV com base nos dados e filtros."""
    logger.debug(f"[DEBUG] render_tv_layout disparado, filter_values={filter_values}")
    if not json_data:
        logger.debug("[DEBUG] Nenhum dado em render_tv_layout")
        return html.Div(
            "Selecione uma obra para visualizar os dados.",
            className="text-center my-4"
        )

    try:
        # Usar StringIO para ler JSON literal
        df = pd.read_json(io.StringIO(json_data), orient="records")
    except Exception as e:
        logger.error(f"[DEBUG] Erro ao ler JSON em render_tv_layout: {str(e)}")
        return html.Div(
            f"Erro ao processar dados: {str(e)}",
            className="text-center my-4"
        )

    logger.debug(f"[DEBUG] Dados recebidos em render_tv_layout: {len(df)} linhas")
    return create_tv_layout(df, filter_values)
