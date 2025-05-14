import json
import gzip
from datetime import datetime, timedelta
from typing import Any, Dict, Tuple, List, Union

import dash
from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc
from dash.dash_table import DataTable, FormatTemplate
import plotly.express as px
import pandas as pd
import numpy as np
from dash.dash_table.Format import Format, Scheme
import logging

from db import query_to_df
from config import META_MINERIO, META_ESTERIL, PROJECTS_CONFIG, PROJECT_LABELS
from app import cache

logging.basicConfig(
    level=logging.INFO,
    filename="dashboard.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

num_format = Format(precision=2, scheme=Scheme.fixed, group=True)

# ==================== FUNÇÕES AUXILIARES ====================

@cache.memoize(timeout=300)
def cached_query(query: str, projeto: str) -> pd.DataFrame:
    return query_to_df(query, projeto=projeto)

def convert_date_columns(df: pd.DataFrame, date_cols: List[str]) -> pd.DataFrame:
    if df.empty:
        return df
    for col in date_cols:
        if col in df.columns and not pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df

def filter_by_date(df: pd.DataFrame, date_col: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    if df.empty or date_col not in df.columns:
        return df
    mask = (df[date_col].notna()) & (df[date_col] >= start_date) & (df[date_col] <= end_date)
    return df[mask]

def group_movimentacao(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    if df.empty or group_col not in df.columns:
        return pd.DataFrame(columns=[group_col, "viagens", "volume", "massa"])
    df[group_col] = df[group_col].astype("category").cat.remove_unused_categories()
    grouped = df.groupby(group_col, as_index=False).agg(
        viagens=("cod_viagem", "count"),
        volume=("volume", "sum"),
        massa=("massa", "sum")
    )
    return grouped[grouped[["viagens", "volume", "massa"]].gt(0).any(axis=1)]

def format_total_row(df_group: pd.DataFrame, group_col: str) -> pd.DataFrame:
    if df_group.empty:
        return pd.DataFrame({group_col: ["TOTAL"], "viagens": [0], "volume": [0], "massa": [0]})
    total = pd.DataFrame({
        group_col: ["TOTAL"],
        "viagens": [df_group["viagens"].sum()],
        "volume": [df_group["volume"].sum()],
        "massa": [df_group["massa"].sum()]
    })
    return pd.concat([df_group, total], ignore_index=True)

@cache.memoize(timeout=300)
def load_df(json_data: Union[str, Dict]) -> pd.DataFrame:
    if not json_data or (isinstance(json_data, dict) and "error" in json_data):
        return pd.DataFrame()
    try:
        if isinstance(json_data, str):
            decompressed = gzip.decompress(bytes.fromhex(json_data)).decode("utf-8")
            df = pd.read_json(decompressed, orient="records")
        else:
            df = pd.DataFrame(json_data)
        for col in ["nome_operacao", "nome_modelo", "nome_tipo_equipamento"]:
            if col in df.columns:
                df[col] = df[col].astype("category").cat.remove_unused_categories()
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar DataFrame: {str(e)}")
        return pd.DataFrame()

def compress_json(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    json_str = df.to_json(date_format="iso", orient="records")
    compressed = gzip.compress(json_str.encode("utf-8"))
    return compressed.hex()

# ==================== LAYOUT ====================

navbar = dbc.Navbar(
    dbc.Container([
        dbc.NavbarBrand([
            html.I(className="fas fa-industry mr-2"),
            "Informativo de Produção"
        ], href="/relatorio2", className="ms-2 d-flex align-items-center", style={"fontSize": "1.1rem"}),
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

layout = dbc.Container(
    [
        navbar,
        html.Div(
            id="rel2-no-project-message",
            children=html.P(
                "Selecione uma obra para visualizar os dados.",
                className="text-center my-4"
            )
        ),
        dbc.Row(
            dbc.Col(
                html.H3(
                    "Informativo de Produção",
                    className="text-center mt-4 mb-4",
                    style={"fontFamily": "Arial, sans-serif", "fontSize": "1.6rem", "fontWeight": "500"}
                ),
                width=12
            ),
            className="mb-3"
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Label(
                            "Selecione o Período:",
                            className="fw-bold text-secondary",
                            style={"fontFamily": "Arial, sans-serif", "fontSize": "0.9rem"}
                        ),
                        dcc.DatePickerRange(
                            id="date-picker-range",
                            min_date_allowed=datetime(2020, 1, 1),
                            max_date_allowed=datetime.today().date(),
                            start_date=(datetime.today().date() - timedelta(days=7)),
                            end_date=datetime.today().date(),
                            display_format="DD/MM/YYYY",
                            className="mb-2",
                            style={
                                "fontSize": "0.9rem",
                                "borderRadius": "8px",
                                "backgroundColor": "#f8f9fa",
                                "width": "100%"
                            }
                        ),
                        dbc.Button(
                            [
                                html.I(className="fas fa-filter mr-1"),
                                "Aplicar Filtro"
                            ],
                            id="apply-button",
                            n_clicks=0,
                            className="w-100",
                            style={
                                "fontSize": "0.9rem",
                                "borderRadius": "10px",
                                "background": "linear-gradient(45deg, #007bff, #00aaff)",
                                "color": "#fff",
                                "transition": "all 0.3s",
                                "padding": "6px 12px"
                            }
                        )
                    ],
                    xs=12, md=4
                ),
                dbc.Col(
                    [
                        html.Label(
                            "Filtrar Operações (opcional):",
                            className="fw-bold text-secondary",
                            style={"fontFamily": "Arial, sans-serif", "fontSize": "0.9rem"}
                        ),
                        dcc.Dropdown(
                            id="operacao-dropdown",
                            placeholder="Selecione uma ou mais operações",
                            multi=True,
                            className="mb-2",
                            style={
                                "fontSize": "0.9rem",
                                "borderRadius": "8px",
                                "backgroundColor": "#f8f9fa",
                                "width": "100%"
                            }
                        )
                    ],
                    xs=12, md=8
                )
            ],
            className="mb-3 align-items-end"
        ),
        dcc.Store(id="data-store"),
        dcc.Store(id="data-store-hora"),
        html.Hr(),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                html.H5("Movimentação (Último dia)", className="mb-0 text-white", style={
                                    "fontSize": "1.1rem", "fontWeight": "500", "fontFamily": "Arial, sans-serif"
                                }),
                                style={"background": "linear-gradient(90deg, #343a40, #495057)"}
                            ),
                            dbc.CardBody(
                                dcc.Loading(
                                    DataTable(
                                        id="tabela-1",
                                        style_table={"overflowX": "auto", "width": "100%", "borderRadius": "8px"},
                                        style_header={
                                            "background": "linear-gradient(90deg, #343a40, #495057)",
                                            "fontWeight": "bold",
                                            "textAlign": "center",
                                            "color": "white",
                                            "fontFamily": "Arial, sans-serif",
                                            "fontSize": "0.9rem",
                                            "border": "1px solid #e9ecef"
                                        },
                                        style_cell={
                                            "textAlign": "center",
                                            "whiteSpace": "normal",
                                            "fontFamily": "Arial, sans-serif",
                                            "fontSize": "0.9rem",
                                            "padding": "8px",
                                            "border": "1px solid #e9ecef"
                                        }
                                    ),
                                    type="default"
                                ),
                                style={"padding": "0.8rem"}
                            )
                        ],
                        className="shadow-md mb-3 animate__animated animate__zoomIn",
                        style={"borderRadius": "12px", "border": "none"}
                    ),
                    xs=12, md=6
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                html.H5("Movimentação (Acumulado)", className="mb-0 text-white", style={
                                    "fontSize": "1.1rem", "fontWeight": "500", "fontFamily": "Arial, sans-serif"
                                }),
                                style={"background": "linear-gradient(90deg, #343a40, #495057)"}
                            ),
                            dbc.CardBody(
                                dcc.Loading(
                                    DataTable(
                                        id="tabela-2",
                                        style_table={"overflowX": "auto", "width": "100%", "borderRadius": "8px"},
                                        style_header={
                                            "background": "linear-gradient(90deg, #343a40, #495057)",
                                            "fontWeight": "bold",
                                            "textAlign": "center",
                                            "color": "white",
                                            "fontFamily": "Arial, sans-serif",
                                            "fontSize": "0.9rem",
                                            "border": "1px solid #e9ecef"
                                        },
                                        style_cell={
                                            "textAlign": "center",
                                            "whiteSpace": "normal",
                                            "fontFamily": "Arial, sans-serif",
                                            "fontSize": "0.9rem",
                                            "padding": "8px",
                                            "border": "1px solid #e9ecef"
                                        }
                                    ),
                                    type="default"
                                ),
                                style={"padding": "0.8rem"}
                            )
                        ],
                        className="shadow-md mb-3 animate__animated animate__zoomIn",
                        style={"borderRadius": "12px", "border": "none"}
                    ),
                    xs=12, md=6
                )
            ],
            className="mt-2"
        ),
        html.Hr(),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                html.H5("Gráfico de Volume", className="mb-0", style={
                                    "fontSize": "1.1rem", "fontWeight": "500", "fontFamily": "Arial, sans-serif"
                                }),
                                style={"background": "linear-gradient(90deg, #f8f9fa, #e9ecef)"}
                            ),
                            dbc.CardBody(
                                dcc.Loading(
                                    dcc.Graph(
                                        id="grafico-volume",
                                        config={"displayModeBar": False, "responsive": True},
                                        style={"minHeight": "40vh"}
                                    ),
                                    type="default"
                                ),
                                style={"padding": "0.8rem"}
                            )
                        ],
                        className="shadow-md mb-3 animate__animated animate__zoomIn",
                        style={"borderRadius": "12px", "border": "none"}
                    ),
                    xs=12, md=12
                )
            ],
            className="mt-2"
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                html.H5("Gráfico de Massa", className="mb-0", style={
                                    "fontSize": "1.1rem", "fontWeight": "500", "fontFamily": "Arial, sans-serif"
                                }),
                                style={"background": "linear-gradient(90deg, #f8f9fa, #e9ecef)"}
                            ),
                            dbc.CardBody(
                                dcc.Loading(
                                    dcc.Graph(
                                        id="grafico-massa",
                                        config={"displayModeBar": False, "responsive": True},
                                        style={"minHeight": "40vh"}
                                    ),
                                    type="default"
                                ),
                                style={"padding": "0.8rem"}
                            )
                        ],
                        className="shadow-md mb-3 animate__animated animate__zoomIn",
                        style={"borderRadius": "12px", "border": "none"}
                    ),
                    xs=12, md=12
                )
            ],
            className="mt-2"
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                html.H5("Viagens por Hora Trabalhada (Último Dia)", className="mb-0", style={
                                    "fontSize": "1.1rem", "fontWeight": "500", "fontFamily": "Arial, sans-serif"
                                }),
                                style={"background": "linear-gradient(90deg, #f8f9fa, #e9ecef)"}
                            ),
                            dbc.CardBody(
                                dcc.Loading(
                                    dcc.Graph(
                                        id="grafico-viagens-hora",
                                        config={"displayModeBar": False, "responsive": True},
                                        style={"minHeight": "40vh"}
                                    ),
                                    type="default"
                                ),
                                style={"padding": "0.8rem"}
                            )
                        ],
                        className="shadow-md mb-3 animate__animated animate__zoomIn",
                        style={"borderRadius": "12px", "border": "none"}
                    ),
                    xs=12, md=12
                )
            ],
            className="mt-2"
        ),
        html.Hr(),
        dbc.Row(
            dbc.Col(
                [
                    html.Label(
                        "Filtrar por Modelo (Indicadores):",
                        className="fw-bold text-secondary",
                        style={"fontFamily": "Arial, sans-serif", "fontSize": "0.9rem"}
                    ),
                    dcc.Dropdown(
                        id="modelo-dropdown",
                        placeholder="(Opcional) Selecione um ou mais modelos (Equipamento)",
                        multi=True,
                        style={
                            "fontSize": "0.9rem",
                            "borderRadius": "8px",
                            "backgroundColor": "#f8f9fa",
                            "width": "100%"
                        }
                    )
                ],
                xs=12
            ),
            className="mt-2"
        ),
        html.Hr(),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                html.H5("Indicadores - Último Dia", className="mb-0 text-white", style={
                                    "fontSize": "1.1rem", "fontWeight": "500", "fontFamily": "Arial, sans-serif"
                                }),
                                style={"background": "linear-gradient(90deg, #343a40, #495057)"}
                            ),
                            dbc.CardBody(
                                dcc.Loading(
                                    DataTable(
                                        id="tabela-ind-ultimo",
                                        style_table={"overflowX": "auto", "width": "100%", "borderRadius": "8px"},
                                        style_header={
                                            "background": "linear-gradient(90deg, #343a40, #495057)",
                                            "fontWeight": "bold",
                                            "textAlign": "center",
                                            "color": "white",
                                            "fontFamily": "Arial, sans-serif",
                                            "fontSize": "0.9rem",
                                            "border": "1px solid #e9ecef"
                                        },
                                        style_cell={
                                            "textAlign": "center",
                                            "fontFamily": "Arial, sans-serif",
                                            "fontSize": "0.9rem",
                                            "padding": "8px",
                                            "border": "1px solid #e9ecef"
                                        }
                                    ),
                                    type="default"
                                ),
                                style={"padding": "0.8rem"}
                            )
                        ],
                        className="shadow-md mb-3 animate__animated animate__zoomIn",
                        style={"borderRadius": "12px", "border": "none"}
                    ),
                    xs=12, md=6
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                html.H5("Indicadores - Acumulado", className="mb-0 text-white", style={
                                    "fontSize": "1.1rem", "fontWeight": "500", "fontFamily": "Arial, sans-serif"
                                }),
                                style={"background": "linear-gradient(90deg, #343a40, #495057)"}
                            ),
                            dbc.CardBody(
                                dcc.Loading(
                                    DataTable(
                                        id="tabela-ind-acum",
                                        style_table={"overflowX": "auto", "width": "100%", "borderRadius": "8px"},
                                        style_header={
                                            "background": "linear-gradient(90deg, #343a40, #495057)",
                                            "fontWeight": "bold",
                                            "textAlign": "center",
                                            "color": "white",
                                            "fontFamily": "Arial, sans-serif",
                                            "fontSize": "0.9rem",
                                            "border": "1px solid #e9ecef"
                                        },
                                        style_cell={
                                            "textAlign": "center",
                                            "fontFamily": "Arial, sans-serif",
                                            "fontSize": "0.9rem",
                                            "padding": "8px",
                                            "border": "1px solid #e9ecef"
                                        }
                                    ),
                                    type="default"
                                ),
                                style={"padding": "0.8rem"}
                            )
                        ],
                        className="shadow-md mb-3 animate__animated animate__zoomIn",
                        style={"borderRadius": "12px", "border": "none"}
                    ),
                    xs=12, md=6
                )
            ],
            className="mt-4"
        )
    ],
    fluid=True
)

