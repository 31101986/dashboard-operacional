import math
import logging
from datetime import datetime, timedelta

import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import dash_table
import plotly.express as px
import pandas as pd

# Importa o fuso horário definido em config.py
from config import TIMEZONE

# Configuração do log (utilize seu gerenciador de logs conforme necessário)
logging.basicConfig(
    level=logging.INFO,
    filename="dashboard.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)

from db import query_to_df

# =============================================================================
# CONSTANTES
# =============================================================================
MAPBOX_TOKEN = ""  # Informe seu token Mapbox, se disponível
DEFAULT_MAP_STYLE = "open-street-map"  # Forçamos um estilo fixo

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def get_current_shift_period():
    """
    Retorna o início e o fim do turno atual (07:00 → 07:00 do dia seguinte),
    considerando o fuso horário definido em TIMEZONE.
    """
    now = datetime.now(TIMEZONE)
    # Define a base como hoje às 07:00 (tz-aware)
    shift_start = now.replace(hour=7, minute=0, second=0, microsecond=0)

    # Se ainda não chegamos às 07:00 de hoje, significa que o turno começou ontem às 07:00
    if now.hour < 7:
        shift_start -= timedelta(days=1)

    # Fim do turno: 24 horas após o início
    shift_end = shift_start + timedelta(days=1)
    return shift_start, shift_end

def no_data_fig(title):
    """Retorna um gráfico vazio com mensagem 'Sem dados...' e layout modernizado."""
    df_empty = pd.DataFrame({"x": [], "y": []})
    fig = px.bar(df_empty, x="x", y="y", title=title)
    fig.update_layout(
        template="plotly_white",
        title_x=0.5,
        xaxis={'visible': False},
        yaxis={'visible': False},
        annotations=[{
            "text": "Sem dados para o período selecionado",
            "xref": "paper",
            "yref": "paper",
            "showarrow": False,
            "font": {"size": 16}
        }],
        margin=dict(l=30, r=30, t=60, b=60),
        font=dict(family="Arial, sans-serif", size=14)
    )
    return fig

def no_data_table():
    """Retorna uma linha de tabela informando que não há dados."""
    return [{"Mensagem": "Sem dados para o período selecionado"}]

def execute_query(query):
    """Executa a query usando query_to_df e trata exceções, retornando um DataFrame."""
    try:
        return query_to_df(query)
    except Exception as e:
        logging.error(f"Erro na execução da query: {e}")
        return pd.DataFrame()

def common_map_layout(center_lat, center_lon):
    """
    Layout padrão para mapas com configurações centralizadas,
    utilizando estilo fixo 'open-street-map'.
    """
    return {
        "template": "plotly_white",
        "mapbox_style": DEFAULT_MAP_STYLE,
        "mapbox_accesstoken": MAPBOX_TOKEN if MAPBOX_TOKEN else None,
        "mapbox": {
            "center": {"lat": center_lat, "lon": center_lon},
            "zoom": 15,
            "pitch": 30
        },
        "uirevision": "constant",
        "title_x": 0.5,
        "margin": {"r": 0, "t": 60, "l": 0, "b": 0},
        "title_font": {"size": 20, "color": "black"},
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 0.01,
            "xanchor": "right",
            "x": 0.99,
            "title": ""
        },
        "font": {"family": "Arial, sans-serif", "size": 14}
    }

def localize_column_tz(df, col_name):
    """
    Converte a coluna 'col_name' de df para datetime (se ainda não for)
    e, se estiver tz-naive, localiza no TIMEZONE; caso já tenha timezone,
    converte para TIMEZONE.
    """
    if col_name not in df.columns:
        return df
    
    # 1. Converte para datetime
    df[col_name] = pd.to_datetime(df[col_name], errors="coerce")
    
    # 2. Se estiver completamente sem timezone, localize no TIMEZONE
    # (Verificando se "dt.tz" é None)
    sample_tz = df[col_name].dt.tz
    if sample_tz is None:
        df[col_name] = df[col_name].dt.tz_localize(TIMEZONE)
    else:
        # Caso já tenha timezone, converta para o TIMEZONE local
        df[col_name] = df[col_name].dt.tz_convert(TIMEZONE)
    return df

