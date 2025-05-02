from __future__ import annotations

"""
relatorio6.py – Equipamentos por Estado

Exibe o estado atual dos equipamentos em um layout de TV, com cartões agrupados por estado e tipo,
incluindo imagens por modelo e escala de cores para duração. Otimizado para performance com cache robusto,
operações vetorizadas e logs de depuração. Usa TIMEZONE de config.py (ZoneInfo) para Horário de Brasília.

Dependências:
  - Banco de dados via `db.query_to_df`
  - Cache via `app.cache`
  - TIMEZONE de config.py
"""

# ============================================================
# IMPORTAÇÕES
# ============================================================
from datetime import datetime, timedelta
import logging
import time
from typing import Tuple, List, Dict, Any, Union, Optional

import pandas as pd
from dash import dcc, html, Input, Output, callback
import dash_bootstrap_components as dbc
import plotly.express as px

from db import query_to_df
from app import cache
from config import TIMEZONE  # Importar TIMEZONE de config.py (ZoneInfo)

# ============================================================
# CONFIGURAÇÕES
# ============================================================

# Configuração do log
logging.basicConfig(level=logging.INFO, filename="dashboard.log", filemode="a", format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Período para consulta: últimos 7 dias, usando TIMEZONE (Horário de Brasília)
DAY_END: datetime = datetime.now(tz=TIMEZONE)
DAY_START: datetime = DAY_END - timedelta(days=7)

# Mapeamento de imagens por modelo
MODEL_IMAGES: Dict[str, str] = {
    "VOLVO FMX 500 8X4": "/assets/VOLVO FMX 500 8X4.jpg",
    "MERCEDES BENZ AROCS 4851/45 8X4": "/assets/MERCEDES_BENZ_AROCS 4851_45_8X4.jpg",
    "MERCEDES BENZ AXOR 3344 6X4 (PIPA)": "/assets/MERCEDES BENZ AXOR 3344 6X4 (PIPA).jpg",
    "ESCAVADEIRA HIDRÁULICA CAT 374DL": "/assets/ESCAVADEIRA_HIDRAULICA_CAT_374DL.jpg",
    "ESCAVADEIRA HIDRÁULICA VOLVO EC750DL": "/assets/ESCAVADEIRA_HIDRAULICA_VOLVO_EC750DL.jpg",
    "PERFURATRIZ HIDRAULICA SANDVIK DP1500I": "/assets/PERFURATRIZ HIDRAULICA SANDVIK DP1500I.jpg",
    "PERFURATRIZ HIDRAULICA SANDVIK DX800": "/assets/PERFURATRIZ HIDRAULICA SANDVIK DP1500I.jpg",
    "TRATOR DE ESTEIRAS CAT D7": "/assets/TRATOR DE ESTEIRAS CAT D7.jpg",
    "TRATOR DE ESTEIRAS CAT D6T": "/assets/TRATOR DE ESTEIRAS CAT D7.jpg",
    "TRATOR DE ESTEIRAS CAT D8": "/assets/TRATOR DE ESTEIRAS CAT D7.jpg",
    "TRATOR DE ESTEIRAS KOMATSU D155": "/assets/TRATOR DE ESTEIRAS KOMATSU D155.jpg",
    "ESCAVADEIRA HIDRÁULICA CAT 320": "/assets/ESCAVADEIRA_HIDRAULICA CAT 320.jpg",
    "ESCAVADEIRA HIDRÁULICA CAT 320 (ROMPEDOR)": "/assets/ESCAVADEIRA_HIDRAULICA CAT 320 (ROMPEDOR).jpg",
    "ESCAVADEIRA HIDRÁULICA CAT 352": "/assets/ESCAVADEIRA_HIDRAULICA CAT 320.jpg",
    "ESCAVADEIRA HIDRAULICA CAT 336NGX": "/assets/ESCAVADEIRA_HIDRAULICA CAT 320.jpg",
    "ESCAVADEIRA HIDRAULICA SANY SY750H": "/assets/ESCAVADEIRA HIDRAULICA SANY SY750H.jpg",
    "ESCAVADEIRA HIDRÁULICA VOLVO EC480DL": "/assets/ESCAVADEIRA_HIDRAULICA_VOLVO_EC480DL.jpg",
    "MOTONIVELADORA CAT 140K": "/assets/MOTONIVELADORA CAT 140K.jpg",
    "PÁ CARREGADEIRA CAT 966L": "/assets/PA CARREGADEIRA CAT 966L.jpg",
    "RETRO ESCAVADEIRA CAT 416F2": "/assets/RETRO ESCAVADEIRA CAT 416F2.jpg",
}

# Tempo máximo para escala de cores (4 horas em segundos)
MAX_DURATION_SECONDS: int = 4 * 60 * 60

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def profile_time(func):
    """Decorador para medir o tempo de execução da função e registrar no log."""
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = func(*args, **kwargs)
        t1 = time.perf_counter()
        logger.info(f"[Profile] {func.__name__} executada em {t1 - t0:.4f} segundos")
        return result
    return wrapper

def get_color_for_duration(duration: timedelta) -> Tuple[str, int]:
    """Retorna uma cor interpolada (amarelo a vermelho) com base na duração do estado."""
    seconds = duration.total_seconds()
    fraction = min(seconds / MAX_DURATION_SECONDS, 1)
    green = int(255 * (1 - fraction))
    return f"rgb(255, {green}, 0)", green

@cache.memoize(timeout=60)
@profile_time
def fetch_equipment_data(start_date: datetime, end_date: datetime, refresh: bool = False) -> pd.DataFrame:
    """
    Consulta todos os equipamentos e seus estados no banco, com cache.

    Args:
        start_date (datetime): Data inicial (Horário de Brasília).
        end_date (datetime): Data final (Horário de Brasília).
        refresh (bool): Força atualização do cache.

    Returns:
        pd.DataFrame: Dados de equipamentos ou DataFrame vazio em caso de erro.
    """
    logger.debug(f"[DEBUG] Consultando dados de {start_date:%d/%m/%Y %H:%M:%S} a {end_date:%d/%m/%Y %H:%M:%S} (BRT), refresh={refresh}")
    logger.debug(f"[DEBUG] Fuso horário de start_date: {start_date.tzinfo}, end_date: {end_date.tzinfo}")

    # Consultar estados dos equipamentos
    state_query = (
        f"EXEC dw_sdp_mt_fas..usp_fato_hora "
        f"'{start_date:%d/%m/%Y %H:%M:%S}', '{end_date:%d/%m/%Y %H:%M:%S}'"
    )
    try:
        df_state = query_to_df(state_query)
        logger.debug(f"[DEBUG] Estados brutos retornados: {len(df_state)} linhas")
        logger.debug(f"[DEBUG] Colunas de df_state: {df_state.columns.tolist()}")
        if df_state.empty:
            logger.debug("[DEBUG] Consulta usp_fato_hora retornou DataFrame vazio")
        else:
            logger.debug(f"[DEBUG] Primeiras linhas de df_state: {df_state.head().to_dict()}")
    except Exception as e:
        logger.error(f"[DEBUG] Erro ao consultar usp_fato_hora com intervalo {start_date:%d/%m/%Y %H:%M:%S} a {end_date:%d/%m/%Y %H:%M:%S} (BRT): {str(e)}")
        df_state = pd.DataFrame()

    # Se não houver dados, tentar lista de equipamentos distinta
    if df_state.empty:
        logger.debug("[DEBUG] Nenhum estado retornado, tentando lista distinta de equipamentos")
        equip_query = (
            f"SELECT DISTINCT nome_equipamento, nome_modelo "
            f"FROM dw_sdp_mt_fas..fato_hora "
            f"WHERE dt_registro BETWEEN '{start_date:%d/%m/%Y %H:%M:%S}' AND '{end_date:%d/%m/%Y %H:%M:%S}'"
        )
        try:
            df_equip = query_to_df(equip_query)
            logger.debug(f"[DEBUG] Equipamentos distintos retornados: {len(df_equip)}")
            logger.debug(f"[DEBUG] Colunas de df_equip: {df_equip.columns.tolist()}")
            if df_equip.empty:
                logger.debug("[DEBUG] Consulta de equipamentos distintos retornou DataFrame vazio")
            else:
                logger.debug(f"[DEBUG] Primeiras linhas de df_equip: {df_equip.head().to_dict()}")
        except Exception as e:
            logger.error(f"[DEBUG] Erro ao consultar equipamentos distintos com intervalo {start_date:%d/%m/%Y %H:%M:%S} a {end_date:%d/%m/%Y %H:%M:%S} (BRT): {str(e)}")
            df_equip = pd.DataFrame()
    else:
        # Tentar consultar tb_equipamentos
        equip_query = "SELECT nome_equipamento, nome_modelo FROM dw_sdp_mt_fas..tb_equipamentos WHERE ativo = 1"
        try:
            df_equip = query_to_df(equip_query)
            logger.debug(f"[DEBUG] Equipamentos retornados de tb_equipamentos: {len(df_equip)}")
            logger.debug(f"[DEBUG] Colunas de df_equip: {df_equip.columns.tolist()}")
            if df_equip.empty:
                logger.debug("[DEBUG] Consulta tb_equipamentos retornou DataFrame vazio")
            else:
                logger.debug(f"[DEBUG] Primeiras linhas de df_equip: {df_equip.head().to_dict()}")
        except Exception as e:
            logger.warning(f"[DEBUG] Tabela tb_equipamentos não acessível: {str(e)}, usando equipamentos de fato_hora")
            df_equip = df_state[["nome_equipamento", "nome_modelo"]].drop_duplicates()

    if df_equip.empty and df_state.empty:
        logger.debug("[DEBUG] Nenhum dado retornado de nenhuma consulta")
        return pd.DataFrame()

    # Combinar equipamentos com estados (LEFT JOIN)
    df = df_equip[["nome_equipamento", "nome_modelo"]].merge(
        df_state,
        on=["nome_equipamento", "nome_modelo"],
        how="left"
    )
    logger.debug(f"[DEBUG] Após merge: {len(df)} linhas")
    logger.debug(f"[DEBUG] Colunas de df após merge: {df.columns.tolist()}")
    if df.empty:
        logger.debug("[DEBUG] DataFrame resultante do merge está vazio")
    else:
        logger.debug(f"[DEBUG] Primeiras linhas de df após merge: {df.head().to_dict()}")

    # Preencher estados ausentes
    df["nome_estado"] = df["nome_estado"].fillna("DESCONHECIDO")
    df["nome_tipo_estado"] = df["nome_tipo_estado"].fillna("DESCONHECIDO")
    df["id_lancamento"] = df["id_lancamento"].fillna(-1)
    df["dt_registro"] = df["dt_registro"].fillna(pd.Timestamp("1900-01-01"))

    # Normalizar colunas de texto uma única vez
    for col in ["nome_equipamento", "nome_modelo", "nome_estado", "nome_tipo_estado"]:
        if col in df.columns:
            df[col] = df[col].str.strip().str.upper().astype("category")

    # Converter dt_registro para datetime com fuso horário
    if "dt_registro" in df.columns:
        df["dt_registro"] = pd.to_datetime(df["dt_registro"], errors="coerce")
        # Assumir que dt_registro está em BRT e associar TIMEZONE
        df["dt_registro"] = df["dt_registro"].dt.tz_localize(TIMEZONE, ambiguous='raise', nonexistent='raise')
        invalid_dates = df["dt_registro"].isna().sum()
        logger.debug(f"[DEBUG] Linhas com datas inválidas (NaT): {invalid_dates}")

    # Verificar colunas esperadas
    expected_cols = ["nome_equipamento", "nome_modelo", "nome_estado", "nome_tipo_estado", "dt_registro", "id_lancamento"]
    missing_cols = [col for col in expected_cols if col not in df.columns]
    if missing_cols:
        logger.warning(f"[DEBUG] Colunas esperadas ausentes: {missing_cols}")

    return df

@profile_time
def get_latest_records() -> pd.DataFrame:
    """Retorna o registro mais recente por equipamento, com dt_registro_inicio."""
    df = fetch_equipment_data(DAY_START, DAY_END)
    if df.empty:
        logger.debug("[DEBUG] Nenhum dado retornado por fetch_equipment_data")
        return pd.DataFrame()

    # Obter dt_registro mínimo por equipamento e id_lancamento
    dt_min = df.groupby(["nome_equipamento", "id_lancamento"], as_index=False)["dt_registro"].min()

    # Obter o registro mais recente por equipamento
    df_sorted = df.sort_values("dt_registro")
    latest = df_sorted.groupby("nome_equipamento", as_index=False).last()

    # Combinar com dt_registro mínimo
    current_state = pd.merge(
        latest,
        dt_min,
        on=["nome_equipamento", "id_lancamento"],
        suffixes=("", "_inicio"),
        how="left"
    )
    current_state.rename(columns={"dt_registro_inicio": "dt_registro_inicio"}, inplace=True)

    logger.debug(f"[DEBUG] Registros mais recentes: {len(current_state)} linhas")
    return current_state

@profile_time
def create_tv_layout(df: pd.DataFrame, filter_values: Optional[List[str]] = None) -> html.Div:
    """
    Cria o layout de TV com cartões de equipamentos agrupados por estado e tipo.
    """
    if df.empty:
        logger.debug("[DEBUG] DataFrame vazio em create_tv_layout")
        return html.Div(
            "Sem dados para exibir. Verifique a disponibilidade de dados no banco (Horário de Brasília) ou a conexão no Render.",
            className="text-center my-4"
        )

    # Remover registros do equipamento TRIMAK
    df = df[df["nome_equipamento"] != "TRIMAK"]
    logger.debug(f"[DEBUG] Após remover TRIMAK: {len(df)} linhas")

    # Aplicar filtro de nome_tipo_estado, se fornecido e não vazio
    if filter_values and filter_values != [""]:
        filter_values_upper = [v.strip().upper() for v in filter_values if v]
        logger.debug(f"[DEBUG] Aplicando filtro: {filter_values_upper}")
        df = df[df["nome_tipo_estado"].isin(filter_values_upper)]
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
    grouped = df.groupby(group_cols, as_index=False)

    rows = []
    now = datetime.now(tz=TIMEZONE)  # Usar Horário de Brasília
    logger.debug(f"[DEBUG] Fuso horário de now: {now.tzinfo}")
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

            dt_val = pd.to_datetime(row.get("dt_registro_inicio"), errors="coerce")
            logger.debug(f"[DEBUG] dt_val para {equip_name}: {dt_val}, fuso horário: {getattr(dt_val, 'tzinfo', 'None')}")
            if pd.notnull(dt_val):
                # Garantir que dt_val seja tz-aware (assumir BRT se tz-naive)
                if dt_val.tzinfo is None:
                    dt_val = dt_val.tz_localize(TIMEZONE)
                duration = now - dt_val
                time_str = dt_val.strftime("%d/%m/%Y %H:%M:%S")
                band_color, green_val = get_color_for_duration(duration)
                text_color = "black" if green_val > 200 else "white"
            else:
                time_str = "N/A"
                band_color = "#CCCCCC"
                text_color = "white"

            img_url = normalized_model_images.get(model_name, None) if model_name else None
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
                }
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
            className="mb-2"
        )
        rows.append(row_layout)

    logger.debug(f"[DEBUG] Layout criado com {len(rows)} grupos")
    return html.Div([header] + rows)