# ==================== CALLBACKS ====================

@callback(
    [Output("data-store", "data"),
     Output("data-store-hora", "data"),
     Output("rel2-no-project-message", "style")],
    [Input("apply-button", "n_clicks"),
     Input("projeto-store", "data")],
    [State("date-picker-range", "start_date"),
     State("date-picker-range", "end_date")]
)
def apply_filter(n_clicks: int, projeto: str, start_date: str, end_date: str) -> Tuple[Any, Any, Dict]:
    if not projeto or projeto not in PROJECTS_CONFIG:
        return {}, {}, {"display": "block", "textAlign": "center", "color": "#343a40", "fontSize": "1.2rem", "margin": "20px 0"}
    if not start_date or not end_date:
        return {}, {}, {"display": "none"}

    start_date_obj = datetime.fromisoformat(start_date)
    end_date_obj = datetime.fromisoformat(end_date) + timedelta(days=1) - timedelta(seconds=1)
    start_date_str = start_date_obj.strftime("%d/%m/%Y")
    end_date_str = end_date_obj.strftime("%d/%m/%Y")

    query_prod = f"EXEC {PROJECTS_CONFIG[projeto]['database']}..usp_fato_producao '{start_date_str}', '{end_date_str}'"
    try:
        df_prod = cached_query(query_prod, projeto)
    except Exception as e:
        logger.error(f"Erro ao consultar Produção: {str(e)}")
        return {"error": f"Erro ao consultar Produção: {str(e)}"}, {}, {"display": "none"}

    needed_prod_cols = {"dt_registro_turno", "nome_operacao", "volume", "massa", "nome_equipamento_utilizado", "cod_viagem"}
    if df_prod.empty or not needed_prod_cols.issubset(df_prod.columns):
        return {"error": "Dados de produção inválidos ou colunas ausentes"}, {}, {"display": "none"}

    df_prod = convert_date_columns(df_prod, ["dt_registro_turno"])
    df_prod = filter_by_date(df_prod, "dt_registro_turno", start_date_obj, end_date_obj)
    df_prod = df_prod.dropna(subset=["nome_operacao"])
    df_prod = df_prod[list(needed_prod_cols)]
    df_prod["nome_operacao"] = df_prod["nome_operacao"].astype("category").cat.remove_unused_categories()

    data_prod_json = compress_json(df_prod) if not df_prod.empty else {}

    query_hora = f"EXEC {PROJECTS_CONFIG[projeto]['database']}..usp_fato_hora '{start_date_str}', '{end_date_str}'"
    try:
        df_h = cached_query(query_hora, projeto)
    except Exception as e:
        logger.error(f"Erro ao consultar Hora: {str(e)}")
        return data_prod_json, {"error": f"Erro ao consultar Hora: {str(e)}"}, {"display": "none"}

    needed_hora_cols = {"dt_registro_turno", "nome_modelo", "nome_tipo_estado", "tempo_hora", "nome_equipamento", "nome_tipo_equipamento"}
    if df_h.empty or not needed_hora_cols.issubset(df_h.columns):
        return data_prod_json, {"error": "Dados de horas inválidos ou colunas ausentes"}, {"display": "none"}

    df_h = convert_date_columns(df_h, ["dt_registro_turno"])
    df_h = df_h[list(needed_hora_cols)]
    for col in ["nome_modelo", "nome_tipo_estado", "nome_tipo_equipamento"]:
        if col in df_h.columns:
            df_h[col] = df_h[col].astype("category").cat.remove_unused_categories()

    data_hora_json = compress_json(df_h) if not df_h.empty else {}
    return data_prod_json, data_hora_json, {"display": "none"}