def get_filtered_data_producao(period_start, period_end, operacao_filter=None, df=None):
    """
    Filtra os dados de Produção localmente ou executa a query se df for None.
    Aplica filtros de data e, se informado, de operação.
    """
    if df is None:
        query = (
            f"EXEC dw_sdp_mt_fas..usp_fato_producao "
            f"'{period_start:%d/%m/%Y %H:%M:%S}', '{period_end:%d/%m/%Y %H:%M:%S}'"
        )
        df = execute_query(query)
    if df.empty:
        return df

    # Convertemos a coluna dt_registro_fim para tz-aware antes de comparar
    if "dt_registro_fim" in df.columns:
        df = localize_column_tz(df, "dt_registro_fim")
        # Filtra pelo turno
        df = df[(df["dt_registro_fim"] >= period_start) & (df["dt_registro_fim"] < period_end)]
    
    if operacao_filter and "nome_operacao" in df.columns:
        df = df[df["nome_operacao"].isin(operacao_filter)]
    return df

def get_filtered_data_hora(period_start, period_end, only_today=True, df=None):
    """
    Filtra os dados de 'Hora' localmente ou executa a query se df for None.
    Filtra por estado específico e converte colunas de data (dt_registro_turno).
    """
    if df is None:
        query = (
            f"EXEC dw_sdp_mt_fas..usp_fato_hora "
            f"'{period_start:%d/%m/%Y %H:%M:%S}', '{period_end:%d/%m/%Y %H:%M:%S}'"
        )
        df = execute_query(query)
    if df.empty:
        return df

    if "dt_registro_turno" in df.columns:
        df = localize_column_tz(df, "dt_registro_turno")
        df = df[(df["dt_registro_turno"] >= period_start) & (df["dt_registro_turno"] < period_end)]

    if "nome_estado" in df.columns:
        df = df[df["nome_estado"].isin(["Carregando", "Manobra no Carregamento"])]

    return df

def compute_truck_stats(df_prod_period, df_hora):
    """
    Calcula estatísticas de ciclo e estima os caminhões necessários.
    Caso 'tempo_ciclo_minuto' seja superior a 120, considera o valor 60.
    """
    if df_prod_period.empty:
        cols = ["nome_equipamento_utilizado", "avg_cycle", "avg_carregando", "avg_manobra", "trucks_needed"]
        return pd.DataFrame(columns=cols)

    if "tempo_ciclo_minuto" in df_prod_period.columns:
        df_prod_period["tempo_ciclo_minuto"] = pd.to_numeric(df_prod_period["tempo_ciclo_minuto"], errors="coerce")
        df_prod_period.loc[df_prod_period["tempo_ciclo_minuto"] > 60, "tempo_ciclo_minuto"] = 45

    prod_grp = df_prod_period.groupby("nome_equipamento_utilizado", as_index=False).agg(
        avg_cycle=("tempo_ciclo_minuto", "mean")
    )
    prod_grp["avg_cycle"] = prod_grp["avg_cycle"].round(2)

    base = df_prod_period[["cod_viagem", "nome_equipamento_utilizado"]].drop_duplicates()

    if df_hora.empty:
        prod_grp["avg_carregando"] = 3.5
        prod_grp["avg_manobra"] = 1
    else:
        cod_list = df_prod_period["cod_viagem"].unique()
        df_join = df_hora[df_hora["cod_viagem"].isin(cod_list)]
        df_join = pd.merge(base, df_join, on="cod_viagem", how="left")

        def compute_avg(grp, state, default):
            sub = grp[grp["nome_estado"] == state]
            if not sub.empty:
                val = sub["tempo_minuto"].mean()
                if state == "Carregando":
                    return val if 1 <= val <= 10 else default
                elif state == "Manobra no Carregamento":
                    return val if 5/60 <= val <= 5 else default
            return default

        if not df_join.empty:
            trip_stats = df_join.groupby("cod_viagem").apply(
                lambda g: pd.Series({
                    "avg_carregando": compute_avg(g, "Carregando", 3.5),
                    "avg_manobra": compute_avg(g, "Manobra no Carregamento", 1)
                })
            ).reset_index()
            trip_stats = trip_stats.merge(base, on="cod_viagem", how="left")
            op_grp = trip_stats.groupby("nome_equipamento_utilizado", as_index=False).agg(
                avg_carregando=("avg_carregando", "mean"),
                avg_manobra=("avg_manobra", "mean")
            )
            op_grp["avg_carregando"] = op_grp["avg_carregando"].round(2)
            op_grp["avg_manobra"] = op_grp["avg_manobra"].round(2)
        else:
            eq_list = base["nome_equipamento_utilizado"].unique()
            op_grp = pd.DataFrame({
                "nome_equipamento_utilizado": eq_list,
                "avg_carregando": [3.5] * len(eq_list),
                "avg_manobra": [1] * len(eq_list)
            })

        prod_grp = pd.merge(prod_grp, op_grp, on="nome_equipamento_utilizado", how="left")

    if "avg_carregando" not in prod_grp.columns:
        prod_grp["avg_carregando"] = 3.5
    if "avg_manobra" not in prod_grp.columns:
        prod_grp["avg_manobra"] = 1

    prod_grp["trucks_needed"] = prod_grp.apply(
        lambda row: math.ceil(row["avg_cycle"] / (row["avg_carregando"] + row["avg_manobra"]))
        if (row["avg_carregando"] + row["avg_manobra"]) > 0 else 0, axis=1
    )
    return prod_grp