# [O restante do código permanece idêntico ao fornecido anteriormente, incluindo NAVBAR, layout, e callbacks]

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
                className="text-center mt-4 mb-4",
                style={"fontFamily": "Arial, sans-serif", "fontSize": "1.6rem", "fontWeight": "500"}
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
                            "borderRadius": "8px",
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
    dcc.Interval(id="interval-component", interval=300000, n_intervals=0),
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
    Input("interval-component", "n_intervals")
)
def update_data(n_clicks: int, n_intervals: int) -> Tuple[Optional[str], str]:
    """
    Atualiza os dados com os registros mais recentes por equipamento.
    """
    # Forçar atualização do cache na primeira carga ou ao clicar em Atualizar
    refresh = n_clicks is not None or n_intervals == 0
    try:
        latest = get_latest_records()
    except Exception as e:
        logger.error(f"[DEBUG] Erro ao obter registros mais recentes: {str(e)}")
        return None, "Erro ao carregar dados. Verifique a conexão com o banco ou a disponibilidade de dados (Horário de Brasília) no Render."

    if latest.empty:
        logger.debug("[DEBUG] Nenhum dado retornado por get_latest_records")
        return None, "Sem dados. Verifique a disponibilidade de dados no banco (Horário de Brasília) no Render."

    latest = latest[latest["nome_equipamento"] != "TRIMAK"]
    logger.debug(f"[DEBUG] Após remover TRIMAK em update_data: {len(latest)} linhas")

    # Converter colunas de texto para category antes de serializar
    for col in ["nome_equipamento", "nome_modelo", "nome_estado", "nome_tipo_estado"]:
        if col in latest.columns:
            latest[col] = latest[col].astype("category")

    try:
        json_data = latest.to_json(orient="records", date_format="iso")
    except Exception as e:
        logger.error(f"[DEBUG] Erro ao serializar dados para JSON: {str(e)}")
        return None, "Erro ao processar dados no Render."

    last_update_text = f"Última atualização: {datetime.now(tz=TIMEZONE).strftime('%d/%m/%Y %H:%M:%S')} (BRT)"
    return json_data, last_update_text