@callback(
    Output("operacao-dropdown", "options"),
    [Input("data-store", "data"),
     Input("projeto-store", "data")]
)
def update_operacoes_options(json_data: Union[str, dict], projeto: str) -> List[Dict[str, str]]:
    if not projeto or projeto not in PROJECTS_CONFIG:
        return []
    df = load_df(json_data)
    if df.empty or "nome_operacao" not in df.columns:
        return []
    ops_unicas = sorted(df["nome_operacao"].dropna().unique())
    return [{"label": op, "value": op} for op in ops_unicas]

@cache.memoize(timeout=300)
def _update_tables(json_data: str, operacoes_selecionadas: str, start_date: str, end_date: str, projeto: str):
    df = load_df(json_data)
    if df.empty or "dt_registro_turno" not in df.columns:
        return [], [], [], [], [], []

    df = convert_date_columns(df, ["dt_registro_turno"]).dropna(subset=["dt_registro_turno"])
    if operacoes_selecionadas:
        try:
            operacoes = json.loads(operacoes_selecionadas)
            if operacoes:
                df = df[df["nome_operacao"].isin(operacoes)]
                df["nome_operacao"] = df["nome_operacao"].astype("category").cat.remove_unused_categories()
        except json.JSONDecodeError:
            logger.warning("Erro ao decodificar operacoes_selecionadas, ignorando filtro")

    if df.empty:
        return [], [], [], [], [], []

    ultimo_dia = df["dt_registro_turno"].dt.date.max()
    df_last_day = df[df["dt_registro_turno"].dt.date == ultimo_dia]
    df_t1 = group_movimentacao(df_last_day, "nome_operacao")
    df_t1 = format_total_row(df_t1, "nome_operacao")
    df_t2 = group_movimentacao(df, "nome_operacao")
    df_t2 = format_total_row(df_t2, "nome_operacao")

    meta_total_last = META_MINERIO + META_ESTERIL
    style_cond_t1 = [
        {"if": {"filter_query": f'{{nome_operacao}} = "TOTAL" && {{volume}} >= {meta_total_last}', "column_id": "volume"}, "color": "rgb(0,55,158)"},
        {"if": {"filter_query": f'{{nome_operacao}} = "TOTAL" && {{volume}} < {meta_total_last}', "column_id": "volume"}, "color": "red"},
        {"if": {"filter_query": '{nome_operacao} = "TOTAL"'}, "backgroundColor": "#fff9c4", "fontWeight": "bold"}
    ]

    start_date_obj = datetime.fromisoformat(start_date)
    end_date_obj = datetime.fromisoformat(end_date)
    n_days = (end_date_obj - start_date_obj).days + 1
    meta_total_acc = n_days * (META_MINERIO + META_ESTERIL)
    style_cond_t2 = [
        {"if": {"filter_query": f'{{nome_operacao}} = "TOTAL" && {{volume}} >= {meta_total_acc}', "column_id": "volume"}, "color": "rgb(0,55,158)"},
        {"if": {"filter_query": f'{{nome_operacao}} = "TOTAL" && {{volume}} < {meta_total_acc}', "column_id": "volume"}, "color": "red"},
        {"if": {"filter_query": '{nome_operacao} = "TOTAL"'}, "backgroundColor": "#fff9c4", "fontWeight": "bold"}
    ]

    columns = [
        {"name": "Operação", "id": "nome_operacao", "type": "text"},
        {"name": "Viagens", "id": "viagens", "type": "numeric", "format": num_format},
        {"name": "Volume", "id": "volume", "type": "numeric", "format": num_format},
        {"name": "Massa", "id": "massa", "type": "numeric", "format": num_format}
    ]
    return df_t1.to_dict("records"), columns, style_cond_t1, df_t2.to_dict("records"), columns, style_cond_t2

