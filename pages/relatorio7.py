from __future__ import annotations

"""
relatorio7.py – Informativo de Produção

Exibe um relatório com tabelas de movimentação (último dia e acumulada) e gráfico de volume por dia.
Otimizado para performance com cache em consultas e operações vetorizadas, mantendo todas as funcionalidades
e importações originais. Inclui logs para diagnosticar dados vazios.

Dependências:
  - Banco de dados via `db.query_to_df`
  - Configurações `META_MINERIO`, `META_ESTERIL`, `PROJECTS_CONFIG`, `PROJECT_LABELS` de `config`
"""

# ============================================================
# IMPORTAÇÕES
# ============================================================
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple, Union, Optional

import dash
from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc
from dash.dash_table import DataTable
from dash.dash_table.Format import Format, Scheme
import plotly.express as px
import pandas as pd
import numpy as np

from db import query_to_df
from config import META_MINERIO, META_ESTERIL, PROJECTS_CONFIG, PROJECT_LABELS
from app import cache

# ============================================================
# CONFIGURAÇÕES
# ============================================================

# Formato numérico para tabelas
NUM_FORMAT = Format(precision=2, scheme=Scheme.fixed, group=True)

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

@cache.memoize(timeout=300)
def fetch_production_data(start_date: str, end_date: str, projeto: str) -> pd.DataFrame:
    """
    Consulta os dados de produção no banco para o período especificado, com cache.

    Args:
        start_date (str): Data inicial (DD/MM/YYYY).
        end_date (str): Data final (DD/MM/YYYY).
        projeto (str): ID do projeto (ex.: 'projeto1').

    Returns:
        pd.DataFrame: Dados de produção ou DataFrame vazio em caso de erro.
    """
    print(f"[DEBUG] Consultando dados de {start_date} a {end_date} para projeto {projeto}")
    if not projeto or projeto not in PROJECTS_CONFIG:
        print("[DEBUG] Projeto inválido ou não selecionado")
        return pd.DataFrame()
    
    query = f"""
        EXEC {PROJECTS_CONFIG[projeto]['database']}..usp_fato_producao
        '{start_date}',
        '{end_date}'
    """
    try:
        df = query_to_df(query, projeto=projeto)
        print(f"[DEBUG] Dados brutos retornados: {len(df)} linhas")
        if df.empty or "dt_registro_turno" not in df.columns:
            print("[DEBUG] DataFrame vazio ou sem coluna 'dt_registro_turno'")
            return pd.DataFrame()
        
        # Forçar conversão para datetime com formatos comuns
        df["dt_registro_turno"] = pd.to_datetime(
            df["dt_registro_turno"],
            errors="coerce",
            infer_datetime_format=True
        )
        
        # Logar linhas com datas inválidas
        invalid_dates = df["dt_registro_turno"].isna().sum()
        print(f"[DEBUG] Linhas com datas inválidas (NaT): {invalid_dates}")
        
        # Remover apenas linhas com nome_operacao nulo
        df = df.dropna(subset=["nome_operacao"])
        print(f"[DEBUG] Após dropna(nome_operacao): {len(df)} linhas")
        
        return df
    except Exception as e:
        print(f"[DEBUG] Erro ao consultar Produção: {str(e)}")
        return pd.DataFrame()