# =============================================================================
# LAYOUT DO RELATÓRIO
# =============================================================================

# Navbar simples com título centralizado
navbar = dbc.NavbarSimple(
    brand="Dashboard Operacional",
    color="primary",
    dark=True,
    fluid=True,
)

# Layout principal com cabeçalho, filtros e cards para gráficos e tabela
layout = dbc.Container([
    navbar,
    html.H3("Ciclo Operacional", className="text-center mt-4 mb-4", style={"fontFamily": "Arial, sans-serif"}),

    # Linha de filtros e botão de atualização
    dbc.Row([
        dbc.Col(
            dcc.Dropdown(
                id="operacao-filter",
                placeholder="Selecione as Operações",
                multi=True,
                options=[],
                persistence=True,
                persistence_type="session",
                style={"fontSize": "16px"}
            ),
            width=10
        ),
        dbc.Col(
            dbc.Button("Atualizar", id="btn-atualizar", color="primary",
                       className="w-100", style={"fontSize": "16px"}, title="Clique para atualizar os dados"),
            width=2
        ),
    ], className="mb-4 align-items-center"),

    # Informativo de Caminhões
    dbc.Row([
        dbc.Col(
            html.Div(
                id="truck-info",
                style={
                    "fontSize": "24px",
                    "fontWeight": "bold",
                    "textAlign": "center",
                    "padding": "10px",
                    "backgroundColor": "#e9ecef",
                    "borderRadius": "5px"
                }
            ),
            width=12
        )
    ], className="mb-4"),

    # Gráfico: Caminhões Necessários por Escavadeira
    dbc.Row([
        dbc.Col(
            dbc.Card([
                dbc.CardHeader(html.H5("Caminhões Necessários por Escavadeira", className="mb-0")),
                dbc.CardBody(
                    dcc.Loading(
                        dcc.Graph(
                            id="truck-cards",
                            config={"displayModeBar": True, "responsive": True},
                            style={"minHeight": "450px"}
                        ),
                        type="default"
                    )
                )
            ], className="shadow mb-4 animate__animated animate__fadeInUp")
        )
    ]),

    # Linha apenas com o gráfico de Volume por Escavadeira
    dbc.Row([
        dbc.Col(
            dbc.Card([
                dbc.CardHeader(html.H5("Volume por Escavadeira", className="mb-0")),
                dbc.CardBody(
                    dcc.Loading(
                        dcc.Graph(
                            id="volume-bar",
                            config={"displayModeBar": True, "responsive": True},
                            style={"minHeight": "450px"}
                        ),
                        type="default"
                    )
                )
            ], className="shadow mb-4 animate__animated animate__fadeInUp"),
            width=12
        )
    ]),

    # Linha com dois mapas lado a lado: Mapa de Carregamento e Mapa de Basculamento
    dbc.Row([
        dbc.Col(
            dbc.Card([
                dbc.CardHeader(html.H5("Mapa de Carregamento (Detalhado)", className="mb-0")),
                dbc.CardBody(
                    dcc.Loading(
                        dcc.Graph(
                            id="map-carregamento",
                            config={"displayModeBar": True, "responsive": True},
                            style={"minHeight": "400px"}
                        ),
                        type="default"
                    )
                )
            ], className="shadow mb-4 animate__animated animate__fadeInUp"),
            width=12, md=6
        ),
        dbc.Col(
            dbc.Card([
                dbc.CardHeader(html.H5("Mapa de Basculamento", className="mb-0")),
                dbc.CardBody(
                    dcc.Loading(
                        dcc.Graph(
                            id="map-basculamento",
                            config={"displayModeBar": True, "responsive": True},
                            style={"minHeight": "400px"}
                        ),
                        type="default"
                    )
                )
            ], className="shadow mb-4 animate__animated animate__fadeInUp"),
            width=12, md=6
        )
    ]),

    # Linha com a tabela de detalhamento operacional
    dbc.Row([
        dbc.Col(
            dbc.Card([
                dbc.CardHeader(
                    html.H5("Detalhamento Operacional do Dia", className="mb-0 text-white"),
                    style={"backgroundColor": "#343a40"}
                ),
                dbc.CardBody(
                    dash_table.DataTable(
                        id='table-data',
                        columns=[
                            {"name": col, "id": col, "presentation": "markdown"}
                            for col in [
                                'nome_origem', 'nome_destino', 'tempo_ciclo_minuto', 'volume',
                                'dmt_mov_cheio', 'dmt_mov_vazio', 'velocidade_media_cheio', 'velocidade_media_vazio'
                            ]
                        ],
                        data=[],
                        style_cell={'textAlign': 'center', 'padding': '10px', 'fontFamily': 'Arial'},
                        style_header={
                            'fontWeight': 'bold',
                            'backgroundColor': '#343a40',
                            'color': 'white',
                            'fontFamily': 'Arial',
                            'border': '1px solid #ddd'
                        },
                        tooltip_header={
                            'nome_origem': 'Origem da operação',
                            'nome_destino': 'Destino da operação',
                            'tempo_ciclo_minuto': 'Média do tempo de ciclo (min)',
                            'volume': 'Soma do volume produzido',
                            'dmt_mov_cheio': 'Média ponderada de DMT Mov Cheio (peso = volume)',
                            'dmt_mov_vazio': 'Média ponderada de DMT Mov Vazio (peso = volume)',
                            'velocidade_media_cheio': 'Média da velocidade (cheio)',
                            'velocidade_media_vazio': 'Média da velocidade (vazio)'
                        },
                        tooltip_delay=500,
                        tooltip_duration=None,
                        style_data_conditional=[
                            {
                                'if': {'filter_query': '{velocidade_media_cheio} >= 15',
                                       'column_id': 'velocidade_media_cheio'},
                                'color': 'green', 'fontWeight': 'bold'
                            },
                            {
                                'if': {'filter_query': '{velocidade_media_cheio} < 15',
                                       'column_id': 'velocidade_media_cheio'},
                                'color': 'red', 'fontWeight': 'bold'
                            },
                            {
                                'if': {'filter_query': '{velocidade_media_vazio} >= 16',
                                       'column_id': 'velocidade_media_vazio'},
                                'color': 'green', 'fontWeight': 'bold'
                            },
                            {
                                'if': {'filter_query': '{velocidade_media_vazio} < 16',
                                       'column_id': 'velocidade_media_vazio'},
                                'color': 'red', 'fontWeight': 'bold'
                            },
                            {
                                'if': {'state': 'active'},
                                'backgroundColor': '#f1f1f1', 'border': '1px solid #ddd'
                            }
                        ],
                        page_size=10,
                        style_table={'overflowX': 'auto', 'border': '1px solid #ddd', 'borderRadius': '5px'}
                    )
                )
            ], className="shadow mb-4 animate__animated animate__fadeInUp")
        )
    ]),

    # Atualização automática dos dados a cada 25 minutos
    dcc.Interval(id="interval-update", interval=25*60*1000, n_intervals=0),

    # Armazenamento dos dados para produção e hora
    dcc.Store(id="store-producao"),
    dcc.Store(id="store-hora"),

], fluid=True)

