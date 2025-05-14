from __future__ import annotations

"""
relatorio5.py – Timeline de Apontamentos por Equipamento

Exibe uma timeline estilo Gantt dos estados de equipamentos, com filtros por período (Hoje/Ontem)
e equipamentos. Otimizado para performance com cache, operações vetorizadas e logs de depuração.
Inicia em branco até que uma obra seja selecionada via projeto-store. Filtra equipamentos com
nome_tipo_equipamento = 'Carga' e exclui TRIMAK.

Dependências:
  - Banco de dados via `db.query_to_df`
  - Configurações `META_MINERIO`, `META_ESTERIL`, `TIMEZONE`, `PROJECTS_CONFIG`, `PROJECT_LABELS` de `config`
"""

# ============================================================
# IMPORTAÇÕES
# ============================================================
from datetime import datetime, timedelta
import logging
import time
from typing import List, Dict, Optional, Any

import dash
from dash import dcc, html, Output, Input
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from db import query_to_df
from config import META_MINERIO, META_ESTERIL, TIMEZONE, PROJECTS_CONFIG, PROJECT_LABELS
from app import cache

# ============================================================
# CONFIGURAÇÕES
# ============================================================

# Configuração do log
logging.basicConfig(
    level=logging.INFO,
    filename="dashboard.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Mapeamento de cores por nome_tipo_estado
COLOR_MAP = {
    "MANUTENÇÃO CORRETIVA": "red",
    "MANUTENÇÃO PREVENTIVA": "red",
    "MANUTENÇÃO OPERACIONAL": "red",
    "IMPRODUTIVA INTERNA": "blue",
    "IMPRODUTIVA EXTERNA": "blue",
    "OPERANDO": "green",
    "SERVIÇO AUXILIAR": "yellow",
    "ATRASO OPERACIONAL": "yellow",
    "FORA DE FROTA": "red"
}

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def profile_time(func):
    """
    Decorador para medir o tempo de execução da função e registrar no log.

    Args:
        func: Função a ser decorada.

    Returns:
        Função embrulhada com medição de tempo.
    """
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = func(*args, **kwargs)
        t1 = time.perf_counter()
        logger.info(f"[Profile] {func.__name__} executada em {t1 - t0:.4f} segundos")
        return result
    return wrapper

@cache.memoize(timeout=300)
@profile_time
def fetch_fato_hora(start_dt: datetime, end_dt: datetime, projeto: str) -> pd.DataFrame:
    """
    Consulta os dados da tabela fato_hora para o período e projeto especificados, com cache.

    Args:
        start_dt (datetime): Data inicial.
        end_dt (datetime): Data final.
        projeto (str): ID do projeto (ex.: 'projeto1').

    Returns:
        pd.DataFrame: Dados de fato_hora ou DataFrame vazio em caso de erro.
    """
    logger.debug(f"[DEBUG] Consultando fato_hora de {start_dt:%d/%m/%Y %H:%M:%S} a {end_dt:%d/%m/%Y %H:%M:%S} para projeto {projeto}")
    if projeto not in PROJECTS_CONFIG:
        logger.error(f"[DEBUG] Projeto {projeto} não encontrado em PROJECTS_CONFIG")
        return pd.DataFrame()
    
    logger.debug(f"[DEBUG] Configuração para {projeto}: server={PROJECTS_CONFIG[projeto]['server']}, database={PROJECTS_CONFIG[projeto]['database']}")
    query = (
        f"EXEC {PROJECTS_CONFIG[projeto]['database']}..usp_fato_hora "
        f"'{start_dt:%d/%m/%Y %H:%M:%S}', '{end_dt:%d/%m/%Y %H:%M:%S}'"
    )
    logger.debug(f"[DEBUG] Query executada: {query}")
    try:
        # Ensure cache key includes projeto to prevent cross-project data leakage
        df = query_to_df(query, projeto=projeto)
        logger.debug(f"[DEBUG] Dados brutos retornados: {len(df)} linhas")
        logger.debug(f"[DEBUG] Colunas retornadas: {df.columns.tolist()}")
        logger.debug(f"[DEBUG] Primeiras 5 linhas:\n{df.head().to_string()}")
        if df.empty or "dt_registro" not in df.columns:
            logger.debug("[DEBUG] DataFrame vazio ou sem coluna 'dt_registro'")
            return pd.DataFrame()
        
        df["dt_registro"] = pd.to_datetime(df["dt_registro"], errors="coerce", infer_datetime_format=True)
        df["dt_registro_turno"] = pd.to_datetime(df["dt_registro_turno"], errors="coerce", infer_datetime_format=True)
        invalid_dates = df["dt_registro"].isna().sum() + df["dt_registro_turno"].isna().sum()
        logger.debug(f"[DEBUG] Linhas com datas inválidas (NaT): {invalid_dates}")
        
        # Normalizar strings
        df = df.assign(
            nome_modelo=df["nome_modelo"].str.strip().str.upper(),
            nome_equipamento=df["nome_equipamento"].str.strip().str.upper(),
            nome_tipo_estado=df["nome_tipo_estado"].str.strip().str.upper(),
            nome_estado=df["nome_estado"].str.strip().str.upper(),
            nome_tipo_equipamento=df["nome_tipo_equipamento"].str.strip().str.upper()
        )
        
        # Filtrar por nome_tipo_equipamento = "CARGA"
        logger.debug(f"[DEBUG] Valores únicos de nome_tipo_equipamento: {df['nome_tipo_equipamento'].unique().tolist()}")
        df = df[df["nome_tipo_equipamento"] == "CARGA"]
        logger.debug(f"[DEBUG] Após filtro nome_tipo_equipamento='CARGA': {len(df)} linhas")
        
        # Excluir TRIMAK
        df = df[df["nome_equipamento"] != "TRIMAK"]
        logger.debug(f"[DEBUG] Após excluir TRIMAK: {len(df)} linhas")
        
        df = df.dropna(subset=["nome_equipamento", "nome_modelo", "nome_estado", "nome_tipo_estado", "nome_tipo_equipamento"])
        logger.debug(f"[DEBUG] Após dropna: {len(df)} linhas")
        return df
    except Exception as e:
        logger.error(f"[DEBUG] Erro ao consultar fato_hora para projeto {projeto}: {str(e)}")
        return pd.DataFrame()

@profile_time
def compute_segments(df: pd.DataFrame, end_dt: datetime) -> pd.DataFrame:
    """
    Calcula segmentos contínuos de estados por equipamento, com duração em minutos.

    Args:
        df (pd.DataFrame): DataFrame com dados de fato_hora.
        end_dt (datetime): Data final para o último segmento.

    Returns:
        pd.DataFrame: Segmentos com colunas nome_equipamento, nome_estado, nome_tipo_estado, start, end, duration.
    """
    if df.empty:
        logger.debug("[DEBUG] DataFrame vazio em compute_segments")
        return pd.DataFrame(columns=["nome_equipamento", "nome_estado", "nome_tipo_estado", "start", "end", "duration"])
    
    df = df.sort_values(["nome_equipamento", "dt_registro"])
    
    # Detectar mudanças de estado ou tipo usando shift
    df["segment_change"] = (
        (df.groupby("nome_equipamento")["nome_estado"].shift() != df["nome_estado"]) |
        (df.groupby("nome_equipamento")["nome_tipo_estado"].shift() != df["nome_tipo_estado"])
    ).fillna(True)
    df["segment_id"] = df.groupby("nome_equipamento")["segment_change"].cumsum().astype(int)
    
    # Agregar segmentos com reset_index para evitar conflitos de índice
    segments = df.groupby(["nome_equipamento", "segment_id"]).agg(
        nome_estado=("nome_estado", "first"),
        nome_tipo_estado=("nome_tipo_estado", "first"),
        start=("dt_registro", "first")
    ).reset_index()
    
    # Definir fim do segmento
    segments["end"] = segments.groupby("nome_equipamento")["start"].shift(-1).fillna(pd.Timestamp(end_dt))
    
    # Calcular duração em minutos
    segments["duration"] = ((segments["end"] - segments["start"]).dt.total_seconds() / 60.0).round(1)
    
    logger.debug(f"[DEBUG] Segmentos calculados: {len(segments)}")
    return segments[["nome_equipamento", "nome_estado", "nome_tipo_estado", "start", "end", "duration"]]

@profile_time
def create_timeline_graph(selected_day: str, projeto: Optional[str], equipment_filter: Optional[List[str]] = None) -> go.Figure:
    """
    Cria um gráfico de timeline (Gantt) com tooltips e layout responsivo.

    Args:
        selected_day (str): Período selecionado ("hoje" ou "ontem").
        projeto (Optional[str]): ID do projeto (ex.: 'projeto1').
        equipment_filter (Optional[List[str]]): Lista de equipamentos para filtrar.

    Returns:
        go.Figure: Gráfico de timeline.
    """
    # Definir período
    if selected_day == "hoje":
        day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = datetime.now()
        title = f"Timeline de Apontamentos - Hoje ({PROJECT_LABELS.get(projeto, 'Nenhuma obra selecionada')})"
    elif selected_day == "ontem":
        day_end = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        day_start = day_end - timedelta(days=1)
        title = f"Timeline de Apontamentos - Ontem ({PROJECT_LABELS.get(projeto, 'Nenhuma obra selecionada')})"
    else:
        day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        title = f"Timeline de Apontamentos ({PROJECT_LABELS.get(projeto, 'Nenhuma obra selecionada')})"
    
    # Verificar projeto
    if not projeto or projeto not in PROJECTS_CONFIG:
        logger.debug("[DEBUG] Nenhum projeto selecionado ou projeto inválido")
        fig = go.Figure()
        fig.add_annotation(
            text="Selecione uma obra para visualizar os dados.",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="#343a40")
        )
        fig.update_layout(
            xaxis_title="Hora",
            yaxis_title="Equipamento",
            showlegend=False,
            title={'text': title, 'x': 0.5, 'xanchor': 'center'},
            template="plotly_white",
            margin=dict(l=150, r=50, t=70, b=50)
        )
        return fig
    
    # Obter dados
    df = fetch_fato_hora(day_start, day_end, projeto)
    if df.empty:
        logger.debug(f"[DEBUG] Nenhum dado retornado por fetch_fato_hora para projeto {projeto}")
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado disponível para o período selecionado.",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="#343a40")
        )
        fig.update_layout(
            xaxis_title="Hora",
            yaxis_title="Equipamento",
            showlegend=False,
            title={'text': title, 'x': 0.5, 'xanchor': 'center'},
            template="plotly_white",
            margin=dict(l=150, r=50, t=70, b=50)
        )
        return fig
    
    # Aplicar filtro de equipamentos (se houver)
    if equipment_filter:
        equipment_filter_upper = [e.strip().upper() for e in equipment_filter]
        df = df[df["nome_equipamento"].isin(equipment_filter_upper)]
        logger.debug(f"[DEBUG] Após filtro de equipamentos selecionados: {len(df)} linhas")
    
    if df.empty:
        logger.debug("[DEBUG] DataFrame vazio após filtros")
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum equipamento corresponde ao filtro selecionado.",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="#343a40")
        )
        fig.update_layout(
            xaxis_title="Hora",
            yaxis_title="Equipamento",
            showlegend=False,
            title={'text': title, 'x': 0.5, 'xanchor': 'center'},
            template="plotly_white",
            margin=dict(l=150, r=50, t=70, b=50)
        )
        return fig
    
    # Filtrar por período
    ts_start = pd.Timestamp(day_start)
    ts_end = pd.Timestamp(day_end)
    logger.debug(f"[DEBUG] ts_start: {ts_start}, tz={ts_start.tz}; ts_end: {ts_end}, tz={ts_end.tz}")
    logger.debug(f"[DEBUG] dt_registro_turno dtype: {df['dt_registro_turno'].dtype}")
    df = df[(df["dt_registro_turno"] >= ts_start) & (df["dt_registro_turno"] < ts_end)]
    
    if df.empty:
        logger.debug("[DEBUG] Nenhum dado no período selecionado")
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado no período selecionado.",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="#343a40")
        )
        fig.update_layout(
            xaxis_title="Hora",
            yaxis_title="Equipamento",
            showlegend=False,
            title={'text': title, 'x': 0.5, 'xanchor': 'center'},
            template="plotly_white",
            margin=dict(l=150, r=50, t=70, b=50)
        )
        return fig
    
    # Calcular segmentos
    seg_df = compute_segments(df, day_end)
    if seg_df.empty:
        logger.debug("[DEBUG] Nenhum segmento calculado")
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum segmento disponível para o período selecionado.",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="#343a40")
        )
        fig.update_layout(
            xaxis_title="Hora",
            yaxis_title="Equipamento",
            showlegend=False,
            title={'text': title, 'x': 0.5, 'xanchor': 'center'},
            template="plotly_white",
            margin=dict(l=150, r=50, t=70, b=50)
        )
        return fig
    
    # Preparar tooltips
    seg_df["start_str"] = seg_df["start"].dt.strftime("%H:%M:%S")
    seg_df["end_str"] = seg_df["end"].dt.strftime("%H:%M:%S")
    
    # Configurar altura dinâmica
    all_equips = sorted(seg_df["nome_equipamento"].unique())
    dynamic_height = max(600, len(all_equips) * 60 + 150)
    
    # Criar gráfico
    fig = px.timeline(
        seg_df,
        x_start="start",
        x_end="end",
        y="nome_equipamento",
        color="nome_tipo_estado",
        color_discrete_map=COLOR_MAP,
        title=title,
        custom_data=["nome_estado", "duration", "start_str", "end_str"]
    )
    fig.update_traces(
        hovertemplate=(
            "<b>Equipamento:</b> %{y}<br>" +
            "<b>Estado:</b> %{customdata[0]}<br>" +
            "<b>Início:</b> %{customdata[2]}<br>" +
            "<b>Fim:</b> %{customdata[3]}<br>" +
            "<b>Duração:</b> %{customdata[1]:.1f} minutos<extra></extra>"
        ),
        marker_line_color="black",
        marker_line_width=2
    )
    fig.update_yaxes(
        autorange="reversed",
        categoryorder="array",
        categoryarray=all_equips,
        tickfont=dict(size=12),
        showgrid=True,
        gridwidth=1,
        gridcolor="lightgray"
    )
    fig.update_layout(
        xaxis_title="Hora",
        yaxis_title="Equipamento",
        height=dynamic_height,
        margin=dict(l=150, r=50, t=70, b=50),
        template="plotly_white",
        title={'x': 0.5, 'xanchor': 'center'},
        xaxis=dict(
            rangeslider_visible=True,
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1h", step="hour", stepmode="backward"),
                    dict(count=6, label="6h", step="hour", stepmode="backward"),
                    dict(count=12, label="12h", step="hour", stepmode="backward"),
                    dict(step="all")
                ])
            )
        )
    )
    fig.update_xaxes(tickformat="%H:%M:%S")
    
    logger.debug(f"[DEBUG] Gráfico criado com {len(all_equips)} equipamentos")
    return fig