@callback(
    Output("filter-dropdown", "options"),
    Output("filter-dropdown", "value"),
    Input("latest-data-store", "data")
)
def update_filter_options(json_data: Optional[Union[str, dict]]) -> Tuple[List[Dict[str, str]], List[str]]:
    """
    Atualiza as opções do Dropdown de filtro e define valores padrão.

    Args:
        json_data (Optional[Union[str, dict]]): Dados em JSON.

    Returns:
        Tuple[List[Dict[str, str]], List[str]]: Opções do dropdown e valores padrão.
    """
    if not json_data:
        logger.debug("[DEBUG] Nenhum dado em update_filter_options")
        return [], []

    try:
        df = pd.read_json(json_data, orient="records")
    except Exception as e:
        logger.error(f"[DEBUG] Erro ao ler JSON em update_filter_options: {str(e)}")
        return [], []

    if df.empty or "nome_tipo_estado" not in df.columns:
        logger.debug("[DEBUG] DataFrame vazio ou sem nome_tipo_estado")
        return [], []

    tipos = sorted(df["nome_tipo_estado"].dropna().unique())
    logger.debug(f"[DEBUG] Tipos de estado disponíveis: {tipos}")
    options = [{"label": t, "value": t} for t in tipos]

    # Definir valores predefinidos
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
def render_tv_layout(json_data: Optional[Union[str, dict]], filter_values: Optional[List[str]]) -> html.Div:
    """
    Renderiza o layout de TV com base nos dados e filtros.
    """
    if not json_data:
        logger.debug("[DEBUG] Nenhum dado em render_tv_layout")
        return html.Div(
            "Erro ao carregar dados. Verifique a conexão com o banco, a disponibilidade de dados (Horário de Brasília) ou clique em 'Atualizar' no Render.",
            className="text-center my-4"
        )

    try:
        df = pd.read_json(json_data, orient="records")
    except Exception as e:
        logger.error(f"[DEBUG] Erro ao ler JSON em render_tv_layout: {str(e)}")
        return html.Div(
            "Erro ao processar dados no Render. Verifique o log para detalhes.",
            className="text-center my-4"
        )

    logger.debug(f"[DEBUG] Dados recebidos em render_tv_layout: {len(df)} linhas")
    logger.debug(f"[DEBUG] Filter values: {filter_values}")
    if df.empty:
        logger.debug("[DEBUG] DataFrame vazio em render_tv_layout")
        return html.Div(
            "Sem dados para exibir. Verifique a disponibilidade de dados no banco (Horário de Brasília) no Render.",
            className="text-center my-4"
        )

    return create_tv_layout(df, filter_values)
