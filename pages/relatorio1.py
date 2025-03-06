import math 
import logging
from datetime import datetime, timedelta

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import dash_table
import plotly.express as px
import pandas as pd

# -------------------- Configuração de Logging --------------------
logging.basicConfig(
    level=logging.INFO,
    filename="dashboard.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Constante para o período de busca (últimas 2 horas)
SEARCH_PERIOD_HOURS = 2

# Token do Mapbox (necessário para estilos que não sejam "open-street-map")
MAPBOX_TOKEN = ""  # Substitua por seu token se disponível

# -------------------- Importação de Função do Módulo DB --------------------
from db import query_to_df

# -------------------- Funções Auxiliares --------------------
def get_search_period():
    """Retorna o período adaptativo: últimas SEARCH_PERIOD_HOURS horas."""
    now = datetime.now()
    period_start = now - timedelta(hours=SEARCH_PERIOD_HOURS)
    return period_start, now

def no_data_fig(title):
    """Retorna uma figura padrão informando ausência de dados."""
    df_empty = pd.DataFrame({"x": [], "y": []})
    fig = px.bar(df_empty, x="x", y="y", title=title)
    fig.update_layout(
        xaxis={'visible': False},
        yaxis={'visible': False},
        annotations=[{
            "text": "Sem dados para o período selecionado",
            "xref": "paper",
            "yref": "paper",
            "showarrow": False,
            "font": {"size": 16}
        }],
        margin=dict(l=50, r=50, t=50, b=120)
    )
    return fig

def no_data_table():
    """Retorna uma mensagem padrão para a tabela quando não houver dados."""
    return [{"Mensagem": "Sem dados para o período selecionado"}]

def execute_query(query):
    """Executa a query e trata exceções, retornando um DataFrame."""
    try:
        df = query_to_df(query)
        return df
    except Exception as e:
        logging.error(f"Erro na execução da query: {e}")
        return pd.DataFrame()

def common_map_layout(center_lat, center_lon, map_style):
    """Retorna um layout padronizado para os mapas."""
    return {
        "mapbox_style": map_style,
        "mapbox_accesstoken": MAPBOX_TOKEN if MAPBOX_TOKEN else None,
        "mapbox": {
            "center": {"lat": center_lat, "lon": center_lon},
            "zoom": 15,
            "pitch": 30
        },
        "uirevision": "constant",
        "margin": {"r": 0, "t": 60, "l": 0, "b": 0},
        "title_font": {"size": 20, "color": "black"},
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 0.01,
            "xanchor": "right",
            "x": 0.99,
            "title": ""
        }
    }

# -------------------- Layout do Dashboard --------------------
navbar = dbc.NavbarSimple(
    brand="Dashboard Operacional",
    color="primary",
    dark=True,
    fluid=True,
)

# Componente de escolha de estilo do mapa com ajustes visuais
map_style_selector = html.Div([
    dbc.Label("Estilo do Mapa", className="mb-1", style={"fontWeight": "bold", "fontSize": "16px"}),
    dbc.RadioItems(
        id="map-style-selector",
        options=[
            {"label": "Padrão", "value": "open-street-map"},
            {"label": "Satélite", "value": "satellite-streets"},
        ],
        value="open-street-map",
        inline=True,
    ),
], style={"padding": "10px", "backgroundColor": "#f8f9fa", "borderRadius": "5px"})