# ============================================================
# LAYOUT PRINCIPAL
# ============================================================

NAVBAR = dbc.Navbar(
    dbc.Container([
        dbc.NavbarBrand([
            html.I(className="fas fa-timeline mr-2"),
            "Timeline de Apontamentos"
        ], href="/relatorio5", className="ms-2 d-flex align-items-center", style={"fontSize": "1.1rem"}),
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
                [html.I(className="fas fa-timeline mr-2"), "Timeline de Apontamentos por Equipamento"],
                className="text-center mt-4 mb-4",
                style={"fontFamily": "Arial, sans-serif", "fontSize": "1.6rem", "fontWeight": "500"}
            ),
            width=12
        ),
        className="mb-3"
    ),
    html.Div(
        id="rel5-no-project-message",
        children=html.P(
            "Selecione uma obra para visualizar os dados.",
            className="text-center my-4"
        )
    ),
    dbc.Card([
        dbc.CardHeader(
            html.H5("Selecionar Período", className="mb-0 text-white", style={
                "fontSize": "1.1rem",
                "fontWeight": "500",
                "fontFamily": "Arial, sans-serif"
            }),
            style={"background": "linear-gradient(90deg, #343a40, #495057)"}
        ),
        dbc.CardBody(
            dcc.Tabs(
                id="rel5-tabs",
                value="hoje",
                children=[
                    dcc.Tab(
                        label="Hoje",
                        value="hoje",
                        style={
                            "fontSize": "0.9rem",
                            "padding": "6px 12px",
                            "borderRadius": "8px 8px 0 0",
                            "backgroundColor": "#f8f9fa",
                            "color": "#343a40"
                        },
                        selected_style={
                            "fontSize": "0.9rem",
                            "padding": "6px 12px",
                            "borderRadius": "8px 8px 0 0",
                            "background": "linear-gradient(45deg, #007bff, #00aaff)",
                            "color": "#fff",
                            "fontWeight": "bold"
                        }
                    ),
                    dcc.Tab(
                        label="Ontem",
                        value="ontem",
                        style={
                            "fontSize": "0.9rem",
                            "padding": "6px 12px",
                            "borderRadius": "8px 8px 0 0",
                            "backgroundColor": "#f8f9fa",
                            "color": "#343a40"
                        },
                        selected_style={
                            "fontSize": "0.9rem",
                            "padding": "6px 12px",
                            "borderRadius": "8px 8px 0 0",
                            "background": "linear-gradient(45deg, #007bff, #00aaff)",
                            "color": "#fff",
                            "fontWeight": "bold"
                        }
                    )
                ],
                style={"margin": "0", "padding": "0"}
            ),
            style={"padding": "0.8rem"}
        )
    ], className="shadow-md mb-4 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none", "zIndex": "10"}),
    dbc.Card([
        dbc.CardHeader(
            html.H5("Filtrar Equipamentos", className="mb-0 text-white", style={
                "fontSize": "1.1rem",
                "fontWeight": "500",
                "fontFamily": "Arial, sans-serif"
            }),
            style={"background": "linear-gradient(90deg, #343a40, #495057)"}
        ),
        dbc.CardBody(
            dcc.Dropdown(
                id="rel5-equipment-dropdown",
                placeholder="Filtrar por Equipamento (opcional)",
                multi=True,
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
    dcc.Interval(id="rel5-interval-component", interval=300000, n_intervals=0),
    dcc.Loading(
        id="loading-rel5-graph",
        type="default",
        children=dbc.Card([
            dbc.CardHeader(
                html.H5("Timeline de Apontamentos", className="mb-0 text-white", style={
                    "fontSize": "1.1rem",
                    "fontWeight": "500",
                    "fontFamily": "Arial, sans-serif"
                }),
                style={"background": "linear-gradient(90deg, #343a40, #495057)"}
            ),
            dbc.CardBody(
                dcc.Graph(
                    id="rel5-graph",
                    config={"displayModeBar": False, "responsive": True},
                    style={"minHeight": "600px"}
                ),
                style={"padding": "0.8rem"}
            )
        ], className="shadow-md mb-4 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none", "zIndex": "5"})
    ),
], fluid=True)

# ============================================================
# CALLBACKS
# ============================================================

@dash.callback(
    [Output("rel5-equipment-dropdown", "options"),
     Output("rel5-no-project-message", "style")],
    [Input("rel5-tabs", "value"),
     Input("rel5-interval-component", "n_intervals"),
     Input("projeto-store", "data")]
)
def update_equipment_options(selected_day: str, n_intervals: int, projeto: Optional[str]) -> tuple[List[Dict[str, str]], Dict[str, str]]:
    """
    Atualiza as opções do dropdown de equipamentos com base no período e projeto selecionados,
    e controla a visibilidade da mensagem de 'sem projeto'.

    Args:
        selected_day (str): Período selecionado ("hoje" ou "ontem").
        n_intervals (int): Contador de intervalos para atualização automática.
        projeto (Optional[str]): ID do projeto (ex.: 'projeto1').

    Returns:
        tuple[List[Dict[str, str]], Dict[str, str]]: Opções para o dropdown e estilo da mensagem.
    """
    logger.debug(f"[DEBUG] update_equipment_options disparado: selected_day={selected_day}, n_intervals={n_intervals}, projeto={projeto}")
    
    if not projeto or projeto not in PROJECTS_CONFIG:
        logger.debug("[DEBUG] Nenhum projeto selecionado ou projeto inválido")
        return [], {"display": "block"}
    
    if selected_day == "hoje":
        day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = datetime.now()
    elif selected_day == "ontem":
        day_end = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        day_start = day_end - timedelta(days=1)
    else:
        day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
    
    df = fetch_fato_hora(day_start, day_end, projeto)
    if df.empty:
        logger.debug(f"[DEBUG] Nenhum dado retornado para dropdown para projeto {projeto}")
        return [], {"display": "block", "textAlign": "center", "color": "#343a40", "fontSize": "1.2rem", "margin": "20px 0"}
    
    equips = sorted(df["nome_equipamento"].dropna().astype(str).unique())
    logger.debug(f"[DEBUG] Equipamentos encontrados para dropdown: {len(equips)}")
    return [{"label": equip, "value": equip} for equip in equips], {"display": "none"}

@dash.callback(
    Output("rel5-graph", "figure"),
    [Input("rel5-tabs", "value"),
     Input("rel5-equipment-dropdown", "value"),
     Input("rel5-interval-component", "n_intervals"),
     Input("projeto-store", "data")]
)
def update_graph(selected_day: str, equipment_filter: Optional[List[str]], n_intervals: int, projeto: Optional[str]) -> go.Figure:
    """
    Atualiza o gráfico de timeline com base no período, filtro de equipamentos e projeto.

    Args:
        selected_day (str): Período selecionado ("hoje" ou "ontem").
        equipment_filter (Optional[List[str]]): Lista de equipamentos selecionados.
        n_intervals (int): Contador de intervalos para atualização automática.
        projeto (Optional[str]): ID do projeto (ex.: 'projeto1').

    Returns:
        go.Figure: Gráfico de timeline atualizado.
    """
    logger.debug(f"[DEBUG] update_graph disparado: selected_day={selected_day}, equipment_filter={equipment_filter}, n_intervals={n_intervals}, projeto={projeto}")
    return create_timeline_graph(selected_day, projeto, equipment_filter)