def filter_by_date_range(df: pd.DataFrame, date_col: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    Filtra o DataFrame por intervalo de datas usando operações vetorizadas.

    Args:
        df (pd.DataFrame): DataFrame a filtrar.
        date_col (str): Coluna de data.
        start_date (datetime): Data inicial.
        end_date (datetime): Data final.

    Returns:
        pd.DataFrame: DataFrame filtrado.
    """
    if date_col in df.columns:
        # Converter novamente para garantir formato datetime
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        if df[date_col].notna().any():
            mask = (df[date_col] >= start_date) & (df[date_col] <= end_date)
            filtered_df = df[mask]
            print(f"[DEBUG] Após filtro de data ({start_date} a {end_date}): {len(filtered_df)} linhas")
            return filtered_df
    print("[DEBUG] Coluna de data ausente ou inválida")
    return df

def aggregate_movimentacao(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """
    Agrupa o DataFrame por uma coluna, calculando viagens, volume e massa.

    Args:
        df (pd.DataFrame): DataFrame a agrupar.
        group_col (str): Coluna de agrupamento.

    Returns:
        pd.DataFrame: DataFrame com agregações.
    """
    grouped = df.groupby(group_col, as_index=False).agg(
        viagens=pd.NamedAgg(column=group_col, aggfunc="size"),
        volume=pd.NamedAgg(column="volume", aggfunc="sum"),
        massa=pd.NamedAgg(column="massa", aggfunc="sum")
    )
    print(f"[DEBUG] Após agregação por {group_col}: {len(grouped)} linhas")
    return grouped

def append_total_row(df_group: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """
    Adiciona uma linha de total ao DataFrame agrupado.

    Args:
        df_group (pd.DataFrame): DataFrame agrupado.
        group_col (str): Coluna de agrupamento.

    Returns:
        pd.DataFrame: DataFrame com linha de total.
    """
    total = pd.DataFrame({
        group_col: ["TOTAL"],
        "viagens": [df_group["viagens"].sum()],
        "volume": [df_group["volume"].sum()],
        "massa": [df_group["massa"].sum()]
    })
    return pd.concat([df_group, total], ignore_index=True)

def load_json_data(json_data: Union[str, Dict]) -> pd.DataFrame:
    """
    Converte JSON ou dicionário para DataFrame, retornando vazio em caso de erro.

    Args:
        json_data (Union[str, Dict]): Dados em JSON ou dicionário.

    Returns:
        pd.DataFrame: DataFrame carregado ou vazio.
    """
    if not json_data or (isinstance(json_data, dict) and "error" in json_data):
        print("[DEBUG] JSON vazio ou com erro")
        return pd.DataFrame()
    try:
        df = pd.read_json(json_data, orient="records")
        print(f"[DEBUG] JSON carregado: {len(df)} linhas")
        return df
    except Exception as e:
        print(f"[DEBUG] Erro ao carregar JSON: {str(e)}")
        return pd.DataFrame()

def get_table_columns() -> List[Dict]:
    """
    Retorna as colunas para as tabelas de movimentação.

    Returns:
        List[Dict]: Definições de colunas.
    """
    return [
        {"name": "Operação", "id": "nome_operacao", "type": "text"},
        {"name": "Viagens", "id": "viagens", "type": "numeric", "format": NUM_FORMAT},
        {"name": "Volume", "id": "volume", "type": "numeric", "format": NUM_FORMAT},
        {"name": "Massa", "id": "massa", "type": "numeric", "format": NUM_FORMAT}
    ]

def create_volume_graph(df: pd.DataFrame, operacoes_selecionadas: Optional[List[str]] = None, projeto: str = None) -> px.bar:
    """
    Cria um gráfico de barras para volume por dia, com cores baseadas em metas.

    Args:
        df (pd.DataFrame): DataFrame com dados.
        operacoes_selecionadas (Optional[List[str]]): Operações filtradas.
        projeto (str): ID do projeto (ex.: 'projeto1').

    Returns:
        px.bar: Gráfico Plotly.
    """
    if df.empty or "dt_registro_turno" not in df.columns:
        print("[DEBUG] DataFrame vazio ou sem dt_registro_turno em create_volume_graph")
        return px.bar(title="Selecione uma obra para visualizar os dados.", template="plotly_white")

    # Garantir que dt_registro_turno seja datetime
    df["dt_registro_turno"] = pd.to_datetime(df["dt_registro_turno"], errors="coerce")
    if df["dt_registro_turno"].isna().all():
        print("[DEBUG] Todas as datas são NaT em create_volume_graph")
        return px.bar(title="Dados de data inválidos.", template="plotly_white")

    df_filtered = df[df["nome_operacao"].isin(operacoes_selecionadas)] if operacoes_selecionadas else df
    if df_filtered.empty:
        print("[DEBUG] DataFrame filtrado vazio em create_volume_graph")
        return px.bar(title="Sem dados para esse filtro.", template="plotly_white")

    df_filtered["dia"] = df_filtered["dt_registro_turno"].dt.date
    df_grouped = df_filtered.groupby("dia", as_index=False).agg(volume=("volume", "sum")).sort_values("dia")
    meta_total = META_MINERIO + META_ESTERIL
    df_grouped["bar_color"] = np.where(df_grouped["volume"] >= meta_total, "rgb(149,211,36)", "red")

    fig = px.bar(
        df_grouped,
        x="dia",
        y="volume",
        title=f"Soma do Volume por Dia ({PROJECT_LABELS.get(projeto, 'Nenhuma obra selecionada')})",
        text="volume",
        template="plotly_white"
    )
    fig.update_traces(
        textposition="outside",
        texttemplate="%{y:,.2f}",
        cliponaxis=False,
        marker_color=df_grouped["bar_color"],
        textfont=dict(family="Arial Black", size=16, color="black")
    )
    fig.update_layout(
        xaxis_title="Dia",
        yaxis_title="Volume",
        title_x=0.5,
        margin=dict(l=40, r=40, t=60, b=40)
    )
    fig.update_yaxes(tickformat="0,0.00")
    return fig

# ============================================================
# LAYOUT
# ============================================================

NAVBAR = dbc.Navbar(
    dbc.Container([
        dbc.NavbarBrand([
            html.I(className="fas fa-chart-bar mr-2"),
            "Informativo de Produção"
        ], href="/relatorio7", className="ms-2 d-flex align-items-center", style={"fontSize": "1.1rem"}),
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
    html.Div(
        id="rel7-no-project-message",
        children=html.P(
            "Selecione uma obra para visualizar os dados.",
            className="text-center my-4",
            style={"color": "#343a40", "fontSize": "1.2rem"}
        )
    ),
    dbc.Row(
        dbc.Col(
            html.H3(
                [html.I(className="fas fa-chart-bar mr-2"), "Informativo de Produção"],
                className="text-center mt-4 mb-4",
                style={"fontFamily": "Arial, sans-serif", "fontSize": "1.6rem", "fontWeight": "500"}
            ),
            width=12
        ),
        className="mb-3"
    ),
    dbc.Row(
        dbc.Col(
            html.H5(
                "Análise de Produção e Indicadores no Período Selecionado",
                className="text-center text-muted",
                style={"fontFamily": "Arial, sans-serif", "fontSize": "1.1rem"}
            ),
            width=12
        ),
        className="mb-4"
    ),
    dbc.Card([
        dbc.CardHeader(
            html.H5("Filtros de Análise", className="mb-0 text-white", style={
                "fontSize": "1.1rem",
                "fontWeight": "500",
                "fontFamily": "Arial, sans-serif"
            }),
            style={"background": "linear-gradient(90deg, #343a40, #495057)"}
        ),
        dbc.CardBody(
            dbc.Row([
                dbc.Col([
                    html.Label(
                        "Selecione o Período:",
                        className="fw-bold text-secondary",
                        style={"fontFamily": "Arial, sans-serif", "fontSize": "0.9rem"}
                    ),
                    dcc.DatePickerRange(
                        id="date-picker-range-rel7",
                        min_date_allowed=datetime(2020, 1, 1),
                        max_date_allowed=datetime.today().date(),
                        start_date=(datetime.today() - timedelta(days=7)),
                        end_date=datetime.today().date(),
                        display_format="DD/MM/YYYY",
                        className="mb-2",
                        style={"width": "100%", "fontSize": "0.9rem"}
                    ),
                    dbc.Button(
                        [html.I(className="fas fa-filter mr-1"), "Aplicar Filtro"],
                        id="apply-button-rel7",
                        n_clicks=0,
                        className="w-100 mt-2",
                        style={
                            "fontSize": "0.9rem",
                            "borderRadius": "8px",
                            "background": "linear-gradient(45deg, #007bff, #00aaff)",
                            "color": "#fff",
                            "transition": "all 0.3s",
                            "padding": "6px 12px"
                        }
                    )
                ], xs=12, md=4, className="mb-2 mb-md-0"),
                dbc.Col([
                    html.Label(
                        "Filtrar Operações (opcional):",
                        className="fw-bold text-secondary",
                        style={"fontFamily": "Arial, sans-serif", "fontSize": "0.9rem"}
                    ),
                    dcc.Dropdown(
                        id="operacao-dropdown-rel7",
                        placeholder="Selecione uma ou mais operações",
                        multi=True,
                        className="mb-2",
                        style={
                            "fontFamily": "Arial, sans-serif",
                            "fontSize": "0.9rem",
                            "borderRadius": "8px",
                            "backgroundColor": "#f8f9fa",
                            "padding": "6px"
                        }
                    )
                ], xs=12, md=8)
            ]),
            style={"padding": "0.8rem"}
        )
    ], className="shadow-md mb-4 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none", "zIndex": "10"}),
    dcc.Store(id="data-store-rel7"),
    dbc.Row([
        dbc.Col(
            dbc.Card([
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
                            id="tabela-1-rel7",
                            style_table={"overflowX": "auto", "width": "100%"},
                            style_header={
                                "backgroundColor": "#f8f9fa",
                                "fontWeight": "bold",
                                "textAlign": "center",
                                "fontSize": "0.9rem",
                                "fontFamily": "Arial, sans-serif"
                            },
                            style_cell={
                                "textAlign": "center",
                                "whiteSpace": "normal",
                                "fontFamily": "Arial, sans-serif",
                                "fontSize": "0.85rem",
                                "padding": "6px"
                            }
                        ),
                        type="default"
                    ),
                    style={"padding": "0.8rem"}
                )
            ], className="shadow-md mb-4 animate__animated animate__fadeInUp"),
            xs=12, md=6
        ),
        dbc.Col(
            dbc.Card([
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
                            id="tabela-2-rel7",
                            style_table={"overflowX": "auto", "width": "100%"},
                            style_header={
                                "backgroundColor": "#f8f9fa",
                                "fontWeight": "bold",
                                "textAlign": "center",
                                "fontSize": "0.9rem",
                                "fontFamily": "Arial, sans-serif"
                            },
                            style_cell={
                                "textAlign": "center",
                                "whiteSpace": "normal",
                                "fontFamily": "Arial, sans-serif",
                                "fontSize": "0.85rem",
                                "padding": "6px"
                            }
                        ),
                        type="default"
                    ),
                    style={"padding": "0.8rem"}
                )
            ], className="shadow-md mb-4 animate__animated animate__fadeInUp"),
            xs=12, md=6
        )
    ], className="mt-2"),
    dbc.Row(
        dbc.Col(
            dbc.Card([
                dbc.CardHeader(
                    html.H5("Gráfico de Volume", className="mb-0 text-white", style={
                        "fontSize": "1.1rem",
                        "fontWeight": "500",
                        "fontFamily": "Arial, sans-serif"
                    }),
                    style={"background": "linear-gradient(90deg, #343a40, #495057)"}
                ),
                dbc.CardBody(
                    dcc.Loading(
                        dcc.Graph(
                            id="grafico-volume-rel7",
                            config={"displayModeBar": False, "responsive": True},
                            style={"minHeight": "450px"}
                        ),
                        type="default"
                    ),
                    style={"padding": "0.8rem"}
                )
            ], className="shadow-md mb-4 animate__animated animate__fadeInUp"),
            xs=12
        ),
        className="mt-2"
    )
], fluid=True)

# ============================================================
# CALLBACKS
# ============================================================

@callback(
    [Output("data-store-rel7", "data"),
     Output("rel7-no-project-message", "style")],
    [Input("apply-button-rel7", "n_clicks"),
     Input("projeto-store", "data")],
    [State("date-picker-range-rel7", "start_date"),
     State("date-picker-range-rel7", "end_date")],
    prevent_initial_call=True
)
def store_production_data(n_clicks: int, projeto: str, start_date: str, end_date: str) -> Tuple[Any, Dict]:
    """
    Consulta e armazena os dados de produção para o período selecionado.

    Args:
        n_clicks (int): Número de cliques no botão de filtro.
        projeto (str): ID do projeto (ex.: 'projeto1').
        start_date (str): Data inicial (ISO).
        end_date (str): Data final (ISO).

    Returns:
        Tuple: JSON com dados ou dicionário de erro, e estilo da mensagem de "sem projeto".
    """
    print(f"[DEBUG] store_production_data disparado: n_clicks={n_clicks}, projeto={projeto}, start_date={start_date}, end_date={end_date}")
    
    if not projeto or projeto not in PROJECTS_CONFIG:
        print("[DEBUG] Nenhum projeto selecionado ou projeto inválido")
        return {}, {"display": "block", "textAlign": "center", "color": "#343a40", "fontSize": "1.2rem", "margin": "20px 0"}

    if not start_date or not end_date:
        print("[DEBUG] Datas de filtro não fornecidas")
        return {}, {"display": "none"}

    start_date_obj = datetime.fromisoformat(start_date)
    end_date_obj = datetime.fromisoformat(end_date)
    start_date_str = start_date_obj.strftime("%d/%m/%Y")
    end_date_str = end_date_obj.strftime("%d/%m/%Y")

    df_prod = fetch_production_data(start_date_str, end_date_str, projeto)
    if df_prod.empty:
        print("[DEBUG] Nenhum dado retornado por fetch_production_data")
        return {"error": "Nenhum dado encontrado para o período selecionado."}, {"display": "none"}

    df_prod = filter_by_date_range(df_prod, "dt_registro_turno", start_date_obj, end_date_obj)
    if df_prod.empty:
        print("[DEBUG] DataFrame vazio após filter_by_date_range")
        return {"error": "Nenhum dado válido após filtragem por data."}, {"display": "none"}

    return df_prod.to_json(date_format="iso", orient="records"), {"display": "none"}

@callback(
    Output("operacao-dropdown-rel7", "options"),
    [Input("data-store-rel7", "data"),
     Input("projeto-store", "data")]
)
def update_dropdown_options(json_data: Union[str, Dict], projeto: str) -> List[Dict[str, str]]:
    """
    Atualiza as opções do dropdown com base nos dados armazenados.

    Args:
        json_data (Union[str, Dict]): Dados em JSON.
        projeto (str): ID do projeto (ex.: 'projeto1').

    Returns:
        List[Dict[str, str]]: Opções para o dropdown.
    """
    print(f"[DEBUG] update_dropdown_options disparado: projeto={projeto}")
    
    if not projeto or projeto not in PROJECTS_CONFIG:
        print("[DEBUG] Nenhum projeto selecionado ou projeto inválido")
        return []

    df = load_json_data(json_data)
    if df.empty or "nome_operacao" not in df.columns:
        print("[DEBUG] Nenhum dado ou nome_operacao ausente em update_dropdown_options")
        return []
    ops_unicas = sorted(df["nome_operacao"].astype("category").dropna().unique())
    print(f"[DEBUG] Operações únicas encontradas: {len(ops_unicas)}")
    return [{"label": op, "value": op} for op in ops_unicas]

@callback(
    [
        Output("tabela-1-rel7", "data"),
        Output("tabela-1-rel7", "columns"),
        Output("tabela-1-rel7", "style_data_conditional"),
        Output("tabela-2-rel7", "data"),
        Output("tabela-2-rel7", "columns"),
        Output("tabela-2-rel7", "style_data_conditional"),
        Output("grafico-volume-rel7", "figure")
    ],
    [
        Input("data-store-rel7", "data"),
        Input("operacao-dropdown-rel7", "value"),
        Input("projeto-store", "data"),
        State("date-picker-range-rel7", "start_date"),
        State("date-picker-range-rel7", "end_date")
    ]
)
def update_tables_and_graph(
    json_data: Union[str, Dict],
    operacoes_selecionadas: Optional[List[str]],
    projeto: str,
    start_date: str,
    end_date: str
) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict], List[Dict], List[Dict], px.bar]:
    """
    Atualiza as tabelas e o gráfico com base nos dados e filtros.

    Args:
        json_data (Union[str, Dict]): Dados em JSON.
        operacoes_selecionadas (Optional[List[str]]): Operações selecionadas.
        projeto (str): ID do projeto (ex.: 'projeto1').
        start_date (str): Data inicial (ISO).
        end_date (str): Data final (ISO).

    Returns:
        Tuple: Dados, colunas, estilos para tabelas e figura do gráfico.
    """
    print(f"[DEBUG] update_tables_and_graph disparado: projeto={projeto}, operacoes_selecionadas={operacoes_selecionadas}")
    
    if not projeto or projeto not in PROJECTS_CONFIG:
        print("[DEBUG] Nenhum projeto selecionado ou projeto inválido")
        empty_cols = get_table_columns()
        empty_fig = px.bar(title="Selecione uma obra para visualizar os dados.", template="plotly_white")
        return [], empty_cols, [], [], empty_cols, [], empty_fig

    df = load_json_data(json_data)
    if df.empty or "dt_registro_turno" not in df.columns:
        print("[DEBUG] DataFrame vazio ou sem dt_registro_turno em update_tables_and_graph")
        empty_cols = get_table_columns()
        empty_fig = px.bar(title="Selecione uma obra para visualizar os dados.", template="plotly_white")
        return [], empty_cols, [], [], empty_cols, [], empty_fig

    # Garantir que dt_registro_turno seja datetime
    df["dt_registro_turno"] = pd.to_datetime(df["dt_registro_turno"], errors="coerce")
    if df["dt_registro_turno"].isna().all():
        print("[DEBUG] Todas as datas são NaT em update_tables_and_graph")
        empty_cols = get_table_columns()
        empty_fig = px.bar(title="Dados de data inválidos.", template="plotly_white")
        return [], empty_cols, [], [], empty_cols, [], empty_fig

    if operacoes_selecionadas:
        df = df[df["nome_operacao"].isin(operacoes_selecionadas)]
        print(f"[DEBUG] Após filtro por operações: {len(df)} linhas")
    if df.empty:
        print("[DEBUG] DataFrame vazio após filtro por operações")
        empty_cols = get_table_columns()
        empty_fig = px.bar(title="Sem dados para esse filtro.", template="plotly_white")
        return [], empty_cols, [], [], empty_cols, [], empty_fig

    # Tabela 1: Movimentação do último dia
    ultimo_dia = df["dt_registro_turno"].dt.date.max()
    df_last_day = df[df["dt_registro_turno"].dt.date == ultimo_dia]
    print(f"[DEBUG] Dados do último dia ({ultimo_dia}): {len(df_last_day)} linhas")
    df_t1 = aggregate_movimentacao(df_last_day, "nome_operacao")
    df_t1 = append_total_row(df_t1, "nome_operacao")

    # Tabela 2: Movimentação acumulada
    df_t2 = aggregate_movimentacao(df, "nome_operacao")
    df_t2 = append_total_row(df_t2, "nome_operacao")

    # Estilos condicionais
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

    # Gráfico
    fig_volume = create_volume_graph(df, operacoes_selecionadas, projeto)

    columns = get_table_columns()
    return (
        df_t1.to_dict("records"),
        columns,
        style_cond_t1,
        df_t2.to_dict("records"),
        columns,
        style_cond_t2,
        fig_volume
    )
