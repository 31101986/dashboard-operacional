import json
from datetime import datetime, timedelta
from typing import Any, Dict, Tuple, List, Union

import dash
from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc
from dash.dash_table import DataTable
from dash.dash_table.Format import Format, Scheme
import plotly.express as px
import pandas as pd
import numpy as np

# Import da função para consultar o banco e das variáveis de meta
from db import query_to_df
from config import META_MINERIO, META_ESTERIL

# Formato numérico com 2 casas decimais e separador de milhar
num_format = Format(precision=2, scheme=Scheme.fixed, group=True)

# ==================== FUNÇÕES AUXILIARES ====================

def convert_date_columns(df: pd.DataFrame, date_cols: List[str]) -> pd.DataFrame:
    """Converte as colunas de data do DataFrame para datetime, se necessário."""
    for col in date_cols:
        if col in df.columns and not np.issubdtype(df[col].dtype, np.datetime64):
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df

def filter_by_date(df: pd.DataFrame, date_col: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Filtra o DataFrame pela coluna de data entre start_date e end_date."""
    if date_col in df.columns:
        df = df.dropna(subset=[date_col])
        df = df.loc[(df[date_col] >= start_date) & (df[date_col] <= end_date)]
    return df

def group_movimentacao(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Agrupa o DataFrame para a tabela de movimentação (viagens, volume e massa)."""
    grouped = df.groupby(group_col, as_index=False).agg(
        viagens=(group_col, "size"),
        volume=("volume", "sum"),
        massa=("massa", "sum")
    )
    return grouped

def format_total_row(df_group: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Calcula a linha de total para os grupos e a concatena ao DataFrame."""
    total = pd.DataFrame({
        group_col: ["TOTAL"],
        "viagens": [df_group["viagens"].sum()],
        "volume": [df_group["volume"].sum()],
        "massa": [df_group["massa"].sum()]
    })
    return pd.concat([df_group, total], ignore_index=True)

def load_df(json_data: Union[str, Dict]) -> pd.DataFrame:
    """
    Converte a string JSON ou dicionário para DataFrame. 
    Se o dado for vazio ou contiver um erro, retorna um DataFrame vazio.
    """
    if not json_data or (isinstance(json_data, dict) and "error" in json_data):
        return pd.DataFrame()
    try:
        return pd.read_json(json_data, orient="records")
    except Exception:
        return pd.DataFrame()

# ==================== LAYOUT ====================

header = dbc.Row(
    [
        dbc.Col(
            html.H1(
                "Informativo de Produção",
                className="text-center my-4 text-primary",
                style={"fontFamily": "Arial, sans-serif", "fontSize": "28px"}
            ),
            xs=10
        ),
        dbc.Col(
            dbc.Button("Voltar ao Portal", href="/", color="secondary", className="mt-4"),
            xs=2,
            style={"textAlign": "right"}
        )
    ],
    align="center",
    className="mb-4"
)

layout = dbc.Container(
    [
        header,
        dbc.Row(
            dbc.Col(
                html.H5(
                    "Análise de Produção e Indicadores no Período Selecionado",
                    className="text-center text-muted",
                    style={"fontFamily": "Arial, sans-serif"}
                ),
                width=12
            ),
            className="mb-4"
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Label(
                            "Selecione o Período:",
                            className="fw-bold text-secondary",
                            style={"fontFamily": "Arial, sans-serif", "fontSize": "16px"}
                        ),
                        dcc.DatePickerRange(
                            id="date-picker-range-rel7",
                            min_date_allowed=datetime(2020, 1, 1),
                            max_date_allowed=datetime.today().date(),
                            start_date=(datetime.today() - timedelta(days=7)),
                            end_date=datetime.today().date(),
                            display_format="DD/MM/YYYY",
                            className="mb-2",
                            style={"width": "100%"}
                        ),
                        dbc.Button(
                            "Aplicar Filtro",
                            id="apply-button-rel7",
                            n_clicks=0,
                            className="btn btn-primary mt-2",
                            style={"fontFamily": "Arial, sans-serif", "fontSize": "16px", "width": "100%"}
                        )
                    ],
                    xs=12, md=4
                ),
                dbc.Col(
                    [
                        html.Label(
                            "Filtrar Operações (opcional):",
                            className="fw-bold text-secondary",
                            style={"fontFamily": "Arial, sans-serif", "fontSize": "16px"}
                        ),
                        dcc.Dropdown(
                            id="operacao-dropdown-rel7",
                            placeholder="Selecione uma ou mais operações",
                            multi=True,
                            className="mb-2",
                            style={"fontFamily": "Arial, sans-serif", "fontSize": "16px", "width": "100%"}
                        )
                    ],
                    xs=12, md=8
                )
            ],
            className="my-2"
        ),
        dcc.Store(id="data-store-rel7"),
        html.Hr(),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                html.H5("Movimentação (Último dia)", className="mb-0"),
                                className="bg-light",
                                style={"fontFamily": "Arial, sans-serif"}
                            ),
                            dbc.CardBody(
                                dcc.Loading(
                                    DataTable(
                                        id="tabela-1-rel7",
                                        columns=[
                                            {"name": "Operação", "id": "nome_operacao", "type": "text"},
                                            {"name": "Viagens", "id": "viagens", "type": "numeric", "format": num_format},
                                            {"name": "Volume", "id": "volume", "type": "numeric", "format": num_format},
                                            {"name": "Massa", "id": "massa", "type": "numeric", "format": num_format}
                                        ],
                                        style_table={"overflowX": "auto", "width": "100%"},
                                        style_header={
                                            "backgroundColor": "#f8f9fa",
                                            "fontWeight": "bold",
                                            "textAlign": "center"
                                        },
                                        style_cell={
                                            "textAlign": "center",
                                            "whiteSpace": "normal",
                                            "fontFamily": "Arial, sans-serif"
                                        }
                                    ),
                                    type="default"
                                )
                            )
                        ],
                        className="mb-4 shadow animate__animated animate__fadeInUp"
                    ),
                    xs=12, md=6
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                html.H5("Movimentação (Acumulado)", className="mb-0"),
                                className="bg-light",
                                style={"fontFamily": "Arial, sans-serif"}
                            ),
                            dbc.CardBody(
                                dcc.Loading(
                                    DataTable(
                                        id="tabela-2-rel7",
                                        columns=[
                                            {"name": "Operação", "id": "nome_operacao", "type": "text"},
                                            {"name": "Viagens", "id": "viagens", "type": "numeric", "format": num_format},
                                            {"name": "Volume", "id": "volume", "type": "numeric", "format": num_format},
                                            {"name": "Massa", "id": "massa", "type": "numeric", "format": num_format}
                                        ],
                                        style_table={"overflowX": "auto", "width": "100%"},
                                        style_header={
                                            "backgroundColor": "#f8f9fa",
                                            "fontWeight": "bold",
                                            "textAlign": "center"
                                        },
                                        style_cell={
                                            "textAlign": "center",
                                            "whiteSpace": "normal",
                                            "fontFamily": "Arial, sans-serif"
                                        }
                                    ),
                                    type="default"
                                )
                            )
                        ],
                        className="mb-4 shadow animate__animated animate__fadeInUp"
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
                                html.H5("Gráfico de Volume", className="mb-0"),
                                className="bg-light",
                                style={"fontFamily": "Arial, sans-serif"}
                            ),
                            dbc.CardBody(
                                dcc.Loading(
                                    dcc.Graph(
                                        id="grafico-volume-rel7",
                                        config={"displayModeBar": False, "responsive": True},
                                        style={"minHeight": "450px"}
                                    ),
                                    type="default"
                                )
                            )
                        ],
                        className="mb-4 shadow animate__animated animate__fadeInUp",
                        style={"marginBottom": "30px"}
                    ),
                    xs=12, md=12
                )
            ],
            className="mt-2"
        )
    ],
    fluid=True
)

# ==================== CALLBACKS ====================

@callback(
    Output("data-store-rel7", "data"),
    Input("apply-button-rel7", "n_clicks"),
    State("date-picker-range-rel7", "start_date"),
    State("date-picker-range-rel7", "end_date"),
    prevent_initial_call=True
)
def apply_filter(n_clicks: int, start_date: str, end_date: str) -> Any:
    """
    Consulta os dados de produção entre as datas selecionadas e armazena-os em JSON.
    """
    if not start_date or not end_date:
        return {}

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
        df_prod = query_to_df(query_prod)
    except Exception as e:
        return {"error": f"Erro ao consultar Produção: {str(e)}"}

    if not df_prod.empty and "dt_registro_turno" in df_prod.columns:
        df_prod = convert_date_columns(df_prod, ["dt_registro_turno"])
        df_prod = filter_by_date(df_prod, "dt_registro_turno", start_date_obj, end_date_obj)
        if "nome_operacao" in df_prod.columns:
            df_prod = df_prod.dropna(subset=["nome_operacao"])
    data_prod_json = df_prod.to_json(date_format="iso", orient="records") if not df_prod.empty else {}
    return data_prod_json

@callback(
    Output("operacao-dropdown-rel7", "options"),
    Input("data-store-rel7", "data")
)
def update_operacoes_options(json_data: Union[str, dict]) -> List[Dict[str, str]]:
    df = load_df(json_data)
    if df.empty:
        return []
    df["nome_operacao"] = df["nome_operacao"].astype("category")
    ops_unicas = sorted(df["nome_operacao"].dropna().unique())
    return [{"label": op, "value": op} for op in ops_unicas]

@callback(
    Output("tabela-1-rel7", "data"),
    Output("tabela-1-rel7", "columns"),
    Output("tabela-1-rel7", "style_data_conditional"),
    Output("tabela-2-rel7", "data"),
    Output("tabela-2-rel7", "columns"),
    Output("tabela-2-rel7", "style_data_conditional"),
    Input("data-store-rel7", "data"),
    Input("operacao-dropdown-rel7", "value"),
    State("date-picker-range-rel7", "start_date"),
    State("date-picker-range-rel7", "end_date")
)
def update_tables(json_data: Union[str, dict], operacoes_selecionadas: List[str],
                  start_date: str, end_date: str
                  ) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict], List[Dict], List[Dict]]:
    df = load_df(json_data)
    if df.empty or "dt_registro_turno" not in df.columns:
        return [], [], [], [], [], []

    df = convert_date_columns(df, ["dt_registro_turno"]).dropna(subset=["dt_registro_turno"])
    if operacoes_selecionadas:
        df = df.loc[df["nome_operacao"].isin(operacoes_selecionadas)]
    if df.empty:
        return [], [], [], [], [], []

    ultimo_dia = df["dt_registro_turno"].dt.date.max()
    df_last_day = df.loc[df["dt_registro_turno"].dt.date == ultimo_dia]
    df_t1 = group_movimentacao(df_last_day, "nome_operacao")
    df_t1 = format_total_row(df_t1, "nome_operacao")

    df_t2 = group_movimentacao(df, "nome_operacao")
    df_t2 = format_total_row(df_t2, "nome_operacao")

    meta_total_last = META_MINERIO + META_ESTERIL
    style_cond_t1 = [
        {
            "if": {"filter_query": f'{{nome_operacao}} = "TOTAL" && {{volume}} >= {meta_total_last}', "column_id": "volume"},
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
    Output("grafico-volume-rel7", "figure"),
    Input("data-store-rel7", "data"),
    Input("operacao-dropdown-rel7", "value")
)
def update_graph_volume(json_data: Union[str, dict], operacoes_selecionadas: List[str]):
    df = load_df(json_data)
    if df.empty:
        return px.bar(title="Selecione um período para ver o gráfico.", template="plotly_white")

    df = convert_date_columns(df, ["dt_registro_turno"]).dropna(subset=["dt_registro_turno"])
    if operacoes_selecionadas:
        df = df.loc[df["nome_operacao"].isin(operacoes_selecionadas)]
    if df.empty:
        return px.bar(title="Sem dados para esse filtro.", template="plotly_white")

    df["dia"] = df["dt_registro_turno"].dt.date
    df_grouped = df.groupby("dia", as_index=False).agg(volume=("volume", "sum")).sort_values("dia")
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
    return fig_volume