layout = dbc.Container([
    navbar,
    
    # Linha: Filtros e Botão de Atualizar
    dbc.Row([
        dbc.Col(
            dcc.Dropdown(
                id="operacao-filter",
                placeholder="Filtrar por Operação",
                multi=True,
                options=[],
                persistence=True,
                persistence_type="session",
                style={"fontSize": "16px"}
            ),
            width=8
        ),
        dbc.Col(
            dbc.Button("Atualizar", id="btn-atualizar", color="primary", className="w-100", style={"fontSize": "16px"}),
            width=2
        ),
        dbc.Col(
            map_style_selector,
            width=2
        )
    ], className="mb-4", align="center"),
    
    # Linha: Caixa de Informação de Caminhões
    dbc.Row([
        dbc.Col(
            html.Div(id="truck-info", style={
                "fontSize": "24px",
                "fontWeight": "bold",
                "textAlign": "center",
                "padding": "10px",
                "backgroundColor": "#e9ecef",
                "borderRadius": "5px"
            }),
            width=12
        )
    ], className="mb-4"),
    
    # Linha: Gráfico principal - Caminhões Necessários por Escavadeira
    dbc.Row([
        dbc.Col(
            dbc.Card([
                dbc.CardHeader(html.H5("Caminhões Necessários por Escavadeira", className="mb-0")),
                dbc.CardBody(
                    dcc.Loading(
                        dcc.Graph(id="truck-cards", config={"displayModeBar": True}),
                        type="default"
                    )
                )
            ], className="shadow mb-4")
        )
    ]),
    
    # Linha: Gráficos 3D e Volume (lado a lado)
    dbc.Row([
        dbc.Col(
            dbc.Card([
                dbc.CardHeader(html.H5("Gráfico de Dispersão 3D", className="mb-0")),
                dbc.CardBody(
                    dcc.Loading(
                        dcc.Graph(id="scatter-3d", config={"displayModeBar": True}),
                        type="default"
                    )
                )
            ], className="shadow mb-4"),
            width=6
        ),
        dbc.Col(
            dbc.Card([
                dbc.CardHeader(html.H5("Volume por Escavadeira", className="mb-0")),
                dbc.CardBody(
                    dcc.Loading(
                        dcc.Graph(id="volume-bar", config={"displayModeBar": True}),
                        type="default"
                    )
                )
            ], className="shadow mb-4"),
            width=6
        )
    ]),
    
    # Linha: Mapas (Carregamento e Basculamento) – layout consistente
    dbc.Row([
        dbc.Col(
            dbc.Card([
                dbc.CardHeader(html.H5("Mapa de Carregamento (Detalhado)", className="mb-0")),
                dbc.CardBody(
                    dcc.Loading(
                        dcc.Graph(id="map-carregamento", config={"displayModeBar": True}),
                        type="default"
                    )
                )
            ], className="shadow mb-4"),
            width=6
        ),
        dbc.Col(
            dbc.Card([
                dbc.CardHeader(html.H5("Mapa de Basculamento", className="mb-0")),
                dbc.CardBody(
                    dcc.Loading(
                        dcc.Graph(id="map-basculamento", config={"displayModeBar": True}),
                        type="default"
                    )
                )
            ], className="shadow mb-4"),
            width=6
        )
    ]),
    
    # Linha: Tabela de Detalhamento Operacional
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
                        columns=[{"name": col, "id": col, "presentation": "markdown"}
                                 for col in [
                                     'nome_origem', 'nome_destino', 'tempo_ciclo_minuto', 'volume',
                                     'dmt_mov_cheio', 'dmt_mov_vazio', 'velocidade_media_cheio', 'velocidade_media_vazio'
                                 ]],
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
                            {'if': {'filter_query': '{velocidade_media_cheio} >= 15',
                                    'column_id': 'velocidade_media_cheio'},
                             'color': 'green', 'fontWeight': 'bold'},
                            {'if': {'filter_query': '{velocidade_media_cheio} < 15',
                                    'column_id': 'velocidade_media_cheio'},
                             'color': 'red', 'fontWeight': 'bold'},
                            {'if': {'filter_query': '{velocidade_media_vazio} >= 16',
                                    'column_id': 'velocidade_media_vazio'},
                             'color': 'green', 'fontWeight': 'bold'},
                            {'if': {'filter_query': '{velocidade_media_vazio} < 16',
                                    'column_id': 'velocidade_media_vazio'},
                             'color': 'red', 'fontWeight': 'bold'},
                            {'if': {'state': 'active'},
                             'backgroundColor': '#f1f1f1', 'border': '1px solid #ddd'}
                        ],
                        page_size=10,
                        style_table={'overflowX': 'auto', 'border': '1px solid #ddd', 'borderRadius': '5px'}
                    )
                )
            ], className="shadow mb-4")
        )
    ]),
    
    # Intervalo de atualização dos dados: 25 minutos
    dcc.Interval(id="interval-update", interval=25*60*1000, n_intervals=0)
], fluid=True)

# -------------------- Callbacks --------------------

