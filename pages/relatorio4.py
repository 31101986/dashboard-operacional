import math
import logging
import time
from datetime import datetime, timedelta
from typing import Tuple, List, Dict, Any, Union

import dash
from dash import dcc, html, callback, Input, Output, State
from dash import dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
import numpy as np
from dash.dash_table.Format import Format, Scheme
from pandas.api.types import CategoricalDtype

from db import query_to_df
from app import cache
from config import META_MINERIO, META_ESTERIL, TIMEZONE, PROJECTS_CONFIG, PROJECT_LABELS

# Configuração do log
logging.basicConfig(
    level=logging.INFO,
    filename="relatorio4.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Formato numérico para tabelas
num_format = Format(precision=2, scheme=Scheme.fixed, group=True)

# Modelos para indicadores
ESCAVACAO_MODELOS = [
    "ESCAVADEIRA HIDRAULICA SANY SY750H",
    "ESCAVADEIRA HIDRÁULICA CAT 352",
    "ESCAVADEIRA HIDRÁULICA CAT 374DL",
    "ESCAVADEIRA HIDRÁULICA VOLVO EC750DL",
]
TRANSPORTE_MODELOS = [
    "MERCEDES BENZ AROCS 4851/45 8X4",
    "VOLVO FMX 500 8X4"
]
PERFURACAO_MODELOS = [
    "PERFURATRIZ HIDRAULICA SANDVIK DP1500I",
    "PERFURATRIZ HIDRAULICA SANDVIK DX800"
]

# ===================== Funções Auxiliares =====================

def consulta_producao(dia_str: str, projeto: str) -> pd.DataFrame:
    """Consulta o fato_producao para o dia informado e projeto especificado."""
    logger.debug(f"[DEBUG] Consultando fato_producao para {dia_str} e projeto {projeto}")
    if projeto not in PROJECTS_CONFIG:
        logger.error(f"[DEBUG] Projeto {projeto} não encontrado em PROJECTS_CONFIG")
        return pd.DataFrame()
    query = f"EXEC {PROJECTS_CONFIG[projeto]['database']}..usp_fato_producao '{dia_str}', '{dia_str}'"
    try:
        df = query_to_df(query, projeto=projeto)
        logger.debug(f"[DEBUG] Dados brutos retornados: {len(df)} linhas")
        logger.debug(f"[DEBUG] Colunas retornadas: {list(df.columns)}")
    except Exception as e:
        logger.error(f"[Rel4] Erro ao consultar fato_producao: {e}")
        return pd.DataFrame()
    if df.empty or "dt_registro_turno" not in df.columns:
        logger.debug("[DEBUG] DataFrame vazio ou sem coluna 'dt_registro_turno'")
        return df
    df["dt_registro_turno"] = pd.to_datetime(df["dt_registro_turno"], errors="coerce")
    if df["dt_registro_turno"].dt.tz is None:
        df["dt_registro_turno"] = df["dt_registro_turno"].dt.tz_localize(TIMEZONE)
    filtro_data = datetime.strptime(dia_str, "%d/%m/%Y").replace(tzinfo=TIMEZONE).date()
    df = df.loc[df["dt_registro_turno"].dt.date == filtro_data]
    logger.debug(f"[DEBUG] Após filtro por data: {len(df)} linhas")
    return df

def consulta_hora(dia_str: str, projeto: str) -> pd.DataFrame:
    """Consulta o fato_hora para o dia informado e projeto especificado."""
    logger.debug(f"[DEBUG] Consultando fato_hora para {dia_str} e projeto {projeto}")
    if projeto not in PROJECTS_CONFIG:
        logger.error(f"[DEBUG] Projeto {projeto} não encontrado em PROJECTS_CONFIG")
        return pd.DataFrame()
    query = f"EXEC {PROJECTS_CONFIG[projeto]['database']}..usp_fato_hora '{dia_str}', '{dia_str}'"
    try:
        df = query_to_df(query, projeto=projeto)
        logger.debug(f"[DEBUG] Dados brutos retornados: {len(df)} linhas")
        logger.debug(f"[DEBUG] Colunas retornadas: {list(df.columns)}")
    except Exception as e:
        logger.error(f"[Rel4] Erro ao consultar fato_hora: {e}")
        return pd.DataFrame()
    if df.empty or "dt_registro_turno" not in df.columns:
        logger.debug("[DEBUG] DataFrame vazio ou sem coluna 'dt_registro_turno'")
        return df
    df["dt_registro_turno"] = pd.to_datetime(df["dt_registro_turno"], errors="coerce")
    if df["dt_registro_turno"].dt.tz is None:
        df["dt_registro_turno"] = df["dt_registro_turno"].dt.tz_localize(TIMEZONE)
    filtro_data = datetime.strptime(dia_str, "%d/%m/%Y").replace(tzinfo=TIMEZONE).date()
    df = df.loc[df["dt_registro_turno"].dt.date == filtro_data]
    logger.debug(f"[DEBUG] Após filtro por data: {len(df)} linhas")
    return df

def calcular_horas_desde_7h(day_choice: str) -> float:
    """
    Calcula as horas decorridas:
      - Se 'ontem', retorna 24 horas.
      - Se 'hoje', calcula a diferença desde as 07:00 do dia atual.
    """
    if day_choice == "ontem":
        logger.debug("[DEBUG] Período 'ontem': retornando 24 horas")
        return 24.0
    now = datetime.now(TIMEZONE)
    start_7h = now.replace(hour=7, minute=0, second=0, microsecond=0)
    if now < start_7h:
        start_7h -= timedelta(days=1)
    horas_passadas = (now - start_7h).total_seconds() / 3600.0
    horas = max(horas_passadas, 0.01)
    logger.debug(f"[DEBUG] Horas decorridas desde 07:00: {horas:.2f}")
    return horas

def calc_indicadores_agrupados_por_modelo(df: pd.DataFrame, modelos_lista: List[str], estado_col: str = "nome_tipo_estado") -> Tuple[List[dict], List[dict], List[dict]]:
    """
    Agrupa os dados (do fato_hora) por modelo, calculando Disponibilidade, Utilização e Rendimento.
    Retorna (data, columns, style_data_conditional) para o DataTable.
    """
    needed_cols = {"nome_modelo", estado_col, "tempo_hora"}
    if not needed_cols.issubset(df.columns):
        logger.debug(f"[DEBUG] Colunas necessárias ausentes: {needed_cols - set(df.columns)}")
        return [], [], []
    df_f = df.loc[df["nome_modelo"].isin(modelos_lista)].copy()
    if df_f.empty:
        logger.debug("[DEBUG] Nenhum dado para os modelos especificados")
        return [], [], []
    df_f["tempo_hora"] = pd.to_numeric(df_f["tempo_hora"], errors="coerce").fillna(0)
    
    grp_total = df_f.groupby("nome_modelo", as_index=False)["tempo_hora"].sum().rename(columns={"tempo_hora": "total"})
    grp_fora = df_f[df_f[estado_col] == "Fora de Frota"].groupby("nome_modelo", as_index=False)["tempo_hora"].sum().rename(columns={"tempo_hora": "fora"})
    grp_manut = df_f[df_f[estado_col].isin(["Manutenção Preventiva", "Manutenção Corretiva", "Manutenção Operacional"])].groupby("nome_modelo", as_index=False)["tempo_hora"].sum().rename(columns={"tempo_hora": "manut"})
    grp_trab = df_f[df_f[estado_col].isin(["Operando", "Serviço Auxiliar", "Atraso Operacional"])].groupby("nome_modelo", as_index=False)["tempo_hora"].sum().rename(columns={"tempo_hora": "trab"})
    
    df_ind = pd.merge(grp_total, grp_fora, on="nome_modelo", how="left").fillna(0)
    df_ind = pd.merge(df_ind, grp_manut, on="nome_modelo", how="left").fillna(0)
    df_ind = pd.merge(df_ind, grp_trab, on="nome_modelo", how="left").fillna(0)
    
    df_ind["cal"] = df_ind["total"] - df_ind["fora"]
    df_ind["disp"] = df_ind["cal"] - df_ind["manut"]
    df_ind["disponibilidade"] = np.where(df_ind["cal"] > 0, 100 * df_ind["disp"] / df_ind["cal"], 0)
    df_ind["utilizacao"] = np.where(df_ind["disp"] > 0, 100 * df_ind["trab"] / df_ind["disp"], 0)
    df_ind["rendimento"] = df_ind["disponibilidade"] * df_ind["utilizacao"] / 100.0

    df_ind = df_ind[["nome_modelo", "disponibilidade", "utilizacao", "rendimento"]]
    
    # Cálculo global utilizando todos os dados
    total_total = df_f["tempo_hora"].sum()
    total_fora = df_f.loc[df_f[estado_col] == "Fora de Frota", "tempo_hora"].sum()
    total_manut = df_f.loc[df_f[estado_col].isin(["Manutenção Preventiva", "Manutenção Corretiva", "Manutenção Operacional"]), "tempo_hora"].sum()
    total_trab = df_f.loc[df_f[estado_col].isin(["Operando", "Serviço Auxiliar", "Atraso Operacional"]), "tempo_hora"].sum()
    total_cal = total_total - total_fora
    total_disp = total_cal - total_manut
    overall_disp = (100 * total_disp / total_cal) if total_cal > 0 else 0
    overall_util = (100 * total_trab / total_disp) if total_disp > 0 else 0
    overall_rend = overall_disp * overall_util / 100.0

    total_row = pd.DataFrame([{
         "nome_modelo": "TOTAL",
         "disponibilidade": overall_disp,
         "utilizacao": overall_util,
         "rendimento": overall_rend
    }])
    df_ind = pd.concat([df_ind, total_row], ignore_index=True)
    data = df_ind.to_dict("records")
    columns = [
       {"name": "Modelo", "id": "nome_modelo", "type": "text"},
       {"name": "Disponibilidade (%)", "id": "disponibilidade", "type": "numeric", "format": num_format},
       {"name": "Utilização (%)", "id": "utilizacao", "type": "numeric", "format": num_format},
       {"name": "Rendimento (%)", "id": "rendimento", "type": "numeric", "format": num_format},
    ]
    style_cond = [
       {"if": {"filter_query": "{disponibilidade} >= 80", "column_id": "disponibilidade"}, "color": "green"},
       {"if": {"filter_query": "{disponibilidade} < 80", "column_id": "disponibilidade"}, "color": "red"},
       {"if": {"filter_query": "{utilizacao} >= 75", "column_id": "utilizacao"}, "color": "green"},
       {"if": {"filter_query": "{utilizacao} < 75", "column_id": "utilizacao"}, "color": "red"},
       {"if": {"filter_query": "{rendimento} >= 60", "column_id": "rendimento"}, "color": "green"},
       {"if": {"filter_query": "{rendimento} < 60", "column_id": "rendimento"}, "color": "red"},
       {"if": {"filter_query": '{nome_modelo} = "TOTAL"'}, "backgroundColor": "#fff9c4", "fontWeight": "bold"}
    ]
    logger.debug(f"[DEBUG] Indicadores calculados: {len(data)} linhas")
    return data, columns, style_cond

# ===================== LAYOUT =====================

# Estilo comum para tabelas
common_table_style: Dict[str, Any] = {
    "style_table": {
        "overflowX": "auto",
        "width": "100%",
        "margin": "auto",
        "borderRadius": "8px"
    },
    "style_cell": {
        "textAlign": "center",
        "padding": "8px",
        "fontFamily": "Arial, sans-serif",
        "fontSize": "0.9rem",
        "whiteSpace": "normal",
        "border": "1px solid #e9ecef"
    },
    "style_header": {
        "background": "linear-gradient(90deg, #343a40, #495057)",
        "fontWeight": "bold",
        "textAlign": "center",
        "color": "white",
        "fontFamily": "Arial, sans-serif",
        "fontSize": "0.9rem",
        "border": "1px solid #e9ecef"
    }
}

# Navbar personalizada com botão de retorno e horário local
navbar = dbc.Navbar(
    dbc.Container([
        # Título com ícone estilizado
        dbc.NavbarBrand([
            html.I(className="fas fa-chart-line mr-2"),
            "Produção e Indicadores"
        ], href="/relatorio4", className="ms-2 d-flex align-items-center", style={"fontSize": "1.1rem"}),
        # Botão de retorno à página inicial
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
        # Horário local em badge
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
    html.Div([
        navbar,
        dbc.Row(
            dbc.Col(
                html.H3(
                    "Produção e Indicadores",
                    className="text-center mt-4 mb-4",
                    style={
                        "fontFamily": "Arial, sans-serif",
                        "fontSize": "1.6rem",
                        "fontWeight": "500"
                    }
                ),
                width=12
            ),
            className="mb-3"
        ),
        # Seleção de Dia
        dbc.Card([
            dbc.CardHeader(
                html.H5("Selecionar Período", className="mb-0 text-white", style={
                    "fontSize": "1.1rem",
                    "fontWeight": "500",
                    "fontFamily": "Arial, sans-serif"
                }),
                style={"background": "linear-gradient(90deg, #343a40, #495057)"}
            ),
            dbc.CardBody([
                html.P(
                    "Escolha se deseja visualizar o dia atual ou o dia anterior.",
                    style={"fontFamily": "Arial, sans-serif", "fontSize": "0.9rem", "marginBottom": "10px"}
                ),
                dbc.RadioItems(
                    id="rel4-day-selector",
                    className="btn-group",
                    inputClassName="btn-check",
                    labelClassName="btn btn-outline-primary",
                    labelCheckedClassName="active",
                    options=[
                        {"label": "Dia Atual", "value": "hoje"},
                        {"label": "Dia Anterior", "value": "ontem"},
                    ],
                    value="hoje",
                    inline=True,
                    style={
                        "fontSize": "0.9rem",
                        "borderRadius": "8px",
                        "backgroundColor": "#f8f9fa",
                        "padding": "6px"
                    }
                )
            ], style={"padding": "0.8rem"})
        ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none"}),
        # Seleção de Operação (Filtro Opcional) - Reposicionado para o topo
        dbc.Card([
            dbc.CardHeader(
                html.H5("Filtrar por Operação (Opcional)", className="mb-0 text-white", style={
                    "fontSize": "1.1rem",
                    "fontWeight": "500",
                    "fontFamily": "Arial, sans-serif"
                }),
                style={"background": "linear-gradient(90deg, #343a40, #495057)"}
            ),
            dbc.CardBody([
                dcc.Dropdown(
                    id="rel4-operacao-filter",
                    options=[],
                    value=None,
                    placeholder="Selecione uma operação (ou deixe em branco)",
                    multi=True,
                    style={
                        "width": "100%",
                        "borderRadius": "6px",
                        "borderColor": "#17a2b8",
                        "fontSize": "0.9rem",
                        "marginBottom": "10px"
                    },
                    className="custom-dropdown"
                )
            ], style={"padding": "0.8rem"})
        ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={
            "borderRadius": "12px",
            "border": "none",
            "position": "relative",
            "zIndex": "10"
        }),
        # Stores para dados de produção e hora
        dcc.Store(id="rel4-producao-store"),
        dcc.Store(id="rel4-hora-store"),
        # 1) Tabela de Movimentação
        dbc.Card([
            dbc.CardHeader(
                html.H5("Movimentação (Dia Atual ou Dia Anterior)", className="mb-0 text-white", style={
                    "fontSize": "1.1rem",
                    "fontWeight": "500",
                    "fontFamily": "Arial, sans-serif"
                }),
                style={"background": "linear-gradient(90deg, #343a40, #495057)"}
            ),
            dbc.CardBody(
                dcc.Loading(
                    dash_table.DataTable(
                        id="rel4-tabela-movimentacao",
                        columns=[
                            {"name": "Operação", "id": "nome_operacao", "type": "text"},
                            {"name": "Viagens", "id": "viagens", "type": "numeric", "format": num_format},
                            {"name": "Volume", "id": "volume", "type": "numeric", "format": num_format},
                            {"name": "Ritmo (m³/h)", "id": "ritmo_volume", "type": "numeric", "format": num_format},
                        ],
                        style_data_conditional=[
                            {
                                "if": {"filter_query": '{nome_operacao} = "TOTAL"'},
                                "backgroundColor": "#fff9c4",
                                "fontWeight": "bold"
                            }
                        ],
                        page_size=10,
                        **common_table_style
                    ),
                    type="default"
                ),
                style={"padding": "0.8rem"}
            )
        ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none"}),
        # 2) Gráfico de Viagens por Hora Trabalhada
        dbc.Card([
            dbc.CardHeader(
                html.H5("Viagens por Hora Trabalhada", className="mb-0 text-white", style={
                    "fontSize": "1.1rem",
                    "fontWeight": "500",
                    "fontFamily": "Arial, sans-serif"
                }),
                style={"background": "linear-gradient(90deg, #343a40, #495057)"}
            ),
            dbc.CardBody(
                dcc.Loading(
                    dcc.Graph(
                        id="rel4-grafico-viagens-hora",
                        config={"displayModeBar": False},
                        style={"minHeight": "450px"}
                    ),
                    type="default"
                ),
                style={"padding": "0.8rem"}
            )
        ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none"}),
        # 3) Tabelas de Indicadores
        # Indicadores - Escavação
        dbc.Card([
            dbc.CardHeader(
                html.H5("Indicadores - Escavação", className="mb-0 text-white", style={
                    "fontSize": "1.1rem",
                    "fontWeight": "500",
                    "fontFamily": "Arial, sans-serif"
                }),
                style={"background": "linear-gradient(90deg, #343a40, #495057)"}
            ),
            dbc.CardBody(
                dcc.Loading(
                    dash_table.DataTable(
                        id="rel4-tabela-ind-escavacao",
                        columns=[],
                        data=[],
                        style_data_conditional=[
                            {"if": {"filter_query": '{nome_modelo} = "TOTAL"'}, "backgroundColor": "#fff9c4", "fontWeight": "bold"}
                        ],
                        page_size=10,
                        **common_table_style
                    ),
                    type="default"
                ),
                style={"padding": "0.8rem"}
            )
        ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none"}),
        # Indicadores - Transporte
        dbc.Card([
            dbc.CardHeader(
                html.H5("Indicadores - Transporte", className="mb-0 text-white", style={
                    "fontSize": "1.1rem",
                    "fontWeight": "500",
                    "fontFamily": "Arial, sans-serif"
                }),
                style={"background": "linear-gradient(90deg, #343a40, #495057)"}
            ),
            dbc.CardBody(
                dcc.Loading(
                    dash_table.DataTable(
                        id="rel4-tabela-ind-transporte",
                        columns=[],
                        data=[],
                        style_data_conditional=[
                            {"if": {"filter_query": '{nome_modelo} = "TOTAL"'}, "backgroundColor": "#fff9c4", "fontWeight": "bold"}
                        ],
                        page_size=10,
                        **common_table_style
                    ),
                    type="default"
                ),
                style={"padding": "0.8rem"}
            )
        ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none"}),
        # Indicadores - Perfuração
        dbc.Card([
            dbc.CardHeader(
                html.H5("Indicadores - Perfuração", className="mb-0 text-white", style={
                    "fontSize": "1.1rem",
                    "fontWeight": "500",
                    "fontFamily": "Arial, sans-serif"
                }),
                style={"background": "linear-gradient(90deg, #343a40, #495057)"}
            ),
            dbc.CardBody(
                dcc.Loading(
                    dash_table.DataTable(
                        id="rel4-tabela-ind-perfuracao",
                        columns=[],
                        data=[],
                        style_data_conditional=[
                            {"if": {"filter_query": '{nome_modelo} = "TOTAL"'}, "backgroundColor": "#fff9c4", "fontWeight": "bold"}
                        ],
                        page_size=10,
                        **common_table_style
                    ),
                    type="default"
                ),
                style={"padding": "0.8rem"}
            )
        ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none"}),
        # Indicadores - Auxiliares
        dbc.Card([
            dbc.CardHeader(
                html.H5("Indicadores - Auxiliares", className="mb-0 text-white", style={
                    "fontSize": "1.1rem",
                    "fontWeight": "500",
                    "fontFamily": "Arial, sans-serif"
                }),
                style={"background": "linear-gradient(90deg, #343a40, #495057)"}
            ),
            dbc.CardBody(
                dcc.Loading(
                    dash_table.DataTable(
                        id="rel4-tabela-ind-auxiliares",
                        columns=[],
                        data=[],
                        style_data_conditional=[
                            {"if": {"filter_query": '{nome_modelo} = "TOTAL"'}, "backgroundColor": "#fff9c4", "fontWeight": "bold"}
                        ],
                        page_action="none",
                        **common_table_style
                    ),
                    type="default"
                ),
                style={"padding": "0.8rem"}
            )
        ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none"}),
    ]),
], fluid=True)

# ===================== CALLBACKS =====================

@dash.callback(
    Output("rel4-producao-store", "data"),
    Output("rel4-hora-store", "data"),
    Input("rel4-day-selector", "value"),
    Input("projeto-store", "data")
)
def fetch_data_dia_escolhido(day_choice: str, projeto: str) -> Tuple[Any, Any]:
    """
    Busca os dados de produção e de hora para o dia selecionado e projeto especificado.
    Retorna os dados serializados em JSON.
    """
    if not projeto:
        logger.debug("[DEBUG] Nenhum projeto selecionado, retornando dados vazios")
        return {}, {}
    if day_choice == "ontem":
        data_str = (datetime.now(TIMEZONE) - timedelta(days=1)).strftime("%d/%m/%Y")
    else:
        data_str = datetime.now(TIMEZONE).strftime("%d/%m/%Y")
    df_prod = consulta_producao(data_str, projeto)
    df_hora = consulta_hora(data_str, projeto)
    logger.debug(f"[DEBUG] Dados para stores - Produção: {len(df_prod)} linhas, Hora: {len(df_hora)} linhas")
    return (
        df_prod.to_json(date_format="iso", orient="records") if not df_prod.empty else {},
        df_hora.to_json(date_format="iso", orient="records") if not df_hora.empty else {}
    )

@dash.callback(
    Output("rel4-operacao-filter", "options"),
    Input("rel4-producao-store", "data")
)
def update_operacao_options(json_prod: Union[str, dict]) -> List[dict]:
    """Atualiza as opções do dropdown com base nos valores únicos de nome_operacao, excluindo None."""
    if not json_prod or isinstance(json_prod, dict):
        logger.debug("[DEBUG] Nenhum dado de produção para atualizar opções de operação")
        return []
    df = pd.read_json(json_prod, orient="records")
    if df.empty or "nome_operacao" not in df.columns:
        logger.debug("[DEBUG] DataFrame vazio ou sem coluna 'nome_operacao'")
        return []
    # Filtra valores None antes de ordenar
    unique_ops = [op for op in df["nome_operacao"].unique() if op is not None]
    options = [{"label": op, "value": op} for op in sorted(unique_ops)]
    logger.debug(f"[DEBUG] Opções de operação atualizadas: {len(options)} itens")
    return options

@dash.callback(
    Output("rel4-tabela-movimentacao", "data"),
    Output("rel4-tabela-movimentacao", "style_data_conditional"),
    Input("rel4-producao-store", "data"),
    Input("rel4-day-selector", "value"),
    Input("rel4-operacao-filter", "value")
)
def update_tabela_movimentacao(json_prod: Union[str, dict], day_choice: str, operacao_filter: Union[str, List[str], None]) -> Tuple[List[dict], List[dict]]:
    """
    Atualiza a tabela de movimentação sem filtro automático, com filtro opcional por nome_operacao.
    """
    if not json_prod or isinstance(json_prod, dict):
        logger.debug("[DEBUG] Nenhum dado de produção para tabela de movimentação")
        return [], []
    df = pd.read_json(json_prod, orient="records")
    if df.empty:
        logger.debug("[DEBUG] DataFrame de produção vazio")
        return [], []
    # Remove linhas onde nome_operacao é None
    df = df[df["nome_operacao"].notna()]
    df["nome_operacao"] = df["nome_operacao"].str.title()  # Normaliza capitalização
    df_grp = df.groupby("nome_operacao", as_index=False).agg(
        viagens=("nome_operacao", "size"),
        volume=("volume", "sum")
    )
    if operacao_filter:
        if isinstance(operacao_filter, str):
            operacao_filter = [operacao_filter]
        df_grp = df_grp[df_grp["nome_operacao"].isin(operacao_filter)]
    total_line = pd.DataFrame({
        "nome_operacao": ["TOTAL"],
        "viagens": [df_grp["viagens"].sum()],
        "volume": [df_grp["volume"].sum()]
    })
    df_grp = pd.concat([df_grp, total_line], ignore_index=True)
    horas_decorridas = calcular_horas_desde_7h(day_choice)
    df_grp["ritmo_volume"] = (df_grp["volume"] / horas_decorridas) * 24.0
    meta_total = META_MINERIO + META_ESTERIL
    style_data_conditional = [
        {
            "if": {"filter_query": f'{{nome_operacao}} = "TOTAL" && {{volume}} >= {meta_total}', "column_id": "volume"},
            "color": "green"
        },
        {
            "if": {"filter_query": f'{{nome_operacao}} = "TOTAL" && {{volume}} < {meta_total}', "column_id": "volume"},
            "color": "red"
        },
        {
            "if": {"filter_query": '{nome_operacao} = "TOTAL"'},
            "backgroundColor": "#fff9c4",
            "fontWeight": "bold"
        }
    ]
    data = df_grp.to_dict("records")
    logger.debug(f"[DEBUG] Tabela de movimentação atualizada: {len(data)} linhas")
    return data, style_data_conditional

@dash.callback(
    Output("rel4-grafico-viagens-hora", "figure"),
    Input("rel4-producao-store", "data"),
    Input("rel4-hora-store", "data"),
    Input("projeto-store", "data"),
    Input("rel4-operacao-filter", "value")  # Novo input para o filtro de operação
)
def update_grafico_viagens_hora(json_prod: Union[str, dict], json_hora: Union[str, dict], projeto: str, operacao_filter: Union[str, List[str], None]) -> Any:
    """
    Cria o gráfico de Viagens por Hora Trabalhada a partir dos dados de produção e fato_hora, aplicando filtro de operação.
    Exibe mensagem se nenhum projeto estiver selecionado ou se não houver dados.
    """
    if not projeto:
        logger.debug("[DEBUG] Nenhum projeto selecionado para gráfico de viagens/hora")
        return px.bar(title="Selecione uma obra para visualizar os dados.", template="plotly_white")
    if (not json_prod or isinstance(json_prod, dict)) or (not json_hora or isinstance(json_hora, dict)):
        logger.debug("[DEBUG] Dados insuficientes para gráfico de viagens/hora")
        return px.bar(title="Sem dados para o período.", template="plotly_white")
    
    df_prod = pd.read_json(json_prod, orient="records")
    df_hora = pd.read_json(json_hora, orient="records")
    if df_prod.empty or df_hora.empty:
        logger.debug("[DEBUG] DataFrames vazios (Produção ou Hora)")
        return px.bar(title="Sem dados para o período.", template="plotly_white")

    # Aplicar o filtro de operação, se fornecido
    if operacao_filter:
        if isinstance(operacao_filter, str):
            operacao_filter = [operacao_filter]
        df_prod = df_prod[df_prod["nome_operacao"].isin(operacao_filter)]
        if df_prod.empty:
            logger.debug("[DEBUG] Nenhum dado após filtro de operação")
            return px.bar(title="Nenhum dado para as operações selecionadas.", template="plotly_white")

    # Verificar coluna de estado
    estado_col = "nome_tipo_estado" if "nome_tipo_estado" in df_hora.columns else "nome_estado" if "nome_estado" in df_hora.columns else None
    if estado_col is None:
        logger.debug("[DEBUG] Nenhuma coluna de estado encontrada (nome_tipo_estado ou nome_estado)")
        return px.bar(title="Sem dados (coluna de estado ausente).", template="plotly_white")
    
    df_viagens = df_prod.groupby("nome_equipamento_utilizado", as_index=False).agg(
        viagens=("nome_equipamento_utilizado", "count")
    )
    estados_trabalho = ["Operando", "Serviço Auxiliar", "Atraso Operacional"]
    df_hora_filtrada = df_hora.loc[df_hora[estado_col].isin(estados_trabalho)]
    df_horas = df_hora_filtrada.groupby("nome_equipamento", as_index=False).agg(
        horas_trabalhadas=("tempo_hora", "sum")
    )
    df_merged = pd.merge(
        df_viagens, df_horas,
        left_on="nome_equipamento_utilizado",
        right_on="nome_equipamento",
        how="inner"
    )
    if df_merged.empty:
        logger.debug("[DEBUG] Nenhum dado após merge para gráfico")
        return px.bar(title="Sem dados para gerar Viagens/Hora após filtro.", template="plotly_white")
    
    df_merged["viagens_por_hora"] = df_merged["viagens"] / df_merged["horas_trabalhadas"].replace(0, np.nan)
    df_merged["viagens_por_hora"] = df_merged["viagens_por_hora"].fillna(0)
    df_merged.sort_values("viagens_por_hora", inplace=True)

    # Ajuste no título para indicar as operações filtradas
    title = "Viagens por Hora Trabalhada"
    if operacao_filter:
        title += f" (Filtrado: {', '.join(operacao_filter)})"

    fig = px.bar(
        df_merged,
        x="nome_equipamento_utilizado",
        y="viagens_por_hora",
        title=title,
        labels={"nome_equipamento_utilizado": "Equipamento", "viagens_por_hora": "Viagens/Hora"},
        text="viagens_por_hora",
        color="viagens_por_hora",
        color_continuous_scale=px.colors.sequential.Viridis,
        template="plotly_white"
    )
    fig.update_traces(texttemplate="%{text:,.2f}", textposition="outside")
    fig.update_layout(
        xaxis_title="Equipamento",
        yaxis_title="Viagens por Hora",
        title_x=0.5,
        margin=dict(l=40, r=40, t=60, b=40),
        # Ajuste para melhorar a legibilidade com poucos dados
        xaxis_tickangle=45,
        height=500 if len(df_merged) > 5 else 400  # Ajusta altura com base no número de equipamentos
    )
    logger.debug(f"[DEBUG] Gráfico de viagens/hora criado com {len(df_merged)} equipamentos")
    return fig

@dash.callback(
    Output("rel4-tabela-ind-escavacao", "data"),
    Output("rel4-tabela-ind-escavacao", "columns"),
    Output("rel4-tabela-ind-escavacao", "style_data_conditional"),
    Input("rel4-hora-store", "data")
)
def update_tabela_ind_escavacao(json_hora: Union[str, dict]) -> Tuple[List[dict], List[dict], List[dict]]:
    if not json_hora or isinstance(json_hora, dict):
        logger.debug("[DEBUG] Nenhum dado de hora para indicadores de escavação")
        return [], [], []
    df_h = pd.read_json(json_hora, orient="records")
    if df_h.empty:
        logger.debug("[DEBUG] DataFrame de hora vazio para escavação")
        return [], [], []
    # Verificar coluna de estado
    estado_col = "nome_tipo_estado" if "nome_tipo_estado" in df_h.columns else "nome_estado" if "nome_estado" in df_h.columns else None
    if estado_col is None:
        logger.debug("[DEBUG] Nenhuma coluna de estado encontrada para indicadores de escavação")
        return [], [], []
    data, columns, style_cond = calc_indicadores_agrupados_por_modelo(df_h, ESCAVACAO_MODELOS, estado_col)
    return data, columns, style_cond

@dash.callback(
    Output("rel4-tabela-ind-transporte", "data"),
    Output("rel4-tabela-ind-transporte", "columns"),
    Output("rel4-tabela-ind-transporte", "style_data_conditional"),
    Input("rel4-hora-store", "data")
)
def update_tabela_ind_transporte(json_hora: Union[str, dict]) -> Tuple[List[dict], List[dict], List[dict]]:
    if not json_hora or isinstance(json_hora, dict):
        logger.debug("[DEBUG] Nenhum dado de hora para indicadores de transporte")
        return [], [], []
    df_h = pd.read_json(json_hora, orient="records")
    if df_h.empty:
        logger.debug("[DEBUG] DataFrame de hora vazio para transporte")
        return [], [], []
    # Verificar coluna de estado
    estado_col = "nome_tipo_estado" if "nome_tipo_estado" in df_h.columns else "nome_estado" if "nome_estado" in df_h.columns else None
    if estado_col is None:
        logger.debug("[DEBUG] Nenhuma coluna de estado encontrada para indicadores de transporte")
        return [], [], []
    data, columns, style_cond = calc_indicadores_agrupados_por_modelo(df_h, TRANSPORTE_MODELOS, estado_col)
    return data, columns, style_cond

@dash.callback(
    Output("rel4-tabela-ind-perfuracao", "data"),
    Output("rel4-tabela-ind-perfuracao", "columns"),
    Output("rel4-tabela-ind-perfuracao", "style_data_conditional"),
    Input("rel4-hora-store", "data")
)
def update_tabela_ind_perfuracao(json_hora: Union[str, dict]) -> Tuple[List[dict], List[dict], List[dict]]:
    if not json_hora or isinstance(json_hora, dict):
        logger.debug("[DEBUG] Nenhum dado de hora para indicadores de perfuração")
        return [], [], []
    df_h = pd.read_json(json_hora, orient="records")
    if df_h.empty:
        logger.debug("[DEBUG] DataFrame de hora vazio para perfuração")
        return [], [], []
    # Verificar coluna de estado
    estado_col = "nome_tipo_estado" if "nome_tipo_estado" in df_h.columns else "nome_estado" if "nome_estado" in df_h.columns else None
    if estado_col is None:
        logger.debug("[DEBUG] Nenhuma coluna de estado encontrada para indicadores de perfuração")
        return [], [], []
    data, columns, style_cond = calc_indicadores_agrupados_por_modelo(df_h, PERFURACAO_MODELOS, estado_col)
    return data, columns, style_cond

@dash.callback(
    Output("rel4-tabela-ind-auxiliares", "data"),
    Output("rel4-tabela-ind-auxiliares", "columns"),
    Output("rel4-tabela-ind-auxiliares", "style_data_conditional"),
    Input("rel4-hora-store", "data")
)
def update_tabela_ind_auxiliares(json_hora: Union[str, dict]) -> Tuple[List[dict], List[dict], List[dict]]:
    if not json_hora or isinstance(json_hora, dict):
        logger.debug("[DEBUG] Nenhum dado de hora para indicadores de auxiliares")
        return [], [], []
    df_h = pd.read_json(json_hora, orient="records")
    if df_h.empty:
        logger.debug("[DEBUG] DataFrame de hora vazio para auxiliares")
        return [], [], []
    # Verificar coluna de estado
    estado_col = "nome_tipo_estado" if "nome_tipo_estado" in df_h.columns else "nome_estado" if "nome_estado" in df_h.columns else None
    if estado_col is None:
        logger.debug("[DEBUG] Nenhuma coluna de estado encontrada para indicadores de auxiliares")
        return [], [], []
    # Lista de todos os modelos exceto os das outras tabelas
    todos_modelos = df_h["nome_modelo"].unique().tolist()
    modelos_existentes = ESCAVACAO_MODELOS + TRANSPORTE_MODELOS + PERFURACAO_MODELOS
    auxiliares_modelos = [modelo for modelo in todos_modelos if modelo not in modelos_existentes]
    if not auxiliares_modelos:
        logger.debug("[DEBUG] Nenhum modelo auxiliar encontrado")
        return [], [], []
    data, columns, style_cond = calc_indicadores_agrupados_por_modelo(df_h, auxiliares_modelos, estado_col)
    return data, columns, style_cond