# =============================================================================
# CALLBACKS
# =============================================================================

# 1) Callback para buscar e armazenar dados de Produção e Hora
@dash.callback(
    Output("store-producao", "data"),
    Output("store-hora", "data"),
    Input("interval-update", "n_intervals"),
    Input("btn-atualizar", "n_clicks"),
    prevent_initial_call=False
)
def fetch_data(n_intervals, n_clicks):
    # Agora pegamos o período do turno (07:00 → 07:00)
    period_start, period_end = get_current_shift_period()

    query_prod = (
        f"EXEC dw_sdp_mt_fas..usp_fato_producao "
        f"'{period_start:%d/%m/%Y %H:%M:%S}', '{period_end:%d/%m/%Y %H:%M:%S}'"
    )
    df_producao = execute_query(query_prod)

    query_hora = (
        f"EXEC dw_sdp_mt_fas..usp_fato_hora "
        f"'{period_start:%d/%m/%Y %H:%M:%S}', '{period_end:%d/%m/%Y %H:%M:%S}'"
    )
    df_hora = execute_query(query_hora)

    return df_producao.to_dict("records"), df_hora.to_dict("records")

# 2) Callback para atualizar o dropdown de operações com os dados filtrados
@dash.callback(
    Output("operacao-filter", "options"),
    Input("store-producao", "data")
)
def update_dropdown(df_producao_records):
    """
    Ajuste para exibir apenas as operações referentes ao turno atual
    (07:00 -> 07:00), usando dt_registro_fim (caso exista) como referência.
    """
    if not df_producao_records:
        return []
    
    df = pd.DataFrame(df_producao_records)
    period_start, period_end = get_current_shift_period()

    # Se quiser filtrar pela dt_registro_fim para manter apenas o período do turno:
    if "dt_registro_fim" in df.columns:
        df = localize_column_tz(df, "dt_registro_fim")
        df = df[(df["dt_registro_fim"] >= period_start) & (df["dt_registro_fim"] < period_end)]

    if df.empty:
        return []

    if "nome_operacao" in df.columns:
        ops = sorted(df["nome_operacao"].dropna().unique())
        return [{"label": op, "value": op} for op in ops]

    return []