###############################################
# CALLBACK: Atualiza Dropdown (nome_operacao)
###############################################
@dash.callback(
    Output("operacao-filter", "options"),
    Input("interval-update", "n_intervals")
)
def update_dropdown(n_intervals):
    now = datetime.now()
    query = (
        f"EXEC dw_sdp_mt_fas..usp_fato_producao '{now.strftime('%d/%m/%Y')}', '{now.strftime('%d/%m/%Y')}'"
    )
    df = execute_query(query)
    if not df.empty:
        df["dt_registro_turno"] = pd.to_datetime(df["dt_registro_turno"], errors="coerce")
        df_day = df[df["dt_registro_turno"].dt.date == now.date()]
        if "nome_operacao" in df_day.columns:
            ops = sorted(df_day["nome_operacao"].dropna().unique())
        else:
            ops = []
    else:
        ops = []
    return [{"label": op, "value": op} for op in ops]

###############################################
# CALLBACK: Botão de Atualizar (Forçar Atualização)
###############################################
@dash.callback(
    Output("interval-update", "n_intervals"),
    Input("btn-atualizar", "n_clicks"),
    prevent_initial_call=True
)
def manual_update(n_clicks):
    return 0

###############################################
# CALLBACK: Bubble Chart – Caminhões Necessários por Escavadeira
###############################################
@dash.callback(
    Output("truck-cards", "figure"),
    [Input("interval-update", "n_intervals"),
     Input("operacao-filter", "value")]
)
def update_truck_chart(n_intervals, operacao_filter):
    start, now = get_search_period()
    query_prod = (
        f"EXEC dw_sdp_mt_fas..usp_fato_producao '{start.strftime('%d/%m/%Y %H:%M:%S')}', '{now.strftime('%d/%m/%Y %H:%M:%S')}'"
    )
    df_prod = execute_query(query_prod)
    if df_prod.empty:
        return no_data_fig("Caminhões Necessários por Escavadeira")
    
    df_prod["dt_registro_fim"] = pd.to_datetime(df_prod["dt_registro_fim"], errors="coerce")
    df_prod["dt_registro_turno"] = pd.to_datetime(df_prod["dt_registro_turno"], errors="coerce")
    df_prod_day = df_prod[df_prod["dt_registro_turno"].dt.date == now.date()]
    df_prod_period = df_prod_day[(df_prod_day["dt_registro_fim"] >= start) & (df_prod_day["dt_registro_fim"] <= now)]
    if operacao_filter:
        df_prod_period = df_prod_period[df_prod_period["nome_operacao"].isin(operacao_filter)]
    
    if df_prod_period.empty:
        return no_data_fig("Caminhões Necessários por Escavadeira")
    
    prod_grp = df_prod_period.groupby("nome_equipamento_utilizado").agg(
        avg_cycle=("tempo_ciclo_minuto", "mean")
    ).reset_index()
    prod_grp["avg_cycle"] = prod_grp["avg_cycle"].round(2)
    
    base = df_prod_period[["cod_viagem", "nome_equipamento_utilizado"]].drop_duplicates()
    
    query_hora = (
        f"EXEC dw_sdp_mt_fas..usp_fato_hora '{start.strftime('%d/%m/%Y %H:%M:%S')}', '{now.strftime('%d/%m/%Y %H:%M:%S')}'"
    )
    df_hora = execute_query(query_hora)
    if not df_hora.empty:
        if "dt_registro_turno" in df_hora.columns:
            df_hora["dt_registro_turno"] = pd.to_datetime(df_hora["dt_registro_turno"], errors="coerce")
            df_hora = df_hora[df_hora["dt_registro_turno"].dt.date == now.date()]
        elif "dt_registro" in df_hora.columns:
            df_hora["dt_registro"] = pd.to_datetime(df_hora["dt_registro"], errors="coerce")
            df_hora = df_hora[df_hora["dt_registro"].dt.date == now.date()]
        df_hora = df_hora[df_hora["nome_estado"].isin(["Carregando", "Manobra no Carregamento"])]
    else:
        df_hora = pd.DataFrame()
    
    cod_list = df_prod_period["cod_viagem"].unique().tolist()
    if not df_hora.empty:
        df_hora = df_hora[df_hora["cod_viagem"].isin(cod_list)]
    df_join = pd.merge(base, df_hora, on="cod_viagem", how="left")
    
    def compute_avg(grp, state, default):
        sub = grp[grp["nome_estado"] == state]
        if not sub.empty:
            avg = sub["tempo_minuto"].mean()
            if state == "Carregando":
                return avg if 1 <= avg <= 10 else default
            elif state == "Manobra no Carregamento":
                return avg if (avg >= 5/60) and (avg <= 5) else default
        return default
    
    if not df_join.empty:
        trip_stats = df_join.groupby("cod_viagem").apply(
            lambda g: pd.Series({
                "avg_carregando": compute_avg(g, "Carregando", 3.5),
                "avg_manobra": compute_avg(g, "Manobra no Carregamento", 1)
            })
        ).reset_index()
    else:
        trip_stats = pd.DataFrame()
    
    if trip_stats.empty:
        return no_data_fig("Caminhões Necessários por Escavadeira")
    
    trip_stats = trip_stats.merge(base, on="cod_viagem", how="left")
    op_grp = trip_stats.groupby("nome_equipamento_utilizado").agg(
        avg_carregando=("avg_carregando", "mean"),
        avg_manobra=("avg_manobra", "mean")
    ).reset_index()
    op_grp["avg_carregando"] = op_grp["avg_carregando"].round(2)
    op_grp["avg_manobra"] = op_grp["avg_manobra"].round(2)
    
    merged_data = pd.merge(prod_grp, op_grp, on="nome_equipamento_utilizado", how="inner")
    
    def calc_trucks(row):
        denom = row["avg_carregando"] + row["avg_manobra"]
        return math.ceil(row["avg_cycle"] / denom) if denom > 0 else 0
    
    merged_data["trucks_needed"] = merged_data.apply(calc_trucks, axis=1)
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
        labels={
            "escavadeira": "Escavadeira",
            "avg_cycle": "Tempo Médio de Ciclo (min)",
            "trucks_needed": "Caminhões Necessários"
        },
        size_max=100,
        color_continuous_scale="Viridis",
        hover_data={"avg_cycle": True, "trucks_needed": True, "escavadeira": False}
    )
    fig.update_traces(textposition="middle center", textfont=dict(size=16, color="black"))
    fig.update_layout(xaxis_tickangle=-45, margin=dict(l=50, r=50, t=50, b=120))
    return fig