@callback(
    [Output("tabela-1", "data"),
     Output("tabela-1", "columns"),
     Output("tabela-1", "style_data_conditional"),
     Output("tabela-2", "data"),
     Output("tabela-2", "columns"),
     Output("tabela-2", "style_data_conditional")],
    [Input("data-store", "data"),
     Input("operacao-dropdown", "value"),
     Input("projeto-store", "data")],
    [State("date-picker-range", "start_date"),
     State("date-picker-range", "end_date")]
)
def update_tables(json_data: Union[str, dict], operacoes_selecionadas: List[str], projeto: str, start_date: str, end_date: str):
    if not projeto or projeto not in PROJECTS_CONFIG:
        return [], [], [], [], [], []
    operacoes_str = json.dumps(operacoes_selecionadas, sort_keys=True)
    return _update_tables(json_data, operacoes_str, start_date, end_date, projeto)

@cache.memoize(timeout=300)
def _update_graphs(json_data: str, operacoes_selecionadas: str, projeto: str):
    df = load_df(json_data)
    if df.empty:
        fig_empty = px.bar(title="Selecione um período para ver o gráfico.", template="plotly_white")
        return fig_empty, fig_empty

    df = convert_date_columns(df, ["dt_registro_turno"]).dropna(subset=["dt_registro_turno"])
    if operacoes_selecionadas:
        try:
            operacoes = json.loads(operacoes_selecionadas)
            if operacoes:
                df = df[df["nome_operacao"].isin(operacoes)]
                df["nome_operacao"] = df["nome_operacao"].astype("category").cat.remove_unused_categories()
        except json.JSONDecodeError:
            logger.warning("Erro ao decodificar operacoes_selecionadas, ignorando filtro")
    if df.empty:
        fig_empty = px.bar(title="Sem dados para esse filtro.", template="plotly_white")
        return fig_empty, fig_empty

    df["dia"] = df["dt_registro_turno"].dt.date
    df_grouped = df.groupby("dia", as_index=False).agg(volume=("volume", "sum"), massa=("massa", "sum")).sort_values("dia")
    meta_total = META_MINERIO + META_ESTERIL
    df_grouped["bar_color"] = np.where(df_grouped["volume"] >= meta_total, "rgb(149,211,36)", "red")

    fig_volume = px.bar(
        df_grouped,
        x="dia",
        y="volume",
        title=f"Soma do Volume por Dia ({PROJECT_LABELS.get(projeto, 'Nenhuma obra selecionada')})",
        text="volume",
        template="plotly_white"
    )
    fig_volume.update_traces(
        textposition="outside",
        texttemplate="%{y:,.2f}",
        cliponaxis=False,
        marker_color=df_grouped["bar_color"],
        textfont=dict(family="Arial Black", size=16, color="black")
    )
    fig_volume.update_layout(
        xaxis_title="Dia",
        yaxis_title="Volume",
        title_x=0.5,
        margin=dict(l=40, r=40, t=60, b=40),
        yaxis_tickformat="0,0.00"
    )

    fig_massa = px.bar(
        df_grouped,
        x="dia",
        y="massa",
        title=f"Soma da Massa por Dia ({PROJECT_LABELS.get(projeto, 'Nenhuma obra selecionada')})",
        text="massa",
        template="plotly_white",
        color_discrete_sequence=["rgb(152,152,154)"]
    )
    fig_massa.update_traces(
        textposition="outside",
        texttemplate="%{y:,.2f}",
        cliponaxis=False,
        textfont=dict(family="Arial Black", size=16, color="black")
    )
    fig_massa.update_layout(
        xaxis_title="Dia",
        yaxis_title="Massa",
        title_x=0.5,
        margin=dict(l=40, r=40, t=60, b=40),
        yaxis_tickformat="0,0.00"
    )
    return fig_volume, fig_massa