# 3) Callback para resetar o intervalo de atualização manualmente
@dash.callback(
    Output("interval-update", "n_intervals"),
    Input("btn-atualizar", "n_clicks"),
    prevent_initial_call=True
)
def manual_update(n_clicks):
    return 0

# 4) Callback para atualizar o gráfico: Caminhões Necessários por Escavadeira
@dash.callback(
    Output("truck-cards", "figure"),
    Input("store-producao", "data"),
    Input("store-hora", "data"),
    Input("operacao-filter", "value")
)
def update_truck_chart(df_producao_records, df_hora_records, operacao_filter):
    period_start, period_end = get_current_shift_period()

    df_prod_period = pd.DataFrame(df_producao_records or [])
    df_prod_period = get_filtered_data_producao(period_start, period_end, operacao_filter, df=df_prod_period)
    if df_prod_period.empty:
        return no_data_fig("Caminhões Necessários por Escavadeira")

    df_hora = pd.DataFrame(df_hora_records or [])
    df_hora = get_filtered_data_hora(period_start, period_end, df=df_hora)

    merged_data = compute_truck_stats(df_prod_period, df_hora)
    if merged_data.empty:
        return no_data_fig("Caminhões Necessários por Escavadeira")

    merged_data = merged_data.rename(columns={"nome_equipamento_utilizado": "escavadeira"})
    fig = px.scatter(
        merged_data,
        x="escavadeira",
        y="avg_cycle",
        size="trucks_needed",
        color="trucks_needed",
        text="trucks_needed",
        title="Caminhões Necessários por Escavadeira",
        labels={"escavadeira": "Escavadeira", "avg_cycle": "Tempo Médio de Ciclo (min)", "trucks_needed": "Caminhões"},
        size_max=100,
        color_continuous_scale="Viridis",
        hover_data={"avg_cycle": True, "trucks_needed": True, "escavadeira": False}
    )
    fig.update_traces(textposition="middle center", textfont=dict(size=16, color="black"))
    fig.update_layout(xaxis_tickangle=-45, margin=dict(l=50, r=50, t=50, b=120))
    return fig

