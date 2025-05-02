import json
import gzip
from datetime import datetime, timedelta
from typing import Any, Dict, Tuple, List, Union

import dash
from dash import dcc, html, callback, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
from dash.dash_table import DataTable, FormatTemplate
import plotly.express as px
import pandas as pd
import numpy as np
from dash.dash_table.Format import Format, Scheme
import logging

# Import da função para consultar o banco, variáveis de meta e cache
from db import query_to_df
from config import META_MINERIO, META_ESTERIL
from app import cache  # Assumindo que cache está definido em app.py

# Configuração do log
logging.basicConfig(
    level=logging.DEBUG,
    filename="dashboard.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Formato numérico com 2 casas decimais e separador de milhar
num_format = Format(precision=2, scheme=Scheme.fixed, group=True)

# ==================== FUNÇÕES AUXILIARES ====================

@cache.memoize(timeout=300)
def cached_query(query: str) -> pd.DataFrame:
    """Consulta o banco com cache de 300 segundos."""
    return query_to_df(query)

def convert_date_columns(df: pd.DataFrame, date_cols: List[str]) -> pd.DataFrame:
    """Converte colunas de data para datetime, apenas se necessário."""
    for col in date_cols:
        if col in df.columns and not df[col].dtype == "datetime64[ns]":
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df

def filter_by_date(df: pd.DataFrame, date_col: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Filtra o DataFrame por intervalo de datas usando máscara booleana."""
    if date_col in df.columns:
        mask = (df[date_col].notna()) & (df[date_col] >= start_date) & (df[date_col] <= end_date)
        df = df.loc[mask]
    return df

def group_movimentacao(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Agrupa o DataFrame para movimentação, otimizando com categoria."""
    if df.empty or group_col not in df.columns:
        logger.debug(f"[DEBUG] DataFrame vazio ou sem {group_col} em group_movimentacao")
        return pd.DataFrame(columns=[group_col, "viagens", "volume", "massa"])

    # Garantir que nome_operacao seja categórica e limpar categorias não usadas
    df[group_col] = df[group_col].astype("category").cat.remove_unused_categories()
    
    # Agrupar e calcular métricas
    grouped = df.groupby(group_col, as_index=False).agg(
        viagens=(group_col, "size"),
        volume=("volume", "sum"),
        massa=("massa", "sum")
    )
    
    # Remover linhas com todas as métricas zeradas
    grouped = grouped[(grouped["viagens"] > 0) | (grouped["volume"] > 0) | (grouped["massa"] > 0)]
    logger.debug(f"[DEBUG] Após group_movimentacao por {group_col}: {len(grouped)} linhas")
    
    return grouped

def format_total_row(df_group: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Calcula a linha de total para os grupos."""
    total = pd.DataFrame({
        group_col: ["TOTAL"],
        "viagens": [df_group["viagens"].sum()],
        "volume": [df_group["volume"].sum()],
        "massa": [df_group["massa"].sum()]
    })
    return pd.concat([df_group, total], ignore_index=True)

@cache.memoize(timeout=300)
def load_df(json_data: Union[str, Dict]) -> pd.DataFrame:
    """Converte JSON comprimido para DataFrame, com cache."""
    if not json_data or (isinstance(json_data, dict) and "error" in json_data):
        logger.debug("[DEBUG] Nenhum dado válido em load_df")
        return pd.DataFrame()
    try:
        if isinstance(json_data, str):
            decompressed = gzip.decompress(bytes.fromhex(json_data)).decode("utf-8")
            df = pd.read_json(decompressed, orient="records")
        else:
            df = pd.DataFrame(json_data)
        # Converter colunas categóricas imediatamente
        for col in ["nome_operacao", "nome_modelo", "nome_tipo_equipamento"]:
            if col in df.columns:
                df[col] = df[col].astype("category").cat.remove_unused_categories()
        logger.debug(f"[DEBUG] DataFrame carregado em load_df: {len(df)} linhas, colunas: {df.columns.tolist()}")
        return df
    except Exception as e:
        logger.error(f"[DEBUG] Erro ao carregar DataFrame em load_df: {str(e)}")
        return pd.DataFrame()

def compress_json(df: pd.DataFrame) -> str:
    """Comprime DataFrame para JSON usando gzip."""
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
        dbc.Row(
            dbc.Col(
                html.H3(
                    "Informativo de Produção",
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
                                    "fontSize": "1.1rem",
                                    "fontWeight": "500",
                                    "fontFamily": "Arial, sans-serif"
                                }),
                                style={"background": "linear-gradient(90deg, #343a40, #495057)"}
                            ),
                            dbc.CardBody(
                                dcc.Loading(
                                    DataTable(
                                        id="tabela-1",
                                        columns=[
                                            {"name": "Operação", "id": "nome_operacao", "type": "text"},
                                            {"name": "Viagens", "id": "viagens", "type": "numeric", "format": num_format},
                                            {"name": "Volume", "id": "volume", "type": "numeric", "format": num_format},
                                            {"name": "Massa", "id": "massa", "type": "numeric", "format": num_format}
                                        ],
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
                                    "fontSize": "1.1rem",
                                    "fontWeight": "500",
                                    "fontFamily": "Arial, sans-serif"
                                }),
                                style={"background": "linear-gradient(90deg, #343a40, #495057)"}
                            ),
                            dbc.CardBody(
                                dcc.Loading(
                                    DataTable(
                                        id="tabela-2",
                                        columns=[
                                            {"name": "Operação", "id": "nome_operacao", "type": "text"},
                                            {"name": "Viagens", "id": "viagens", "type": "numeric", "format": num_format},
                                            {"name": "Volume", "id": "volume", "type": "numeric", "format": num_format},
                                            {"name": "Massa", "id": "massa", "type": "numeric", "format": num_format}
                                        ],
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
                                    "fontSize": "1.1rem",
                                    "fontWeight": "500",
                                    "fontFamily": "Arial, sans-serif"
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
                                    "fontSize": "1.1rem",
                                    "fontWeight": "500",
                                    "fontFamily": "Arial, sans-serif"
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
                                    "fontSize": "1.1rem",
                                    "fontWeight": "500",
                                    "fontFamily": "Arial, sans-serif"
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
                                    "fontSize": "1.1rem",
                                    "fontWeight": "500",
                                    "fontFamily": "Arial, sans-serif"
                                }),
                                style={"background": "linear-gradient(90deg, #343a40, #495057)"}
                            ),
                            dbc.CardBody(
                                dcc.Loading(
                                    DataTable(
                                        id="tabela-ind-ultimo",
                                        columns=[
                                            {"name": "Tipo Equipamento", "id": "nome_tipo_equipamento", "type": "text"},
                                            {"name": "Disponibilidade (%)", "id": "disponibilidade", "type": "numeric", "format": num_format},
                                            {"name": "Utilização (%)", "id": "utilizacao", "type": "numeric", "format": num_format},
                                            {"name": "Rendimento (%)", "id": "rendimento", "type": "numeric", "format": num_format}
                                        ],
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
                                    "fontSize": "1.1rem",
                                    "fontWeight": "500",
                                    "fontFamily": "Arial, sans-serif"
                                }),
                                style={"background": "linear-gradient(90deg, #343a40, #495057)"}
                            ),
                            dbc.CardBody(
                                dcc.Loading(
                                    DataTable(
                                        id="tabela-ind-acum",
                                        columns=[
                                            {"name": "Tipo Equipamento", "id": "nome_tipo_equipamento", "type": "text"},
                                            {"name": "Disponibilidade (%)", "id": "disponibilidade", "type": "numeric", "format": num_format},
                                            {"name": "Utilização (%)", "id": "utilizacao", "type": "numeric", "format": num_format},
                                            {"name": "Rendimento (%)", "id": "rendimento", "type": "numeric", "format": num_format}
                                        ],
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
    Output("data-store", "data"),
    Output("data-store-hora", "data"),
    Input("apply-button", "n_clicks"),
    State("date-picker-range", "start_date"),
    State("date-picker-range", "end_date"),
    prevent_initial_call=True
)
def apply_filter(n_clicks: int, start_date: str, end_date: str) -> Tuple[Any, Any]:
    """Consulta os dados e armazena em JSON comprimido."""
    if not start_date or not end_date:
        logger.debug("[DEBUG] Data inicial ou final não fornecida em apply_filter")
        return {}, {}

    start_date_obj = datetime.fromisoformat(start_date)
    end_date_obj = datetime.fromisoformat(end_date)
    start_date_str = start_date_obj.strftime("%d/%m/%Y")
    end_date_str = end_date_obj.strftime("%d/%m/%Y")

    query_prod = f"""
        EXEC dw_sdp_mt_fas..usp_fato_producao
        '{start_date_str}',
        '{end_date_str}'
    """
    try:
        df_prod = cached_query(query_prod)
        logger.debug(f"[DEBUG] Dados de produção retornados: {len(df_prod)} linhas")
    except Exception as e:
        logger.error(f"[DEBUG] Erro ao consultar Produção: {str(e)}")
        return {"error": f"Erro ao consultar Produção: {str(e)}"}, {}

    needed_prod_cols = {"dt_registro_turno", "nome_operacao", "volume", "massa", "nome_equipamento_utilizado"}
    if not df_prod.empty and needed_prod_cols.issubset(df_prod.columns):
        df_prod = convert_date_columns(df_prod, ["dt_registro_turno"])
        df_prod = filter_by_date(df_prod, "dt_registro_turno", start_date_obj, end_date_obj)
        if "nome_operacao" in df_prod.columns:
            df_prod = df_prod.dropna(subset=["nome_operacao"])
        df_prod = df_prod[list(needed_prod_cols)]  # Selecionar apenas colunas necessárias
        df_prod["nome_operacao"] = df_prod["nome_operacao"].astype("category").cat.remove_unused_categories()
        logger.debug(f"[DEBUG] Dados de produção após filtro: {len(df_prod)} linhas")
    else:
        logger.debug("[DEBUG] Dados de produção inválidos ou colunas ausentes")
        return {"error": "Dados de produção inválidos ou colunas ausentes"}, {}

    data_prod_json = compress_json(df_prod) if not df_prod.empty else {}

    query_hora = f"EXEC dw_sdp_mt_fas..usp_fato_hora '{start_date_str}', '{end_date_str}'"
    try:
        df_h = cached_query(query_hora)
        logger.debug(f"[DEBUG] Dados de hora retornados: {len(df_h)} linhas")
    except Exception as e:
        logger.error(f"[DEBUG] Erro ao consultar Hora: {str(e)}")
        return data_prod_json, {"error": f"Erro ao consultar Hora: {str(e)}"}

    needed_hora_cols = {"dt_registro_turno", "nome_modelo", "nome_tipo_estado", "tempo_hora", "nome_equipamento", "nome_tipo_equipamento"}
    if not df_h.empty and needed_hora_cols.issubset(df_h.columns):
        df_h = convert_date_columns(df_h, ["dt_registro_turno"])
        df_h = df_h[list(needed_hora_cols)]  # Selecionar apenas colunas necessárias
        for col in ["nome_modelo", "nome_tipo_estado", "nome_tipo_equipamento"]:
            if col in df_h.columns:
                df_h[col] = df_h[col].astype("category").cat.remove_unused_categories()
        logger.debug(f"[DEBUG] Dados de hora após processamento: {len(df_h)} linhas")
    else:
        logger.debug("[DEBUG] Dados de horas inválidos ou colunas ausentes")
        return data_prod_json, {"error": "Dados de horas inválidos ou colunas ausentes"}

    data_hora_json = compress_json(df_h) if not df_h.empty else {}
    return data_prod_json, data_hora_json

@callback(
    Output("operacao-dropdown", "options"),
    Input("data-store", "data")
)
def update_operacoes_options(json_data: Union[str, dict]) -> List[Dict[str, str]]:
    df = load_df(json_data)
    if df.empty or "nome_operacao" not in df.columns:
        logger.debug("[DEBUG] Nenhum dado ou nome_operacao ausente em update_operacoes_options")
        return []
    ops_unicas = sorted(df["nome_operacao"].dropna().unique())
    logger.debug(f"[DEBUG] Operações únicas para dropdown: {ops_unicas}")
    return [{"label": op, "value": op} for op in ops_unicas]

@cache.memoize(timeout=300)
def _update_tables(json_data: str, operacoes_selecionadas: str, start_date: str, end_date: str):
    """Função auxiliar cacheada para update_tables."""
    df = load_df(json_data)
    if df.empty or "dt_registro_turno" not in df.columns:
        logger.debug("[DEBUG] DataFrame vazio ou sem dt_registro_turno em update_tables")
        return [], [], [], [], [], []

    # Log inicial
    logger.debug(f"[DEBUG] Dados brutos carregados: {len(df)} linhas, operações únicas: {sorted(df['nome_operacao'].unique())}")

    # Converter colunas de data e remover linhas com dt_registro_turno nulo
    df = convert_date_columns(df, ["dt_registro_turno"]).dropna(subset=["dt_registro_turno"])
    
    # Aplicar filtro de operações selecionadas
    if operacoes_selecionadas and isinstance(operacoes_selecionadas, str):
        try:
            operacoes = json.loads(operacoes_selecionadas)
            if operacoes:  # Verifica se a lista não está vazia
                df = df.loc[df["nome_operacao"].isin(operacoes)]
                df["nome_operacao"] = df["nome_operacao"].astype("category").cat.remove_unused_categories()
                logger.debug(f"[DEBUG] Após filtro de operações {operacoes}: {len(df)} linhas, operações: {sorted(df['nome_operacao'].unique())}")
        except json.JSONDecodeError:
            logger.warning("[DEBUG] Erro ao decodificar operacoes_selecionadas, ignorando filtro")
    
    if df.empty:
        logger.debug("[DEBUG] DataFrame vazio após filtro")
        return [], [], [], [], [], []

    # Filtrar pelo último dia
    ultimo_dia = df["dt_registro_turno"].dt.date.max()
    df_last_day = df.loc[df["dt_registro_turno"].dt.date == ultimo_dia]
    logger.debug(f"[DEBUG] Dados do último dia: {len(df_last_day)} linhas")

    # Agrupar dados do último dia
    df_t1 = group_movimentacao(df_last_day, "nome_operacao")
    df_t1 = format_total_row(df_t1, "nome_operacao")
    logger.debug(f"[DEBUG] Tabela 1 (Último Dia): {df_t1.to_dict('records')}")

    # Agrupar dados acumulados
    df_t2 = group_movimentacao(df, "nome_operacao")
    df_t2 = format_total_row(df_t2, "nome_operacao")
    logger.debug(f"[DEBUG] Tabela 2 (Acumulada): {df_t2.to_dict('records')}")

    # Definir estilos condicionais
    meta_total_last = META_MINERIO + META_ESTERIL
    style_cond_t1 = [
        {
            "if": {"filter_query": f'{{CryptographicError: Invalid initialization vector. Must be 16 bytesnome_operacao}} = "TOTAL" && {{volume}} >= {meta_total_last}', "column_id": "volume"},
            "color": "rgb(0,55,158)"
        },
        {
            "if": {"filter_query": f'{{nome_operacao}} = "TOTAL" && {{volume}} < {meta_total_last}', "column_id": "volume"},
            "color": "red"
        },
        {
            "if": {"filter_query": '{nome_operacao} = "TOTAL"'},
            "backgroundColor": "#fff9c4",
            "fontWeight": "bold"
        }
    ]

    start_date_obj = datetime.fromisoformat(start_date)
    end_date_obj = datetime.fromisoformat(end_date)
    n_days = (end_date_obj - start_date_obj).days + 1
    meta_total_acc = n_days * (META_MINERIO + META_ESTERIL)
    style_cond_t2 = [
        {
            "if": {"filter_query": f'{{nome_operacao}} = "TOTAL" && {{volume}} >= {meta_total_acc}', "column_id": "volume"},
            "color": "rgb(0,55,158)"
        },
        {
            "if": {"filter_query": f'{{nome_operacao}} = "TOTAL" && {{volume}} < {meta_total_acc}', "column_id": "volume"},
            "color": "red"
        },
        {
            "if": {"filter_query": '{nome_operacao} = "TOTAL"'},
            "backgroundColor": "#fff9c4",
            "fontWeight": "bold"
        }
    ]

    columns = [
        {"name": "Operação", "id": "nome_operacao"},
        {"name": "Viagens", "id": "viagens"},
        {"name": "Volume", "id": "volume", "type": "numeric", "format": num_format},
        {"name": "Massa", "id": "massa", "type": "numeric", "format": num_format}
    ]
    data_t1 = df_t1.to_dict("records")
    data_t2 = df_t2.to_dict("records")
    return data_t1, columns, style_cond_t1, data_t2, columns, style_cond_t2

@callback(
    Output("tabela-1", "data"),
    Output("tabela-1", "columns"),
    Output("tabela-1", "style_data_conditional"),
    Output("tabela-2", "data"),
    Output("tabela-2", "columns"),
    Output("tabela-2", "style_data_conditional"),
    Input("data-store", "data"),
    Input("operacao-dropdown", "value"),
    State("date-picker-range", "start_date"),
    State("date-picker-range", "end_date")
)
def update_tables(json_data: Union[str, dict], operacoes_selecionadas: List[str],
                  start_date: str, end_date: str):
    """Atualiza tabelas com controle de contexto."""
    ctx = callback_context
    if not ctx.triggered:
        logger.debug("[DEBUG] Nenhum callback disparado em update_tables")
        return [], [], [], [], [], []

    # Converter operacoes_selecionadas para string para cache
    operacoes_str = json.dumps(operacoes_selecionadas, sort_keys=True)
    return _update_tables(json_data, operacoes_str, start_date, end_date)

@cache.memoize(timeout=300)
def _update_graphs(json_data: str, operacoes_selecionadas: str):
    """Função auxiliar cacheada para update_graphs."""
    df = load_df(json_data)
    if df.empty:
        logger.debug("[DEBUG] DataFrame vazio em _update_graphs")
        fig_empty = px.bar(title="Selecione um período para ver o gráfico.", template="plotly_white")
        return fig_empty, fig_empty

    df = convert_date_columns(df, ["dt_registro_turno"]).dropna(subset=["dt_registro_turno"])
    if operacoes_selecionadas and isinstance(operacoes_selecionadas, str):
        try:
            operacoes = json.loads(operacoes_selecionadas)
            if operacoes:  # Verifica se a lista não está vazia
                df = df.loc[df["nome_operacao"].isin(operacoes)]
                df["nome_operacao"] = df["nome_operacao"].astype("category").cat.remove_unused_categories()
                logger.debug(f"[DEBUG] Dados filtrados para gráficos: {len(df)} linhas, operações: {sorted(df['nome_operacao'].unique())}")
        except json.JSONDecodeError:
            logger.warning("[DEBUG] Erro ao decodificar operacoes_selecionadas em _update_graphs, ignorando filtro")
    if df.empty:
        logger.debug("[DEBUG] DataFrame vazio após filtro em _update_graphs")
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
        title="Soma do Volume por Dia",
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
        margin=dict(l=40, r=40, t=60, b=40)
    )
    fig_volume.update_yaxes(tickformat="0,0.00")

    fig_massa = px.bar(
        df_grouped,
        x="dia",
        y="massa",
        title="Soma da Massa por Dia",
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
        margin=dict(l=40, r=40, t=60, b=40)
    )
    fig_massa.update_yaxes(tickformat="0,0.00")
    return fig_volume, fig_massa

@callback(
    Output("grafico-volume", "figure"),
    Output("grafico-massa", "figure"),
    Input("data-store", "data"),
    Input("operacao-dropdown", "value")
)
def update_graphs(json_data: Union[str, dict], operacoes_selecionadas: List[str]):
    """Atualiza gráficos com controle de contexto."""
    ctx = callback_context
    if not ctx.triggered:
        logger.debug("[DEBUG] Nenhum callback disparado em update_graphs")
        fig_empty = px.bar(title="Selecione um período para ver o gráfico.", template="plotly_white")
        return fig_empty, fig_empty

    operacoes_str = json.dumps(operacoes_selecionadas, sort_keys=True)
    return _update_graphs(json_data, operacoes_str)

@cache.memoize(timeout=300)
def _update_grafico_viagens_hora(json_prod: str, json_hora: str, end_date: str, operacoes_selecionadas: str):
    """Função auxiliar cacheada para update_grafico_viagens_hora."""
    df_prod = load_df(json_prod)
    df_hora = load_df(json_hora)
    if df_prod.empty or df_hora.empty or not end_date:
        logger.debug("[DEBUG] Dados vazios ou end_date ausente em _update_grafico_viagens_hora")
        return px.bar(title="Sem dados para gerar o gráfico de Viagens por Hora Trabalhada.", template="plotly_white")

    if isinstance(json_prod, dict) and "error" in json_prod:
        logger.debug(f"[DEBUG] Erro em json_prod: {json_prod['error']}")
        return px.bar(title=json_prod["error"], template="plotly_white")
    if isinstance(json_hora, dict) and "error" in json_hora:
        logger.debug(f"[DEBUG] Erro em json_hora: {json_hora['error']}")
        return px.bar(title=json_hora["error"], template="plotly_white")

    try:
        df_prod = convert_date_columns(df_prod, ["dt_registro_turno"]).dropna(subset=["dt_registro_turno"])
        df_hora = convert_date_columns(df_hora, ["dt_registro_turno"]).dropna(subset=["dt_registro_turno"])
    except Exception as e:
        logger.error(f"[DEBUG] Erro ao carregar dados em _update_grafico_viagens_hora: {str(e)}")
        return px.bar(title=f"Erro ao carregar dados: {str(e)}", template="plotly_white")

    filtro_dia = datetime.fromisoformat(end_date).date()
    df_prod = df_prod.loc[df_prod["dt_registro_turno"].dt.date == filtro_dia]
    df_hora = df_hora.loc[df_hora["dt_registro_turno"].dt.date == filtro_dia]

    if operacoes_selecionadas and isinstance(operacoes_selecionadas, str):
        try:
            operacoes = json.loads(operacoes_selecionadas)
            if operacoes:  # Verifica se a lista não está vazia
                df_prod = df_prod.loc[df_prod["nome_operacao"].isin(operacoes)]
                df_prod["nome_operacao"] = df_prod["nome_operacao"].astype("category").cat.remove_unused_categories()
                logger.debug(f"[DEBUG] Dados filtrados para viagens/hora: {len(df_prod)} linhas")
        except json.JSONDecodeError:
            logger.warning("[DEBUG] Erro ao decodificar operacoes_selecionadas em _update_grafico_viagens_hora, ignorando filtro")
    if df_prod.empty or df_hora.empty:
        logger.debug("[DEBUG] DataFrame vazio após filtro em _update_grafico_viagens_hora")
        return px.bar(title="Sem dados para gerar o gráfico de Viagens por Hora Trabalhada.", template="plotly_white")

    df_viagens = df_prod.groupby("nome_equipamento_utilizado", as_index=False).agg(
        viagens=("nome_operacao", "count")
    )
    estados_trabalho = ["Operando", "Serviço Auxiliar", "Atraso Operacional"]
    df_hora_filtrada = df_hora.loc[df_hora["nome_tipo_estado"].isin(estados_trabalho)]
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
        logger.debug("[DEBUG] Nenhum dado após merge em _update_grafico_viagens_hora")
        return px.bar(title="Sem dados para gerar o gráfico de Viagens por Hora Trabalhada.", template="plotly_white")

    df_merged["horas_trabalhadas"] = df_merged["horas_trabalhadas"].replace(0, np.nan)
    df_merged["viagens_por_hora"] = (df_merged["viagens"] / df_merged["horas_trabalhadas"]).fillna(0)
    df_merged.sort_values("viagens_por_hora", inplace=True)
    fig = px.bar(
        df_merged,
        x="nome_equipamento_utilizado",
        y="viagens_por_hora",
        title="Viagens por Hora Trabalhada (Último Dia)",
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
    Input("data-store", "data"),
    Input("data-store-hora", "data"),
    Input("date-picker-range", "end_date"),
    Input("operacao-dropdown", "value")
)
def update_grafico_viagens_hora(json_prod: Union[str, dict], json_hora: Union[str, dict],
                                end_date: str, operacoes_selecionadas: List[str]):
    """Atualiza gráfico de viagens por hora com controle de contexto."""
    ctx = callback_context
    if not ctx.triggered:
        logger.debug("[DEBUG] Nenhum callback disparado em update_grafico_viagens_hora")
        return px.bar(title="Sem dados para gerar o gráfico de Viagens por Hora Trabalhada.", template="plotly_white")

    operacoes_str = json.dumps(operacoes_selecionadas, sort_keys=True)
    return _update_grafico_viagens_hora(json_prod, json_hora, end_date, operacoes_str)

@callback(
    Output("modelo-dropdown", "options"),
    Input("data-store-hora", "data")
)
def load_modelos_options(json_data_hora: Union[str, dict]) -> List[Dict[str, str]]:
    df_h = load_df(json_data_hora)
    if df_h.empty or "nome_modelo" not in df_h.columns:
        logger.debug("[DEBUG] Nenhum dado ou nome_modelo ausente em load_modelos_options")
        return []
    modelos_unicos = sorted(df_h["nome_modelo"].dropna().unique())
    logger.debug(f"[DEBUG] Modelos únicos para dropdown: {modelos_unicos}")
    return [{"label": m, "value": m} for m in modelos_unicos]

@cache.memoize(timeout=300)
def _update_tabelas_indicadores(json_data_hora: str, lista_modelos: str, end_date: str):
    """Função auxiliar cacheada para update_tabelas_indicadores."""
    df_h = load_df(json_data_hora)
    if df_h.empty:
        logger.debug("[DEBUG] DataFrame vazio em _update_tabelas_indicadores")
        return [], [], [], [], [], []

    df_h = convert_date_columns(df_h, ["dt_registro_turno"])
    
    # Ajuste para modelos específicos de perfuração
    perfuracao_modelos = ["PERFURATRIZ HIDRAULICA SANDVIK DP1500I", "PERFURATRIZ HIDRAULICA SANDVIK DX800"]
    mask_perf = df_h["nome_modelo"].isin(perfuracao_modelos)
    if mask_perf.any():
        # Adicionar "Perfuração" às categorias antes da atribuição
        df_h["nome_tipo_equipamento"] = df_h["nome_tipo_equipamento"].cat.add_categories(["Perfuração"])
        df_h.loc[mask_perf, "nome_tipo_equipamento"] = "Perfuração"
    
    if lista_modelos and isinstance(lista_modelos, str):
        try:
            modelos = json.loads(lista_modelos)
            if modelos:  # Verifica se a lista não está vazia
                df_h = df_h.loc[df_h["nome_modelo"].isin(modelos)]
                df_h["nome_modelo"] = df_h["nome_modelo"].astype("category").cat.remove_unused_categories()
                logger.debug(f"[DEBUG] Dados filtrados por modelos em _update_tabelas_indicadores: {len(df_h)} linhas")
        except json.JSONDecodeError:
            logger.warning("[DEBUG] Erro ao decodificar lista_modelos em _update_tabelas_indicadores, ignorando filtro")
    if df_h.empty:
        logger.debug("[DEBUG] DataFrame vazio após filtro por modelos em _update_tabelas_indicadores")
        return [], [], [], [], [], []

    df_h["tempo_hora"] = pd.to_numeric(df_h["tempo_hora"], errors="coerce").fillna(0)

    maintenance_states = ["Manutenção Preventiva", "Manutenção Corretiva", "Manutenção Operacional"]
    working_states = ["Operando", "Serviço Auxiliar", "Atraso Operacional"]

    df_h["horas_totais"] = df_h["tempo_hora"]
    df_h["horas_fora"] = np.where(df_h["nome_tipo_estado"] == "Fora de Frota", df_h["tempo_hora"], 0)
    df_h["horas_manut"] = np.where(df_h["nome_tipo_estado"].isin(maintenance_states), df_h["tempo_hora"], 0)
    df_h["horas_trab"] = np.where(df_h["nome_tipo_estado"].isin(working_states), df_h["tempo_hora"], 0)

    def calc_indicators(df_subset: pd.DataFrame) -> pd.DataFrame:
        grp = df_subset.groupby("nome_tipo_equipamento").agg(
            total_totais=('horas_totais', 'sum'),
            total_fora=('horas_fora', 'sum'),
            total_manut=('horas_manut', 'sum'),
            total_trab=('horas_trab', 'sum')
        ).reset_index()
        grp["horas_cal"] = grp["total_totais"] - grp["total_fora"]
        grp["horas_disp"] = grp["horas_cal"] - grp["total_manut"]
        grp["disponibilidade"] = np.where(grp["horas_cal"] > 0, 100 * grp["horas_disp"] / grp["horas_cal"], 0)
        grp["utilizacao"] = np.where(grp["horas_disp"] > 0, 100 * grp["total_trab"] / grp["horas_disp"], 0)
        grp["rendimento"] = grp["disponibilidade"] * grp["utilizacao"] / 100
        return grp[["nome_tipo_equipamento", "disponibilidade", "utilizacao", "rendimento"]]

    if end_date:
        filtro_dia = datetime.fromisoformat(end_date).date()
        df_last = df_h.loc[df_h["dt_registro_turno"].dt.date == filtro_dia]
    else:
        df_last = df_h.copy()
        
    grp_last = calc_indicators(df_last)
    if not df_last.empty:
        tot = grp_last.agg({
            "disponibilidade": "mean",
            "utilizacao": "mean",
            "rendimento": "mean"
        }).to_dict()
        total_last = pd.DataFrame([{
            "nome_tipo_equipamento": "TOTAL",
            "disponibilidade": tot["disponibilidade"],
            "utilizacao": tot["utilizacao"],
            "rendimento": tot["rendimento"]
        }])
        df_ind_ultimo = pd.concat([grp_last, total_last], ignore_index=True)
    else:
        df_ind_ultimo = pd.DataFrame()

    grp_acum = calc_indicators(df_h)
    if not df_h.empty:
        tot_acum = grp_acum.agg({
            "disponibilidade": "mean",
            "utilizacao": "mean",
            "rendimento": "mean"
        }).to_dict()
        total_acum = pd.DataFrame([{
            "nome_tipo_equipamento": "TOTAL",
            "disponibilidade": tot_acum["disponibilidade"],
            "utilizacao": tot_acum["utilizacao"],
            "rendimento": tot_acum["rendimento"]
        }])
        df_ind_acum = pd.concat([grp_acum, total_acum], ignore_index=True)
    else:
        df_ind_acum = pd.DataFrame()

    data_t1 = df_ind_ultimo.to_dict("records")
    data_t2 = df_ind_acum.to_dict("records")
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
    return data_t1, columns_ind, style_cond, data_t2, columns_ind, style_cond

@callback(
    Output("tabela-ind-ultimo", "data"),
    Output("tabela-ind-ultimo", "columns"),
    Output("tabela-ind-ultimo", "style_data_conditional"),
    Output("tabela-ind-acum", "data"),
    Output("tabela-ind-acum", "columns"),
    Output("tabela-ind-acum", "style_data_conditional"),
    Input("data-store-hora", "data"),
    Input("modelo-dropdown", "value"),
    State("date-picker-range", "end_date")
)
def update_tabelas_indicadores(json_data_hora: Union[str, dict], lista_modelos: List[str], end_date: str):
    """Atualiza tabelas de indicadores com controle de contexto."""
    ctx = callback_context
    if not ctx.triggered:
        logger.debug("[DEBUG] Nenhum callback disparado em update_tabelas_indicadores")
        return [], [], [], [], [], []

    modelos_str = json.dumps(lista_modelos, sort_keys=True)
    return _update_tabelas_indicadores(json_data_hora, modelos_str, end_date)