@callback(
    [Output("grafico-volume", "figure"),
     Output("grafico-massa", "figure")],
    [Input("data-store", "data"),
     Input("operacao-dropdown", "value"),
     Input("projeto-store", "data")]
)
def update_graphs(json_data: Union[str, dict], operacoes_selecionadas: List[str], projeto: str):
    if not projeto or projeto not in PROJECTS_CONFIG:
        fig_empty = px.bar(title="Selecione uma obra para visualizar os dados.", template="plotly_white")
        return fig_empty, fig_empty
    operacoes_str = json.dumps(operacoes_selecionadas, sort_keys=True)
    return _update_graphs(json_data, operacoes_str, projeto)

@cache.memoize(timeout=300)
def _update_grafico_viagens_hora(json_prod: str, json_hora: str, end_date: str, operacoes_selecionadas: str, projeto: str):
    df_prod = load_df(json_prod)
    df_hora = load_df(json_hora)
    if df_prod.empty or df_hora.empty or not end_date:
        return px.bar(title="Selecione uma obra para visualizar os dados.", template="plotly_white")

    if isinstance(json_prod, dict) and "error" in json_prod:
        return px.bar(title=json_prod["error"], template="plotly_white")
    if isinstance(json_hora, dict) and "error" in json_hora:
        return px.bar(title=json_hora["error"], template="plotly_white")

    df_prod = convert_date_columns(df_prod, ["dt_registro_turno"]).dropna(subset=["dt_registro_turno"])
    df_hora = convert_date_columns(df_hora, ["dt_registro_turno"]).dropna(subset=["dt_registro_turno"])
    filtro_dia = datetime.fromisoformat(end_date).date()
    df_prod = df_prod[df_prod["dt_registro_turno"].dt.date == filtro_dia]
    df_hora = df_hora[df_hora["dt_registro_turno"].dt.date == filtro_dia]

    if operacoes_selecionadas:
        try:
            operacoes = json.loads(operacoes_selecionadas)
            if operacoes:
                df_prod = df_prod[df_prod["nome_operacao"].isin(operacoes)]
                df_prod["nome_operacao"] = df_prod["nome_operacao"].astype("category").cat.remove_unused_categories()
        except json.JSONDecodeError:
            logger.warning("Erro ao decodificar operacoes_selecionadas, ignorando filtro")
    if df_prod.empty or df_hora.empty:
        return px.bar(title="Sem dados para gerar o gráfico de Viagens por Hora Trabalhada.", template="plotly_white")

    df_viagens = df_prod.groupby("nome_equipamento_utilizado", as_index=False).agg(viagens=("cod_viagem", "count"))
    estados_trabalho = ["Operando", "Serviço Auxiliar", "Atraso Operacional"]
    df_hora_filtrada = df_hora[df_hora["nome_tipo_estado"].isin(estados_trabalho)]
    df_horas = df_hora_filtrada.groupby("nome_equipamento", as_index=False).agg(horas_trabalhadas=("tempo_hora", "sum"))
    df_merged = pd.merge(
        df_viagens, df_horas,
        left_on="nome_equipamento_utilizado",
        right_on="nome_equipamento",
        how="inner"
    )
    if df_merged.empty:
        return px.bar(title="Sem dados para gerar o gráfico de Viagens por Hora Trabalhada.", template="plotly_white")

    df_merged["viagens_por_hora"] = df_merged["viagens"] / df_merged["horas_trabalhadas"].replace(0, np.nan)
    df_merged["viagens_por_hora"] = df_merged["viagens_por_hora"].fillna(0)
    df_merged.sort_values("viagens_por_hora", inplace=True)
    fig = px.bar(
        df_merged,
        x="nome_equipamento_utilizado",
        y="viagens_por_hora",
        title=f"Viagens por Hora Trabalhada (Último Dia) ({PROJECT_LABELS.get(projeto, 'Nenhuma obra selecionada')})",
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
        margin=dict(l=40, r=40, t=60, b=40)
    )
    return fig