# 5) Callback para atualizar o Mapa de Carregamento Detalhado
@dash.callback(
    Output("map-carregamento", "figure"),
    Input("store-producao", "data"),
    Input("operacao-filter", "value")
)
def update_map_carregamento_detalhado(df_producao_records, operacao_filter):
    period_start, period_end = get_current_shift_period()
    df = pd.DataFrame(df_producao_records or [])
    df = get_filtered_data_producao(period_start, period_end, operacao_filter, df=df)

    if df.empty:
        return no_data_fig("Mapa de Carregamento")

    df = df.dropna(subset=["latitude_carregamento", "longitude_carregamento"])
    if df.empty:
        return no_data_fig("Mapa de Carregamento")

    fig = px.scatter_mapbox(
        df,
        lat="latitude_carregamento",
        lon="longitude_carregamento",
        color="nome_equipamento_utilizado",
        hover_name="nome_equipamento_utilizado",
        hover_data={"latitude_carregamento": True, "longitude_carregamento": True},
        title="Mapa de Carregamento (Detalhado)",
        zoom=15,
        height=400
    )
    fig.update_traces(
        marker=dict(size=10, opacity=0.8),
        hovertemplate="<b>%{hovertext}</b><br>Lat: %{lat:.4f}<br>Lon: %{lon:.4f}<extra></extra>"
    )
    center_lat = df["latitude_carregamento"].mean()
    center_lon = df["longitude_carregamento"].mean()
    fig.update_layout(common_map_layout(center_lat, center_lon))
    return fig

# 6) Callback para atualizar o Mapa de Basculamento
@dash.callback(
    Output("map-basculamento", "figure"),
    Input("store-producao", "data"),
    Input("operacao-filter", "value")
)
def update_map_basculamento_detalhado(df_producao_records, operacao_filter):
    period_start, period_end = get_current_shift_period()
    df = pd.DataFrame(df_producao_records or [])
    df = get_filtered_data_producao(period_start, period_end, operacao_filter, df=df)
    if df.empty:
        return no_data_fig("Mapa de Basculamento")

    df = df.dropna(subset=["latitude_basculamento", "longitude_basculamento"])
    if df.empty:
        return no_data_fig("Mapa de Basculamento")

    fig = px.scatter_mapbox(
        df,
        lat="latitude_basculamento",
        lon="longitude_basculamento",
        color="nome_destino",
        hover_name="nome_destino",
        hover_data={"volume": True, "latitude_basculamento": False, "longitude_basculamento": False},
        title="Mapa de Basculamento",
        zoom=15,
        height=400
    )
    fig.update_traces(marker=dict(size=8, opacity=0.8))
    center_lat = df["latitude_basculamento"].mean()
    center_lon = df["longitude_basculamento"].mean()
    fig.update_layout(common_map_layout(center_lat, center_lon))
    return fig

# 7) Callback para atualizar o Gráfico de Barras (Volume)
@dash.callback(
    Output("volume-bar", "figure"),
    Input("store-producao", "data"),
    Input("operacao-filter", "value")
)
def update_volume_bar(df_producao_records, operacao_filter):
    period_start, period_end = get_current_shift_period()
    df = pd.DataFrame(df_producao_records or [])
    df = get_filtered_data_producao(period_start, period_end, operacao_filter, df=df)

    if df.empty or "volume" not in df.columns:
        return no_data_fig("Volume: Sem dados")

    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    df = df.dropna(subset=["volume"])
    if df.empty:
        return no_data_fig("Volume: Sem dados após filtros")

    df_group = df.groupby("nome_equipamento_utilizado", as_index=False)["volume"].sum()
    df_group = df_group.sort_values("volume", ascending=False)

    fig = px.bar(
        df_group,
        x="nome_equipamento_utilizado",
        y="volume",
        title="Volume Total por Escavadeira",
        labels={"nome_equipamento_utilizado": "Escavadeira", "volume": "Volume Total"}
    )
    fig.update_layout(
        template="plotly_white",
        title_x=0.5,
        margin=dict(l=40, r=40, t=60, b=80),
        font=dict(family="Arial, sans-serif", size=14),
        xaxis_tickangle=-45
    )
    return fig