###############################################
# CALLBACK: Mapa de Carregamento (Detalhado)
###############################################
@dash.callback(
    Output("map-carregamento", "figure"),
    [Input("interval-update", "n_intervals"),
     Input("operacao-filter", "value"),
     Input("map-style-selector", "value")]
)
def update_map_carregamento_detalhado(n_intervals, operacao_filter, map_style):
    if map_style == "satellite-streets" and not MAPBOX_TOKEN:
        logging.info("Token do Mapbox não fornecido; utilizando 'open-street-map'.")
        map_style = "open-street-map"
    
    period_start, now = get_search_period()
    query = (
        f"EXEC dw_sdp_mt_fas..usp_fato_producao '{period_start.strftime('%d/%m/%Y %H:%M:%S')}', "
        f"'{now.strftime('%d/%m/%Y %H:%M:%S')}'"
    )
    df = execute_query(query)
    if df.empty:
        logging.info("Nenhum dado retornado da query para Carregamento.")
        return no_data_fig("Mapa de Carregamento")
    
    df["dt_registro_fim"] = pd.to_datetime(df["dt_registro_fim"], errors="coerce")
    df_period = df[(df["dt_registro_fim"] >= period_start) & (df["dt_registro_fim"] <= now)]
    if operacao_filter:
        df_period = df_period[df_period["nome_operacao"].isin(operacao_filter)]
    if df_period.empty:
        return no_data_fig("Mapa de Carregamento")
    
    df_period = df_period.dropna(subset=["latitude_carregamento", "longitude_carregamento"])
    if df_period.empty:
        logging.info("Nenhum registro com coordenadas válidas para Carregamento.")
        return no_data_fig("Mapa de Carregamento")
    
    fig = px.scatter_mapbox(
        df_period,
        lat="latitude_carregamento",
        lon="longitude_carregamento",
        color="nome_equipamento_utilizado",
        hover_name="nome_equipamento_utilizado",
        hover_data={"latitude_carregamento": True, "longitude_carregamento": True},
        title="Mapa de Carregamento (Detalhado)",
        zoom=15,
        height=500
    )
    fig.update_traces(
        marker=dict(size=10, opacity=0.8),
        hovertemplate="<b>%{hovertext}</b><br>Lat: %{lat:.4f}<br>Lon: %{lon:.4f}<extra></extra>"
    )
    center_lat = df_period["latitude_carregamento"].mean()
    center_lon = df_period["longitude_carregamento"].mean()
    fig.update_layout(common_map_layout(center_lat, center_lon, map_style))
    return fig