@callback(
    Output("grafico-viagens-hora", "figure"),
    [Input("data-store", "data"),
     Input("data-store-hora", "data"),
     Input("date-picker-range", "end_date"),
     Input("operacao-dropdown", "value"),
     Input("projeto-store", "data")]
)
def update_grafico_viagens_hora(json_prod: Union[str, dict], json_hora: Union[str, dict], end_date: str, operacoes_selecionadas: List[str], projeto: str):
    if not projeto or projeto not in PROJECTS_CONFIG:
        return px.bar(title="Selecione uma obra para visualizar os dados.", template="plotly_white")
    operacoes_str = json.dumps(operacoes_selecionadas, sort_keys=True)
    return _update_grafico_viagens_hora(json_prod, json_hora, end_date, operacoes_str, projeto)

@callback(
    Output("modelo-dropdown", "options"),
    [Input("data-store-hora", "data"),
     Input("projeto-store", "data")]
)
def load_modelos_options(json_data_hora: Union[str, dict], projeto: str) -> List[Dict[str, str]]:
    if not projeto or projeto not in PROJECTS_CONFIG:
        return []
    df_h = load_df(json_data_hora)
    if df_h.empty or "nome_modelo" not in df_h.columns:
        return []
    modelos_unicos = sorted(df_h["nome_modelo"].dropna().unique())
    return [{"label": m, "value": m} for m in modelos_unicos]

