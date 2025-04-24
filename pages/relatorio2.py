import json
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
        # Considera que os dados foram serializados com orient="records"
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
                            id="date-picker-range",
                            min_date_allowed=datetime(2020, 1, 1),
                            max_date_allowed=datetime.today().date(),
                            start_date=(datetime.today().date() - timedelta(days=7)),
                            end_date=datetime.today().date(),
                            display_format="DD/MM/YYYY",
                            className="mb-2",
                            style={"width": "100%"}
                        ),
                        dbc.Button(
                            "Aplicar Filtro",
                            id="apply-button",
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
                            id="operacao-dropdown",
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
        dcc.Store(id="data-store"),
        dcc.Store(id="data-store-hora"),
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
                                        id="tabela-1",
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
                                        id="tabela-2",
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
                                        id="grafico-volume",
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
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                html.H5("Gráfico de Massa", className="mb-0"),
                                className="bg-light",
                                style={"fontFamily": "Arial, sans-serif"}
                            ),
                            dbc.CardBody(
                                dcc.Loading(
                                    dcc.Graph(
                                        id="grafico-massa",
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
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                html.H5("Viagens por Hora Trabalhada (Último Dia)", className="mb-0"),
                                className="bg-light",
                                style={"fontFamily": "Arial, sans-serif"}
                            ),
                            dbc.CardBody(
                                dcc.Loading(
                                    dcc.Graph(
                                        id="grafico-viagens-hora",
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
        ),
        html.Hr(),
        dbc.Row(
            dbc.Col(
                [
                    html.Label(
                        "Filtrar por Modelo (Indicadores):",
                        className="fw-bold text-secondary",
                        style={"fontFamily": "Arial, sans-serif", "fontSize": "16px"}
                    ),
                    dcc.Dropdown(
                        id="modelo-dropdown",
                        placeholder="(Opcional) Selecione um ou mais modelos (Equipamento)",
                        multi=True,
                        style={"fontFamily": "Arial, sans-serif", "fontSize": "16px", "width": "100%"}
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
                                html.H5("Indicadores - Último Dia", className="mb-0"),
                                className="bg-light",
                                style={"fontFamily": "Arial, sans-serif"}
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
                                        style_table={"overflowX": "auto", "width": "100%"},
                                        style_header={
                                            "backgroundColor": "#f8f9fa",
                                            "fontWeight": "bold",
                                            "textAlign": "center"
                                        },
                                        style_cell={
                                            "textAlign": "center",
                                            "fontFamily": "Arial, sans-serif"
                                        }
                                    ),
                                    type="default"
                                )
                            )
                        ],
                        className="mb-4 shadow animate__animated animate__fadeInUp",
                        style={"marginBottom": "30px"}
                    ),
                    xs=12, md=6
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                html.H5("Indicadores - Acumulado", className="mb-0"),
                                className="bg-light",
                                style={"fontFamily": "Arial, sans-serif"}
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
                                        style_table={"overflowX": "auto", "width": "100%"},
                                        style_header={
                                            "backgroundColor": "#f8f9fa",
                                            "fontWeight": "bold",
                                            "textAlign": "center"
                                        },
                                        style_cell={
                                            "textAlign": "center",
                                            "fontFamily": "Arial, sans-serif"
                                        }
                                    ),
                                    type="default"
                                )
                            )
                        ],
                        className="mb-4 shadow animate__animated animate__fadeInUp",
                        style={"marginBottom": "30px"}
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
    """
    Consulta os dados de produção e hora entre as datas selecionadas e armazena-os em JSON.
    """
    if not start_date or not end_date:
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
        df_prod = query_to_df(query_prod)
    except Exception as e:
        return ({"error": f"Erro ao consultar Produção: {str(e)}"}, {})

    if not df_prod.empty and "dt_registro_turno" in df_prod.columns:
        df_prod = convert_date_columns(df_prod, ["dt_registro_turno"])
        df_prod = filter_by_date(df_prod, "dt_registro_turno", start_date_obj, end_date_obj)
        if "nome_operacao" in df_prod.columns:
            df_prod = df_prod.dropna(subset=["nome_operacao"])
    data_prod_json = df_prod.to_json(date_format="iso", orient="records") if not df_prod.empty else {}

    query_hora = f"EXEC dw_sdp_mt_fas..usp_fato_hora '{start_date_str}', '{end_date_str}'"
    try:
        df_h = query_to_df(query_hora)
    except Exception as e:
        return data_prod_json, {"error": f"Erro ao consultar Hora: {str(e)}"}

    if not df_h.empty:
        df_h = convert_date_columns(df_h, ["dt_registro", "dt_registro_turno"])
    data_hora_json = df_h.to_json(date_format="iso", orient="records") if not df_h.empty else {}

    return data_prod_json, data_hora_json