###############################################
# CALLBACK: Mapa de Basculamento – Exibe pontos individuais
###############################################
@dash.callback(
    Output("map-basculamento", "figure"),
    [Input("interval-update", "n_intervals"),
     Input("operacao-filter", "value"),
     Input("map-style-selector", "value")]
)
def update_map_basculamento_detalhado(n_intervals, operacao_filter, map_style):
    if map_style == "satellite-streets" and not MAPBOX_TOKEN:
        logging.info("Token do Mapbox não fornecido; utilizando 'open-street-map'.")
        map_style = "open-street-map"
    
    period_start, now = get_search_period()
    query = (
        f"EXEC dw_sdp_mt_fas..usp_fato_producao '{period_start.strftime('%d/%m/%Y %H:%M:%S')}', "
        f"'{now.strftime('%d/%m/%Y %H:%M:%S')}'"
    )
    df = execute_query(query)
    if df.empty:
        logging.info("Nenhum dado retornado da query para Basculamento.")
        return no_data_fig("Mapa de Basculamento")
    
    df["dt_registro_fim"] = pd.to_datetime(df["dt_registro_fim"], errors="coerce")
    df_period = df[(df["dt_registro_fim"] >= period_start) & (df["dt_registro_fim"] <= now)]
    if operacao_filter:
        df_period = df_period[df_period["nome_operacao"].isin(operacao_filter)]
    if df_period.empty:
        return no_data_fig("Mapa de Basculamento")
    
    df_period = df_period.dropna(subset=["latitude_basculamento", "longitude_basculamento"])
    if df_period.empty:
        logging.info("Nenhum registro com coordenadas válidas para Basculamento.")
        return no_data_fig("Mapa de Basculamento")
    
    # Exibe TODOS os pontos individuais sem agrupamento, usando "nome_destino" para a legenda
    fig = px.scatter_mapbox(
        df_period,
        lat="latitude_basculamento",
        lon="longitude_basculamento",
        color="nome_destino",
        hover_name="nome_destino",
        hover_data={"volume": True, "latitude_basculamento": False, "longitude_basculamento": False},
        title="Mapa de Basculamento",
        zoom=15,
        height=500
    )
    fig.update_traces(marker=dict(size=8, opacity=0.8))
    center_lat = df_period["latitude_basculamento"].mean()
    center_lon = df_period["longitude_basculamento"].mean()
    fig.update_layout(common_map_layout(center_lat, center_lon, map_style))
    return fig

###############################################
# CALLBACK: Gráfico de Dispersão 3D
###############################################
@dash.callback(
    Output("scatter-3d", "figure"),
    [Input("interval-update", "n_intervals"),
     Input("operacao-filter", "value")]
)
def update_scatter_3d(n_intervals, operacao_filter):
    period_start, now = get_search_period()
    query = (
        f"EXEC dw_sdp_mt_fas..usp_fato_producao '{period_start.strftime('%d/%m/%Y %H:%M:%S')}', "
        f"'{now.strftime('%d/%m/%Y %H:%M:%S')}'"
    )
    df = execute_query(query)
    if df.empty:
        return no_data_fig("Gráfico 3D: Sem dados")
    
    df["latitude_carregamento"] = pd.to_numeric(df["latitude_carregamento"], errors="coerce")
    df["longitude_carregamento"] = pd.to_numeric(df["longitude_carregamento"], errors="coerce")
    df["tempo_ciclo_minuto"] = pd.to_numeric(df["tempo_ciclo_minuto"], errors="coerce")
    
    df = df.dropna(subset=["latitude_carregamento", "longitude_carregamento", "tempo_ciclo_minuto"])
    if operacao_filter:
        df = df[df["nome_operacao"].isin(operacao_filter)]
    if df.empty:
        return no_data_fig("Gráfico 3D: Sem dados após filtros")
    
    fig = px.scatter_3d(
        df,
        x="latitude_carregamento",
        y="longitude_carregamento",
        z="tempo_ciclo_minuto",
        color="nome_operacao",
        hover_data=["nome_origem", "nome_destino"],
        title="Gráfico de Dispersão 3D: Carregamento e Tempo de Ciclo"
    )
    fig.update_layout(margin=dict(l=0, r=0, t=50, b=0))
    return fig