@cache.memoize(timeout=300)
def _update_tabelas_indicadores(json_data_hora: str, lista_modelos: str, end_date: str, projeto: str):
    df_h = load_df(json_data_hora)
    if df_h.empty:
        return [], [], [], [], [], []

    df_h = convert_date_columns(df_h, ["dt_registro_turno"])
    perfuracao_modelos = ["PERFURATRIZ HIDRAULICA SANDVIK DP1500I", "PERFURATRIZ HIDRAULICA SANDVIK DX800"]
    mask_perf = df_h["nome_modelo"].isin(perfuracao_modelos)
    if mask_perf.any():
        df_h["nome_tipo_equipamento"] = df_h["nome_tipo_equipamento"].cat.add_categories(["Perfuração"])
        df_h.loc[mask_perf, "nome_tipo_equipamento"] = "Perfuração"

    if lista_modelos:
        try:
            modelos = json.loads(lista_modelos)
            if modelos:
                df_h = df_h[df_h["nome_modelo"].isin(modelos)]
                df_h["nome_modelo"] = df_h["nome_modelo"].astype("category").cat.remove_unused_categories()
        except json.JSONDecodeError:
            logger.warning("Erro ao decodificar lista_modelos, ignorando filtro")
    if df_h.empty:
        return [], [], [], [], [], []

    df_h["tempo_hora"] = pd.to_numeric(df_h["tempo_hora"], errors="coerce").fillna(0)
    maintenance_states = ["Manutenção Preventiva", "Manutenção Corretiva", "Manutenção Operacional"]
    working_states = ["Operando", "Serviço Auxiliar", "Atraso Operacional"]

    df_h["horas_fora"] = df_h["tempo_hora"].where(df_h["nome_tipo_estado"] == "Fora de Frota", 0)
    df_h["horas_manut"] = df_h["tempo_hora"].where(df_h["nome_tipo_estado"].isin(maintenance_states), 0)
    df_h["horas_trab"] = df_h["tempo_hora"].where(df_h["nome_tipo_estado"].isin(working_states), 0)

    def calc_indicators(df_subset: pd.DataFrame) -> pd.DataFrame:
        if df_subset.empty:
            return pd.DataFrame(columns=["nome_tipo_equipamento", "disponibilidade", "utilizacao", "rendimento"])
        grp = df_subset.groupby("nome_tipo_equipamento").agg(
            total_totais=("tempo_hora", "sum"),
            total_fora=("horas_fora", "sum"),
            total_manut=("horas_manut", "sum"),
            total_trab=("horas_trab", "sum")
        ).reset_index()
        grp["horas_cal"] = grp["total_totais"] - grp["total_fora"]
        grp["horas_disp"] = grp["horas_cal"] - grp["total_manut"]
        grp["disponibilidade"] = (100 * grp["horas_disp"] / grp["horas_cal"]).where(grp["horas_cal"] > 0, 0)
        grp["utilizacao"] = (100 * grp["total_trab"] / grp["horas_disp"]).where(grp["horas_disp"] > 0, 0)
        grp["rendimento"] = grp["disponibilidade"] * grp["utilizacao"] / 100
        return grp[["nome_tipo_equipamento", "disponibilidade", "utilizacao", "rendimento"]]

    filtro_dia = datetime.fromisoformat(end_date).date() if end_date else None
    df_last = df_h[df_h["dt_registro_turno"].dt.date == filtro_dia] if filtro_dia else df_h.copy()
    grp_last = calc_indicators(df_last)
    if not grp_last.empty:
        tot = grp_last[["disponibilidade", "utilizacao", "rendimento"]].mean().to_dict()
        total_last = pd.DataFrame([{
            "nome_tipo_equipamento": "TOTAL",
            "disponibilidade": tot["disponibilidade"],
            "utilizacao": tot["utilizacao"],
            "rendimento": tot["rendimento"]
        }])
        df_ind_ultimo = pd.concat([grp_last, total_last], ignore_index=True)
    else:
        df_ind_ultimo = pd.DataFrame(columns=["nome_tipo_equipamento", "disponibilidade", "utilizacao", "rendimento"])

    grp_acum = calc_indicators(df_h)
    if not grp_acum.empty:
        tot_acum = grp_acum[["disponibilidade", "utilizacao", "rendimento"]].mean().to_dict()
        total_acum = pd.DataFrame([{
            "nome_tipo_equipamento": "TOTAL",
            "disponibilidade": tot_acum["disponibilidade"],
            "utilizacao": tot_acum["utilizacao"],
            "rendimento": tot_acum["rendimento"]
        }])
        df_ind_acum = pd.concat([grp_acum, total_acum], ignore_index=True)
    else:
        df_ind_acum = pd.DataFrame(columns=["nome_tipo_equipamento", "disponibilidade", "utilizacao", "rendimento"])

    columns_ind = [
        {"name": "Tipo Equipamento", "id": "nome_tipo_equipamento", "type": "text"},
        {"name": "Disponibilidade (%)", "id": "disponibilidade", "type": "numeric", "format": num_format},
        {"name": "Utilização (%)", "id": "utilizacao", "type": "numeric", "format": num_format},
        {"name": "Rendimento (%)", "id": "rendimento", "type": "numeric", "format": num_format}
    ]
    style_cond = [
        {"if": {"filter_query": "{disponibilidade} >= 80", "column_id": "disponibilidade"}, "color": "green"},
        {"if": {"filter_query": "{disponibilidade} < 80", "column_id": "disponibilidade"}, "color": "red"},
        {"if": {"filter_query": "{utilizacao} >= 75", "column_id": "utilizacao"}, "color": "green"},
        {"if": {"filter_query": "{utilizacao} < 75", "column_id": "utilizacao"}, "color": "red"},
        {"if": {"filter_query": "{rendimento} >= 60", "column_id": "rendimento"}, "color": "green"},
        {"if": {"filter_query": "{rendimento} < 60", "column_id": "rendimento"}, "color": "red"},
        {"if": {"filter_query": '{nome_tipo_equipamento} = "TOTAL"'}, "backgroundColor": "#fff9c4", "fontWeight": "bold"}
    ]
    return df_ind_ultimo.to_dict("records"), columns_ind, style_cond, df_ind_acum.to_dict("records"), columns_ind, style_cond

@callback(
    [Output("tabela-ind-ultimo", "data"),
     Output("tabela-ind-ultimo", "columns"),
     Output("tabela-ind-ultimo", "style_data_conditional"),
     Output("tabela-ind-acum", "data"),
     Output("tabela-ind-acum", "columns"),
     Output("tabela-ind-acum", "style_data_conditional")],
    [Input("data-store-hora", "data"),
     Input("modelo-dropdown", "value"),
     Input("projeto-store", "data")],
    [State("date-picker-range", "end_date")]
)
def update_tabelas_indicadores(json_data_hora: Union[str, dict], lista_modelos: List[str], projeto: str, end_date: str):
    if not projeto or projeto not in PROJECTS_CONFIG:
        return [], [], [], [], [], []
    modelos_str = json.dumps(lista_modelos, sort_keys=True)
    return _update_tabelas_indicadores(json_data_hora, modelos_str, end_date, projeto)