@callback(
    Output("operacao-dropdown", "options"),
    Input("data-store", "data")
)
def update_operacoes_options(json_data: Union[str, dict]) -> List[Dict[str, str]]:
    df = load_df(json_data)
    if df.empty:
        return []
    df["nome_operacao"] = df["nome_operacao"].astype("category")
    ops_unicas = sorted(df["nome_operacao"].dropna().unique())
    return [{"label": op, "value": op} for op in ops_unicas]


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
    Output("grafico-volume", "figure"),
    Output("grafico-massa", "figure"),
    Input("data-store", "data"),
    Input("operacao-dropdown", "value")
)
def update_graphs(json_data: Union[str, dict], operacoes_selecionadas: List[str]):
    df = load_df(json_data)
    if df.empty:
        fig_empty = px.bar(title="Selecione um período para ver o gráfico.", template="plotly_white")
        return fig_empty, fig_empty

    df = convert_date_columns(df, ["dt_registro_turno"]).dropna(subset=["dt_registro_turno"])
    if operacoes_selecionadas:
        df = df.loc[df["nome_operacao"].isin(operacoes_selecionadas)]
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
    Output("grafico-viagens-hora", "figure"),
    Input("data-store", "data"),
    Input("data-store-hora", "data"),
    Input("date-picker-range", "end_date"),
    Input("operacao-dropdown", "value")
)
def update_grafico_viagens_hora(json_prod: Union[str, dict], json_hora: Union[str, dict],
                                end_date: str, operacoes_selecionadas: List[str]):
    df_prod = load_df(json_prod)
    df_hora = load_df(json_hora)
    if df_prod.empty or df_hora.empty or not end_date:
        return px.bar(title="Sem dados para gerar o gráfico de Viagens por Hora Trabalhada.", template="plotly_white")

    # Verifica se há mensagens de erro nos dados
    if "error" in (json_prod if isinstance(json_prod, dict) else {}):
        return px.bar(title=json_prod["error"], template="plotly_white")
    if "error" in (json_hora if isinstance(json_hora, dict) else {}):
        return px.bar(title=json_hora["error"], template="plotly_white")

    try:
        df_prod = convert_date_columns(df_prod, ["dt_registro_turno"]).dropna(subset=["dt_registro_turno"])
        df_hora = convert_date_columns(df_hora, ["dt_registro_turno"]).dropna(subset=["dt_registro_turno"])
    except Exception as e:
        return px.bar(title=f"Erro ao carregar dados: {str(e)}", template="plotly_white")

    filtro_dia = datetime.fromisoformat(end_date).date()
    df_prod = df_prod.loc[df_prod["dt_registro_turno"].dt.date == filtro_dia]
    df_hora = df_hora.loc[df_hora["dt_registro_turno"].dt.date == filtro_dia]

    if operacoes_selecionadas:
        df_prod = df_prod.loc[df_prod["nome_operacao"].isin(operacoes_selecionadas)]
    if df_prod.empty or df_hora.empty:
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
        return px.bar(title="Sem dados para gerar o gráfico de Viagens por Hora Trabalhada.", template="plotly_white")

    # Evita divisão por zero usando replace e fillna
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
    Output("modelo-dropdown", "options"),
    Input("data-store-hora", "data")
)
def load_modelos_options(json_data_hora: Union[str, dict]) -> List[Dict[str, str]]:
    df_h = load_df(json_data_hora)
    if df_h.empty or "nome_modelo" not in df_h.columns:
        return []
    df_h["nome_modelo"] = df_h["nome_modelo"].astype("category")
    modelos_unicos = sorted(df_h["nome_modelo"].dropna().unique())
    return [{"label": m, "value": m} for m in modelos_unicos]


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
def update_tabelas_indicadores(json_data_hora: Union[str, dict],
                               lista_modelos: List[str],
                               end_date: str
                               ) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict], List[Dict], List[Dict]]:
    df_h = load_df(json_data_hora)
    if df_h.empty:
        return [], [], [], [], [], []

    df_h = convert_date_columns(df_h, ["dt_registro_turno"])
    
    # Ajuste para modelos específicos de perfuração
    perfuracao_modelos = ["PERFURATRIZ HIDRAULICA SANDVIK DP1500I", "PERFURATRIZ HIDRAULICA SANDVIK DX800"]
    mask_perf = df_h["nome_modelo"].isin(perfuracao_modelos)
    df_h.loc[mask_perf, "nome_tipo_equipamento"] = "Perfuração"
    
    # Convertendo colunas de filtro para categoria
    if "nome_modelo" in df_h.columns:
        df_h["nome_modelo"] = df_h["nome_modelo"].astype("category")
    if "nome_tipo_equipamento" in df_h.columns:
        df_h["nome_tipo_equipamento"] = df_h["nome_tipo_equipamento"].astype("category")
    
    if lista_modelos:
        df_h = df_h.loc[df_h["nome_modelo"].isin(lista_modelos)]
        if df_h.empty:
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