###############################################
# CALLBACK: Gráfico de Volume por Escavadeira
###############################################
@dash.callback(
    Output("volume-bar", "figure"),
    [Input("interval-update", "n_intervals"),
     Input("operacao-filter", "value")]
)
def update_volume_bar(n_intervals, operacao_filter):
    period_start, now = get_search_period()
    query = (
        f"EXEC dw_sdp_mt_fas..usp_fato_producao '{period_start.strftime('%d/%m/%Y %H:%M:%S')}', "
        f"'{now.strftime('%d/%m/%Y %H:%M:%S')}'"
    )
    df = execute_query(query)
    if df.empty:
        return no_data_fig("Volume: Sem dados")
    
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    df = df.dropna(subset=["volume"])
    if operacao_filter:
        df = df[df["nome_operacao"].isin(operacao_filter)]
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
    fig.update_layout(margin=dict(l=50, r=50, t=50, b=120))
    return fig

###############################################
# CALLBACK: Tabela de Detalhamento Operacional
###############################################
@dash.callback(
    Output("table-data", "data"),
    [Input("interval-update", "n_intervals"),
     Input("operacao-filter", "value")]
)
def update_table(n_intervals, operacao_filter):
    period_start, now = get_search_period()
    query = (
        f"EXEC dw_sdp_mt_fas..usp_fato_producao '{period_start.strftime('%d/%m/%Y %H:%M:%S')}', "
        f"'{now.strftime('%d/%m/%Y %H:%M:%S')}'"
    )
    df = execute_query(query)
    if df.empty:
        return no_data_table()
    
    df["dt_registro_fim"] = pd.to_datetime(df["dt_registro_fim"], errors="coerce")
    df_period = df[(df["dt_registro_fim"] >= period_start) & (df["dt_registro_fim"] <= now)]
    if operacao_filter:
        df_period = df_period[df_period["nome_operacao"].isin(operacao_filter)]
    if df_period.empty:
        return no_data_table()
    
    required_cols = ['nome_origem', 'nome_destino', 'tempo_ciclo_minuto', 'volume', 
                     'dmt_mov_cheio', 'dmt_mov_vazio', 'velocidade_media_cheio', 'velocidade_media_vazio']
    for col in required_cols:
        if col not in df_period.columns:
            df_period[col] = None

    def weighted_avg(series, weights):
        total_weight = weights.sum()
        return (series * weights).sum() / total_weight if total_weight != 0 else series.mean()

    grouped = df_period.groupby("nome_origem").apply(
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
    
    return grouped.to_dict('records')

###############################################
# CALLBACK: Caixa de Informação de Caminhões
###############################################
@dash.callback(
    Output("truck-info", "children"),
    [Input("interval-update", "n_intervals"),
     Input("operacao-filter", "value")]
)
def update_truck_info(n_intervals, operacao_filter):
    start, now = get_search_period()
    query_prod = (
        f"EXEC dw_sdp_mt_fas..usp_fato_producao '{start.strftime('%d/%m/%Y %H:%M:%S')}', "
        f"'{now.strftime('%d/%m/%Y %H:%M:%S')}'"
    )
    df_prod = execute_query(query_prod)
    if df_prod.empty:
        return "Total Caminhões Indicados: 0 / Máximo em Operação: 48"
    
    df_prod["dt_registro_fim"] = pd.to_datetime(df_prod["dt_registro_fim"], errors="coerce")
    df_prod["dt_registro_turno"] = pd.to_datetime(df_prod["dt_registro_turno"], errors="coerce")
    df_prod_day = df_prod[df_prod["dt_registro_turno"].dt.date == now.date()]
    df_prod_period = df_prod_day[(df_prod_day["dt_registro_fim"] >= start) & (df_prod_day["dt_registro_fim"] <= now)]
    if operacao_filter:
        df_prod_period = df_prod_period[df_prod_period["nome_operacao"].isin(operacao_filter)]
    if df_prod_period.empty:
        return "Total Caminhões Indicados: 0 / Máximo em Operação: 48"
    
    prod_grp = df_prod_period.groupby("nome_equipamento_utilizado").agg(
        avg_cycle=("tempo_ciclo_minuto", "mean")
    ).reset_index()
    prod_grp["avg_cycle"] = prod_grp["avg_cycle"].round(2)
    base = df_prod_period[["cod_viagem", "nome_equipamento_utilizado"]].drop_duplicates()
    query_hora = (
        f"EXEC dw_sdp_mt_fas..usp_fato_hora '{start.strftime('%d/%m/%Y %H:%M:%S')}', "
        f"'{now.strftime('%d/%m/%Y %H:%M:%S')}'"
    )
    df_hora = execute_query(query_hora)
    if not df_hora.empty:
        if "dt_registro_turno" in df_hora.columns:
            df_hora["dt_registro_turno"] = pd.to_datetime(df_hora["dt_registro_turno"], errors="coerce")
            df_hora = df_hora[df_hora["dt_registro_turno"].dt.date == now.date()]
        elif "dt_registro" in df_hora.columns:
            df_hora["dt_registro"] = pd.to_datetime(df_hora["dt_registro"], errors="coerce")
            df_hora = df_hora[df_hora["dt_registro"].dt.date == now.date()]
        df_hora = df_hora[df_hora["nome_estado"].isin(["Carregando", "Manobra no Carregamento"])]
    else:
        df_hora = pd.DataFrame()
    cod_list = df_prod_period["cod_viagem"].unique().tolist()
    if not df_hora.empty:
        df_hora = df_hora[df_hora["cod_viagem"].isin(cod_list)]
    df_join = pd.merge(base, df_hora, on="cod_viagem", how="left")
    
    def compute_avg(grp, state, default):
        sub = grp[grp["nome_estado"] == state]
        if not sub.empty:
            avg = sub["tempo_minuto"].mean()
            if state == "Carregando":
                return avg if 1 <= avg <= 10 else default
            elif state == "Manobra no Carregamento":
                return avg if (avg >= 5/60) and (avg <= 5) else default
        return default
    
    if not df_join.empty:
        trip_stats = df_join.groupby("cod_viagem").apply(
            lambda g: pd.Series({
                "avg_carregando": compute_avg(g, "Carregando", 3.5),
                "avg_manobra": compute_avg(g, "Manobra no Carregamento", 1)
            })
        ).reset_index()
    else:
        trip_stats = pd.DataFrame()
    
    if trip_stats.empty:
        total_trucks = 0
    else:
        trip_stats = trip_stats.merge(base, on="cod_viagem", how="left")
        op_grp = trip_stats.groupby("nome_equipamento_utilizado").agg(
            avg_carregando=("avg_carregando", "mean"),
            avg_manobra=("avg_manobra", "mean")
        ).reset_index()
        op_grp["avg_carregando"] = op_grp["avg_carregando"].round(2)
        op_grp["avg_manobra"] = op_grp["avg_manobra"].round(2)
        merged_data = pd.merge(prod_grp, op_grp, on="nome_equipamento_utilizado", how="inner")
    
        def calc_trucks(row):
            denom = row["avg_carregando"] + row["avg_manobra"]
            return math.ceil(row["avg_cycle"] / denom) if denom > 0 else 0
    
        merged_data["trucks_needed"] = merged_data.apply(calc_trucks, axis=1)
        total_trucks = merged_data["trucks_needed"].sum()
    
    return f"Total Caminhões Indicados: {total_trucks} / Máximo em Operação: 48"

# Expor a variável global layout para uso pelo app
layout = layout

# -------------------- Execução do App --------------------
if __name__ == '__main__':
    app = dash.Dash(__name__, external_stylesheets=[dbc.themes.LUX])
    app.title = "Dashboard Operacional"
    app.layout = layout
    app.run_server(debug=True)
