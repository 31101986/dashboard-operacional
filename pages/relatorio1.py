import math
import logging
import time
from datetime import datetime, timedelta
from functools import wraps

import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import dash_table
import plotly.express as px
import pandas as pd
import numpy as np

from config import TIMEZONE, PROJECTS_CONFIG, PROJECT_LABELS
from db import query_to_df

# Configuração do log
logging.basicConfig(
    level=logging.INFO,
    filename="dashboard.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTES
# =============================================================================
MAPBOX_TOKEN = ""
DEFAULT_MAP_STYLE = "open-street-map"
# Estilos gratuitos confiáveis no Plotly
MAP_STYLE_OPTIONS = [
    {"label": "Open Street Map", "value": "open-street-map"},
    {"label": "Carto Positron", "value": "carto-positron"},
    {"label": "Carto Darkmatter", "value": "carto-darkmatter"},
    {"label": "White Background", "value": "white-bg"}
]

# =============================================================================
# DECORADOR DE PROFILING
# =============================================================================
def profile_time(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = func(*args, **kwargs)
        t1 = time.perf_counter()
        logger.info(f"[Profile] {func.__name__} executed in {t1-t0:.4f} seconds")
        return result
    return wrapper

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================
def get_current_shift_period():
    now = datetime.now(TIMEZONE)
    shift_start = now.replace(hour=7, minute=0, second=0, microsecond=0)
    if now.hour < 7:
        shift_start -= timedelta(days=1)
    shift_end = shift_start + timedelta(days=1)
    return shift_start, shift_end

def no_data_fig(title):
    fig = px.bar(pd.DataFrame({"x": [], "y": []}), x="x", y="y", title=title)
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
    return [{"Mensagem": "Sem dados para o período selecionado"}]

def execute_query(query, projeto):
    try:
        return query_to_df(query, projeto=projeto)
    except Exception as e:
        logger.error(f"Erro na execução da query para projeto {projeto}: {e}")
        return pd.DataFrame()

def common_map_layout(center_lat, center_lon, map_style=DEFAULT_MAP_STYLE):
    return {
        "template": "plotly_white",
        "mapbox_style": map_style,
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
    if col_name not in df.columns or df.empty:
        return df
    df[col_name] = pd.to_datetime(df[col_name], errors="coerce")
    sample_tz = df[col_name].dt.tz
    if sample_tz is None:
        df[col_name] = df[col_name].dt.tz_localize(TIMEZONE)
    elif sample_tz != TIMEZONE:
        df[col_name] = df[col_name].dt.tz_convert(TIMEZONE)
    return df

@profile_time
def get_filtered_data_producao(period_start, period_end, operacao_filter=None, df=None, last_hours=None):
    if df is None or df.empty:
        return pd.DataFrame()
    df = localize_column_tz(df, "dt_registro_fim")
    mask = (df["dt_registro_fim"] >= period_start) & (df["dt_registro_fim"] < period_end)
    if last_hours is not None:
        now = datetime.now(TIMEZONE)
        time_threshold = now - timedelta(hours=last_hours)
        mask &= (df["dt_registro_fim"] >= time_threshold)
    if operacao_filter and "nome_operacao" in df.columns:
        mask &= df["nome_operacao"].isin(operacao_filter)
    return df[mask]

@profile_time
def get_filtered_data_hora(period_start, period_end, only_today=True, df=None, last_hours=None):
    if df is None or df.empty:
        return pd.DataFrame()
    df = localize_column_tz(df, "dt_registro_turno")
    mask = (df["dt_registro_turno"] >= period_start) & (df["dt_registro_turno"] < period_end)
    if last_hours is not None:
        now = datetime.now(TIMEZONE)
        time_threshold = now - timedelta(hours=last_hours)
        mask &= (df["dt_registro_turno"] >= time_threshold)
    mask &= df["nome_estado"].isin(["Carregando", "Manobra no Carregamento"])
    return df[mask]

@profile_time
def compute_truck_stats(df_prod_period, df_hora):
    if df_prod_period.empty:
        return pd.DataFrame(columns=["nome_equipamento_utilizado", "avg_cycle", "avg_carregando", "avg_manobra", "trucks_needed"])

    df_prod_period["tempo_ciclo_minuto"] = pd.to_numeric(df_prod_period["tempo_ciclo_minuto"], errors="coerce").clip(upper=60).replace(np.nan, 45)
    
    prod_grp = df_prod_period.groupby("nome_equipamento_utilizado")["tempo_ciclo_minuto"].mean().round(2).reset_index(name="avg_cycle")
    base = df_prod_period[["cod_viagem", "nome_equipamento_utilizado"]].drop_duplicates()

    if df_hora.empty:
        prod_grp = prod_grp.assign(avg_carregando=3.5, avg_manobra=1)
    else:
        cod_list = df_prod_period["cod_viagem"].unique()
        df_join = df_hora[df_hora["cod_viagem"].isin(cod_list)]
        if df_join.empty:
            prod_grp = prod_grp.assign(avg_carregando=3.5, avg_manobra=1)
        else:
            df_carregando = df_join[df_join["nome_estado"] == "Carregando"].groupby("cod_viagem")["tempo_minuto"].mean().rename("avg_carregando")
            df_carregando = df_carregando.where((df_carregando.between(1, 10)), 3.5)
            
            df_manobra = df_join[df_join["nome_estado"] == "Manobra no Carregamento"].groupby("cod_viagem")["tempo_minuto"].mean().rename("avg_manobra")
            df_manobra = df_manobra.where((df_manobra.between(5/60, 5)), 1)
            
            op = base.merge(df_carregando, on="cod_viagem", how="left").merge(df_manobra, on="cod_viagem", how="left")
            op = op.fillna({"avg_carregando": 3.5, "avg_manobra": 1})
            op_grp = op.groupby("nome_equipamento_utilizado")[["avg_carregando", "avg_manobra"]].mean().round(2).reset_index()
            prod_grp = prod_grp.merge(op_grp, on="nome_equipamento_utilizado", how="left").fillna({"avg_carregando": 3.5, "avg_manobra": 1})

    prod_grp["trucks_needed"] = np.ceil(prod_grp["avg_cycle"] / (prod_grp["avg_carregando"] + prod_grp["avg_manobra"])).replace([np.inf, -np.inf], 0)
    return prod_grp

# =============================================================================
# LAYOUT DO RELATÓRIO
# =============================================================================
navbar = dbc.Navbar(
    dbc.Container([
        dbc.NavbarBrand([
            html.I(className="fas fa-chart-line mr-2"),
            "Ciclo Operacional"
        ], href="/relatorio1", className="ms-2 d-flex align-items-center", style={"fontSize": "1.1rem"}),
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
    navbar,
    html.Div(
        id="rel1-no-project-message",
        children=html.P(
            "Selecione uma obra para visualizar os dados.",
            className="text-center my-4"
        )
    ),
    html.H3("Ciclo Operacional", className="text-center mt-4 mb-4", style={
        "fontFamily": "Arial, sans-serif",
        "fontSize": "1.6rem",
        "fontWeight": "500"
    }),
    dbc.Row([
        dbc.Col(
            dcc.Dropdown(
                id="operacao-filter",
                placeholder="Selecione as Operações",
                multi=True,
                options=[],
                persistence=True,
                persistence_type="session",
                style={
                    "fontSize": "0.9rem",
                    "borderRadius": "8px",
                    "backgroundColor": "#f8f9fa",
                    "padding": "4px"
                }
            ),
            width=12, sm=9
        ),
        dbc.Col(
            dbc.Button([
                html.I(className="fas fa-sync-alt mr-1"),
                "Atualizar"
            ], id="btn-atualizar", color="primary", className="w-100", style={
                "fontSize": "0.9rem",
                "borderRadius": "10px",
                "background": "linear-gradient(45deg, #007bff, #00aaff)",
                "transition": "all 0.3s",
                "padding": "6px 12px"
            }, title="Clique para atualizar os dados"),
            width=12, sm=3
        ),
    ], className="mb-3 align-items-center"),
    dbc.Row([
        dbc.Col(
            dbc.Card([
                dbc.CardBody(
                    html.Div(
                        id="truck-info",
                        style={
                            "fontSize": "1.2rem",
                            "fontWeight": "500",
                            "textAlign": "center",
                            "color": "#495057",
                            "fontFamily": "Arial, sans-serif"
                        }
                    ),
                    style={"padding": "0.8rem"}
                )
            ], style={
                "borderRadius": "12px",
                "background": "linear-gradient(90deg, #e9ecef, #f8f9fa)",
                "border": "none"
            }, className="shadow-md animate__animated animate__zoomIn"),
            width=12
        )
    ], className="mb-3"),
    dbc.Row([
        dbc.Col(
            dbc.Card([
                dbc.CardHeader(
                    html.H5("Caminhões Necessários por Escavadeira", className="mb-0", style={
                        "fontSize": "1.1rem",
                        "fontWeight": "500",
                        "fontFamily": "Arial, sans-serif"
                    }),
                    style={"background": "linear-gradient(90deg, #f8f9fa, #e9ecef)"}
                ),
                dbc.CardBody(
                    dcc.Loading(
                        dcc.Graph(
                            id="truck-cards",
                            config={"displayModeBar": True, "responsive": True},
                            style={"minHeight": "40vh"}
                        ),
                        type="default"
                    ),
                    style={"padding": "0.8rem"}
                )
            ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={
                "borderRadius": "12px",
                "border": "none"
            })
        )
    ]),
    dbc.Row([
        dbc.Col(
            dbc.Card([
                dbc.CardHeader(
                    html.H5("Volume por Escavadeira", className="mb-0", style={
                        "fontSize": "1.1rem",
                        "fontWeight": "500",
                        "fontFamily": "Arial, sans-serif"
                    }),
                    style={"background": "linear-gradient(90deg, #f8f9fa, #e9ecef)"}
                ),
                dbc.CardBody(
                    dcc.Loading(
                        dcc.Graph(
                            id="volume-bar",
                            config={"displayModeBar": True, "responsive": True},
                            style={"minHeight": "40vh"}
                        ),
                        type="default"
                    ),
                    style={"padding": "0.8rem"}
                )
            ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={
                "borderRadius": "12px",
                "border": "none"
            }),
            width=12
        )
    ]),
    # Dropdowns para seleção de estilo dos mapas
    dbc.Row([
        dbc.Col(
            dcc.Dropdown(
                id="map-carregamento-style",
                options=MAP_STYLE_OPTIONS,
                value=DEFAULT_MAP_STYLE,
                placeholder="Selecione o estilo do mapa",
                style={
                    "fontSize": "0.9rem",
                    "borderRadius": "8px",
                    "backgroundColor": "#f8f9fa",
                    "padding": "4px",
                    "marginBottom": "10px"
                }
            ),
            width=12, md=6
        ),
        dbc.Col(
            dcc.Dropdown(
                id="map-basculamento-style",
                options=MAP_STYLE_OPTIONS,
                value=DEFAULT_MAP_STYLE,
                placeholder="Selecione o estilo do mapa",
                style={
                    "fontSize": "0.9rem",
                    "borderRadius": "8px",
                    "backgroundColor": "#f8f9fa",
                    "padding": "4px",
                    "marginBottom": "10px"
                }
            ),
            width=12, md=6
        )
    ]),
    # Mapas lado a lado
    dbc.Row([
        dbc.Col(
            dbc.Card([
                dbc.CardHeader(
                    html.H5("Mapa de Carregamento (Detalhado)", className="mb-0", style={
                        "fontSize": "1.1rem",
                        "fontWeight": "500",
                        "fontFamily": "Arial, sans-serif"
                    }),
                    style={"background": "linear-gradient(90deg, #f8f9fa, #e9ecef)"}
                ),
                dbc.CardBody(
                    dcc.Loading(
                        dcc.Graph(
                            id="map-carregamento",
                            config={"displayModeBar": True, "responsive": True},
                            style={"minHeight": "35vh"}
                        ),
                        type="default"
                    ),
                    style={"padding": "0.8rem"}
                )
            ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={
                "borderRadius": "12px",
                "border": "none"
            }),
            width=12, md=6
        ),
        dbc.Col(
            dbc.Card([
                dbc.CardHeader(
                    html.H5("Mapa de Basculamento", className="mb-0", style={
                        "fontSize": "1.1rem",
                        "fontWeight": "500",
                        "fontFamily": "Arial, sans-serif"
                    }),
                    style={"background": "linear-gradient(90deg, #f8f9fa, #e9ecef)"}
                ),
                dbc.CardBody(
                    dcc.Loading(
                        dcc.Graph(
                            id="map-basculamento",
                            config={"displayModeBar": True, "responsive": True},
                            style={"minHeight": "35vh"}
                        ),
                        type="default"
                    ),
                    style={"padding": "0.8rem"}
                )
            ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={
                "borderRadius": "12px",
                "border": "none"
            }),
            width=12, md=6
        )
    ]),
    dbc.Row([
        dbc.Col(
            dbc.Card([
                dbc.CardHeader(
                    html.H5("Detalhamento Operacional do Dia", className="mb-0 text-white", style={
                        "fontSize": "1.1rem",
                        "fontWeight": "500",
                        "fontFamily": "Arial, sans-serif"
                    }),
                    style={"background": "linear-gradient(90deg, #343a40, #495057)"}
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
                        style_cell={
                            'textAlign': 'center',
                            'padding': '8px',
                            'fontFamily': 'Arial',
                            'fontSize': '0.9rem',
                            'border': '1px solid #e9ecef'
                        },
                        style_header={
                            'fontWeight': 'bold',
                            'background': 'linear-gradient(90deg, #343a40, #495057)',
                            'color': 'white',
                            'fontFamily': 'Arial',
                            'fontSize': '0.9rem',
                            'border': '1px solid #e9ecef'
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
                                'backgroundColor': '#f8f9fa',
                                'border': '1px solid #e9ecef'
                            }
                        ],
                        page_size=10,
                        style_table={
                            'overflowX': 'auto',
                            'border': '1px solid #e9ecef',
                            'borderRadius': '8px'
                        }
                    ),
                    style={"padding": "0.8rem"}
                )
            ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={
                "borderRadius": "12px",
                "border": "none"
            })
        )
    ]),
    dcc.Interval(id="interval-update", interval=5*60*1000, n_intervals=0),  # Ajustado para 5 minutos
    dcc.Store(id="store-producao"),
    dcc.Store(id="store-hora"),
], fluid=True)

# =============================================================================
# CALLBACKS
# =============================================================================
@dash.callback(
    [Output("store-producao", "data"),
     Output("store-hora", "data")],
    [Input("interval-update", "n_intervals"),
     Input("btn-atualizar", "n_clicks"),
     Input("projeto-store", "data")],
    prevent_initial_call=False
)
def fetch_data(n_intervals, n_clicks, projeto):
    logger.debug(f"[DEBUG] fetch_data disparado: n_intervals={n_intervals}, n_clicks={n_clicks}, projeto={projeto}")
    
    if not projeto or projeto not in PROJECTS_CONFIG:
        return [], []
    
    period_start, period_end = get_current_shift_period()
    query_prod = f"EXEC {PROJECTS_CONFIG[projeto]['database']}..usp_fato_producao '{period_start:%d/%m/%Y %H:%M:%S}', '{period_end:%d/%m/%Y %H:%M:%S}'"
    df_producao = execute_query(query_prod, projeto)
    
    query_hora = f"EXEC {PROJECTS_CONFIG[projeto]['database']}..usp_fato_hora '{period_start:%d/%m/%Y %H:%M:%S}', '{period_end:%d/%m/%Y %H:%M:%S}'"
    df_hora = execute_query(query_hora, projeto)
    
    # Forçar nova consulta a cada chamada, evitando cache
    logger.info(f"Consulta realizada às {datetime.now(TIMEZONE)} para projeto {projeto}")
    return df_producao.to_dict("records"), df_hora.to_dict("records")

@dash.callback(
    [Output("operacao-filter", "options"),
     Output("rel1-no-project-message", "style")],
    [Input("store-producao", "data"),
     Input("projeto-store", "data")]
)
def update_dropdown(df_producao_records, projeto):
    if not projeto or projeto not in PROJECTS_CONFIG:
        return [], {"display": "block", "textAlign": "center", "color": "#343a40", "fontSize": "1.2rem", "margin": "20px 0"}
    
    if not df_producao_records:
        return [], {"display": "none"}
    
    df = pd.DataFrame(df_producao_records)
    period_start, period_end = get_current_shift_period()
    df = get_filtered_data_producao(period_start, period_end, df=df)
    if df.empty or "nome_operacao" not in df.columns:
        return [], {"display": "none"}
    
    ops = sorted(df["nome_operacao"].dropna().unique())
    return [{"label": op, "value": op} for op in ops], {"display": "none"}

@dash.callback(
    Output("interval-update", "n_intervals"),
    Input("btn-atualizar", "n_clicks"),
    prevent_initial_call=True
)
def manual_update(n_clicks):
    return 0

@dash.callback(
    Output("truck-cards", "figure"),
    [Input("store-producao", "data"),
     Input("store-hora", "data"),
     Input("operacao-filter", "value"),
     Input("projeto-store", "data")]
)
def update_truck_chart(df_producao_records, df_hora_records, operacao_filter, projeto):
    if not projeto or projeto not in PROJECTS_CONFIG:
        return no_data_fig("Caminhões Necessários por Escavadeira")

    period_start, period_end = get_current_shift_period()
    # Filtrar dados das últimas 3 horas
    df_prod_period = get_filtered_data_producao(period_start, period_end, operacao_filter, pd.DataFrame(df_producao_records), last_hours=3)
    if df_prod_period.empty:
        return no_data_fig("Caminhões Necessários por Escavadeira (Últimas 3 Horas)")

    df_hora = get_filtered_data_hora(period_start, period_end, df=pd.DataFrame(df_hora_records), last_hours=3)
    merged_data = compute_truck_stats(df_prod_period, df_hora)
    if merged_data.empty:
        return no_data_fig("Caminhões Necessários por Escavadeira (Últimas 3 Horas)")

    merged_data = merged_data.rename(columns={"nome_equipamento_utilizado": "escavadeira"})
    fig = px.scatter(
        merged_data,
        x="escavadeira",
        y="avg_cycle",
        size="trucks_needed",
        color="trucks_needed",
        text="trucks_needed",
        title=f"Caminhões Necessários por Escavadeira (Últimas 3 Horas) - ({PROJECT_LABELS.get(projeto, 'Nenhuma obra selecionada')})",
        labels={"escavadeira": "Escavadeira", "avg_cycle": "Tempo Médio de Ciclo (min)", "trucks_needed": "Caminhões"},
        size_max=100,
        color_continuous_scale="Viridis",
        hover_data={"avg_cycle": True, "trucks_needed": True, "escavadeira": False}
    )
    fig.update_traces(textposition="middle center", textfont=dict(size=16, color="black"))
    fig.update_layout(xaxis_tickangle=-45, margin=dict(l=50, r=50, t=50, b=120))
    return fig

@dash.callback(
    Output("map-carregamento", "figure"),
    [Input("store-producao", "data"),
     Input("operacao-filter", "value"),
     Input("projeto-store", "data"),
     Input("map-carregamento-style", "value")]
)
def update_map_carregamento_detalhado(df_producao_records, operacao_filter, projeto, map_style):
    if not projeto or projeto not in PROJECTS_CONFIG:
        return no_data_fig("Mapa de Carregamento")

    period_start, period_end = get_current_shift_period()
    # Mapas devem carregar todos os dados do turno, sem filtro de últimas 3 horas
    df = get_filtered_data_producao(period_start, period_end, operacao_filter, pd.DataFrame(df_producao_records))
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
        title=f"Mapa de Carregamento (Detalhado) ({PROJECT_LABELS.get(projeto, 'Nenhuma obra selecionada')})",
        zoom=15,
        height=400
    )
    fig.update_traces(
        marker=dict(size=10, opacity=0.8),
        hovertemplate="<b>%{hovertext}</b><br>Lat: %{lat:.4f}<br>Lon: %{lon:.4f}<extra></extra>"
    )
    center_lat = df["latitude_carregamento"].mean()
    center_lon = df["longitude_carregamento"].mean()
    fig.update_layout(common_map_layout(center_lat, center_lon, map_style))
    return fig

@dash.callback(
    Output("map-basculamento", "figure"),
    [Input("store-producao", "data"),
     Input("operacao-filter", "value"),
     Input("projeto-store", "data"),
     Input("map-basculamento-style", "value")]
)
def update_map_basculamento_detalhado(df_producao_records, operacao_filter, projeto, map_style):
    if not projeto or projeto not in PROJECTS_CONFIG:
        return no_data_fig("Mapa de Basculamento")

    period_start, period_end = get_current_shift_period()
    # Mapas devem carregar todos os dados do turno, sem filtro de últimas 3 horas
    df = get_filtered_data_producao(period_start, period_end, operacao_filter, pd.DataFrame(df_producao_records))
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
        title=f"Mapa de Basculamento ({PROJECT_LABELS.get(projeto, 'Nenhuma obra selecionada')})",
        zoom=15,
        height=400
    )
    fig.update_traces(marker=dict(size=8, opacity=0.8))
    center_lat = df["latitude_basculamento"].mean()
    center_lon = df["longitude_basculamento"].mean()
    fig.update_layout(common_map_layout(center_lat, center_lon, map_style))
    return fig

@dash.callback(
    Output("volume-bar", "figure"),
    [Input("store-producao", "data"),
     Input("operacao-filter", "value"),
     Input("projeto-store", "data")]
)
def update_volume_bar(df_producao_records, operacao_filter, projeto):
    if not projeto or projeto not in PROJECTS_CONFIG:
        return no_data_fig("Volume: Sem dados")

    period_start, period_end = get_current_shift_period()
    # Filtrar dados das últimas 3 horas
    df = get_filtered_data_producao(period_start, period_end, operacao_filter, pd.DataFrame(df_producao_records), last_hours=3)
    if df.empty or "volume" not in df.columns:
        return no_data_fig("Volume: Sem dados (Últimas 3 Horas)")
    
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    df = df.dropna(subset=["volume"])
    if df.empty:
        return no_data_fig("Volume: Sem dados após filtros (Últimas 3 Horas)")
    
    df_group = df.groupby("nome_equipamento_utilizado")["volume"].sum().reset_index().sort_values("volume", ascending=False)
    fig = px.bar(
        df_group,
        x="nome_equipamento_utilizado",
        y="volume",
        title=f"Volume Total por Escavadeira (Últimas 3 Horas) - ({PROJECT_LABELS.get(projeto, 'Nenhuma obra selecionada')})",
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

@dash.callback(
    Output("table-data", "data"),
    [Input("store-producao", "data"),
     Input("operacao-filter", "value"),
     Input("projeto-store", "data")]
)
def update_table(df_producao_records, operacao_filter, projeto):
    if not projeto or projeto not in PROJECTS_CONFIG:
        return no_data_table()

    period_start, period_end = get_current_shift_period()
    # Filtrar dados das últimas 3 horas
    df = get_filtered_data_producao(period_start, period_end, operacao_filter, pd.DataFrame(df_producao_records), last_hours=3)
    if df.empty:
        return no_data_table()

    required_cols = [
        'nome_origem', 'nome_destino', 'tempo_ciclo_minuto', 'volume',
        'dmt_mov_cheio', 'dmt_mov_vazio', 'velocidade_media_cheio', 'velocidade_media_vazio'
    ]
    df = df.assign(**{col: np.nan for col in required_cols if col not in df.columns})

    total_volume = df.groupby("nome_origem")["volume"].sum()
    grouped = df.groupby("nome_origem").agg({
        "nome_destino": "first",
        "tempo_ciclo_minuto": "mean",
        "volume": "sum",
        "velocidade_media_cheio": "mean",
        "velocidade_media_vazio": "mean"
    }).reset_index()

    dmt_mov_cheio = (df["dmt_mov_cheio"] * df["volume"]).groupby(df["nome_origem"]).sum() / total_volume
    dmt_mov_vazio = (df["dmt_mov_vazio"] * df["volume"]).groupby(df["nome_origem"]).sum() / total_volume
    dmt_mov_cheio = dmt_mov_cheio.fillna(df.groupby("nome_origem")["dmt_mov_cheio"].mean())
    dmt_mov_vazio = dmt_mov_vazio.fillna(df.groupby("nome_origem")["dmt_mov_vazio"].mean())

    grouped["dmt_mov_cheio"] = dmt_mov_cheio.values
    grouped["dmt_mov_vazio"] = dmt_mov_vazio.values

    for col in ["tempo_ciclo_minuto", "dmt_mov_cheio", "dmt_mov_vazio", "velocidade_media_cheio", "velocidade_media_vazio"]:
        grouped[col] = grouped[col].round(2)
    grouped["volume"] = grouped["volume"].round(2)

    return grouped.to_dict("records")

@dash.callback(
    Output("truck-info", "children"),
    [Input("store-producao", "data"),
     Input("store-hora", "data"),
     Input("operacao-filter", "value"),
     Input("projeto-store", "data")]
)
def update_truck_info(df_producao_records, df_hora_records, operacao_filter, projeto):
    if not projeto or projeto not in PROJECTS_CONFIG:
        return "Total Caminhões Indicados: 0 / Máximo em Operação: 48"

    period_start, period_end = get_current_shift_period()
    # Filtrar dados das últimas 3 horas
    df_prod_period = get_filtered_data_producao(period_start, period_end, operacao_filter, pd.DataFrame(df_producao_records), last_hours=3)
    if df_prod_period.empty:
        return "Total Caminhões Indicados: 0 / Máximo em Operação: 48"

    df_hora = get_filtered_data_hora(period_start, period_end, df=pd.DataFrame(df_hora_records), last_hours=3)
    merged_data = compute_truck_stats(df_prod_period, df_hora)
    if merged_data.empty:
        return "Total Caminhões Indicados: 0"
    
    total_trucks = int(merged_data["trucks_needed"].sum())
    return f"Total Caminhões Indicados: {total_trucks}"