# 8) Callback para atualizar a tabela de detalhamento operacional
@dash.callback(
    Output("table-data", "data"),
    Input("store-producao", "data"),
    Input("operacao-filter", "value")
)
def update_table(df_producao_records, operacao_filter):
    period_start, period_end = get_current_shift_period()
    df = pd.DataFrame(df_producao_records or [])
    df = get_filtered_data_producao(period_start, period_end, operacao_filter, df=df)

    if df.empty:
        return no_data_table()

    required_cols = [
        'nome_origem', 'nome_destino', 'tempo_ciclo_minuto', 'volume',
        'dmt_mov_cheio', 'dmt_mov_vazio', 'velocidade_media_cheio', 'velocidade_media_vazio'
    ]
    for col in required_cols:
        if col not in df.columns:
            df[col] = None

    def weighted_avg(series, weights):
        total_weight = weights.sum()
        return (series * weights).sum() / total_weight if total_weight != 0 else series.mean()

    grouped = df.groupby("nome_origem").apply(
        lambda g: pd.Series({
            "nome_destino": g["nome_destino"].iloc[0] if "nome_destino" in g.columns else None,
            "tempo_ciclo_minuto": g["tempo_ciclo_minuto"].mean(),
            "volume": g["volume"].sum(),
            "dmt_mov_cheio": weighted_avg(g["dmt_mov_cheio"], g["volume"]),
            "dmt_mov_vazio": weighted_avg(g["dmt_mov_vazio"], g["volume"]),
            "velocidade_media_cheio": g["velocidade_media_cheio"].mean(),
            "velocidade_media_vazio": g["velocidade_media_vazio"].mean()
        })
    ).reset_index()

    for col in ["tempo_ciclo_minuto", "dmt_mov_cheio", "dmt_mov_vazio",
                "velocidade_media_cheio", "velocidade_media_vazio"]:
        grouped[col] = grouped[col].round(2)
    grouped["volume"] = grouped["volume"].round(2)

    return grouped.to_dict("records")

# 9) Callback para atualizar o informativo de caminhões
@dash.callback(
    Output("truck-info", "children"),
    Input("store-producao", "data"),
    Input("store-hora", "data"),
    Input("operacao-filter", "value")
)
def update_truck_info(df_producao_records, df_hora_records, operacao_filter):
    period_start, period_end = get_current_shift_period()
    df_prod_period = pd.DataFrame(df_producao_records or [])
    df_prod_period = get_filtered_data_producao(period_start, period_end, operacao_filter, df=df_prod_period)

    if df_prod_period.empty:
        return "Total Caminhões Indicados: 0 / Máximo em Operação: 48"

    df_hora = pd.DataFrame(df_hora_records or [])
    df_hora = get_filtered_data_hora(period_start, period_end, df=df_hora)

    merged_data = compute_truck_stats(df_prod_period, df_hora)
    if merged_data.empty:
        return "Total Caminhões Indicados: 0 / Máximo em Operação: 48"

    total_trucks = merged_data["trucks_needed"].sum()
    return f"Total Caminhões Indicados: {total_trucks} / Máximo em Operação: 48"

# =============================================================================
# EXECUÇÃO STANDALONE (Para testes independentes, descomente se necessário)
# =============================================================================
"""
if __name__ == "__main__":
    app = dash.Dash(__name__, external_stylesheets=[dbc.themes.LUX])
    app.title = "Relatório 1 - Ciclo Operacional"
    app.layout = layout
    app.run_server(debug=True)
"""
