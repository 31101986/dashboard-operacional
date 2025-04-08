from datetime import datetime, timedelta
import logging
import pandas as pd
import dash
from dash import dcc, html, Output, Input
import dash_bootstrap_components as dbc
import plotly.express as px

from db import query_to_df

# Configuração do log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lista de modelos permitidos, exatamente conforme informado
ALLOWED_MODELS = [
    "ESCAVADEIRA HIDRAULICA SANY SY750H",
    "ESCAVADEIRA HIDRÁULICA CAT 352",
    "ESCAVADEIRA HIDRÁULICA CAT 374DL",
    "ESCAVADEIRA HIDRÁULICA VOLVO EC750DL"
]

# Mapeamento de cores baseado em nome_tipo_estado (chaves em uppercase)
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

def get_fato_hora(start_dt, end_dt):
    """
    Consulta os dados da tabela fato_hora para o período especificado.
    Utiliza a procedure 'usp_fato_hora'.
    """
    query = (
        f"EXEC dw_sdp_mt_fas..usp_fato_hora "
        f"'{start_dt:%d/%m/%Y %H:%M:%S}', '{end_dt:%d/%m/%Y %H:%M:%S}'"
    )
    df = query_to_df(query)
    if not df.empty:
        df["dt_registro"] = pd.to_datetime(df["dt_registro"], errors="coerce")
        df["dt_registro_turno"] = pd.to_datetime(df["dt_registro_turno"], errors="coerce")
    return df

def compute_segments(df, end_dt):
    """
    Divide os registros de cada equipamento em segmentos contínuos onde o estado e
    o tipo de estado permanecem inalterados. Para o último segmento, o período vai até end_dt.
    Acrescenta a coluna 'duration' (em minutos) para cada segmento.

    Versão otimizada utilizando operações vetorizadas.
    """
    # Ordena os dados por equipamento e tempo de registro
    df = df.sort_values(["nome_equipamento", "dt_registro"]).copy()
    
    # Identifica onde há mudança de estado ou tipo de estado para cada equipamento
    df["segment_change"] = (
        (df.groupby("nome_equipamento")["nome_estado"].shift() != df["nome_estado"]) |
        (df.groupby("nome_equipamento")["nome_tipo_estado"].shift() != df["nome_tipo_estado"])
    )
    # Cria um identificador incremental de segmento para cada equipamento
    df["segment_id"] = df.groupby("nome_equipamento")["segment_change"].cumsum()
    
    # Agrega os dados de cada segmento: pega o primeiro estado, tipo e horário do segmento
    segments = df.groupby(["nome_equipamento", "segment_id"], as_index=False).agg(
        nome_estado=("nome_estado", "first"),
        nome_tipo_estado=("nome_tipo_estado", "first"),
        start=("dt_registro", "first")
    )
    
    # Para cada equipamento, o final de um segmento é o início do próximo;
    # para o último segmento, utiliza-se end_dt
    segments["end"] = segments.groupby("nome_equipamento")["start"].shift(-1)
    segments["end"] = segments["end"].fillna(end_dt)
    
    # Calcula a duração do segmento em minutos, arredondada para uma casa decimal
    segments["duration"] = ((segments["end"] - segments["start"]).dt.total_seconds() / 60.0).round(1)
    
    return segments[["nome_equipamento", "nome_estado", "nome_tipo_estado", "start", "end", "duration"]]

def create_timeline_graph(selected_day, equipment_filter=None):
    """
    Cria um gráfico de timeline (estilo Gantt) com:
      - Tooltips enriquecidos com informações de início, fim e duração (em minutos)
      - Range slider com botões de zoom para facilitar a navegação
      - Filtro por equipamento, se informado
      - Layout responsivo e barras com borda para melhor visualização
    """
    if selected_day == "hoje":
        day_start = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        # Para "hoje", use o horário atual para o último registro
        day_end = datetime.now()
        title = "Timeline de Apontamentos - Hoje"
    elif selected_day == "ontem":
        day_end = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        day_start = day_end - timedelta(days=1)
        title = "Timeline de Apontamentos - Ontem"
    else:
        day_start = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        title = "Timeline de Apontamentos"

    df = get_fato_hora(day_start, day_end)
    if df.empty:
        fig = px.timeline(title=title)
        fig.update_layout(xaxis_title="Hora", yaxis_title="Equipamento")
        return fig

    df = df[(df["dt_registro_turno"] >= pd.Timestamp(day_start)) &
            (df["dt_registro_turno"] < pd.Timestamp(day_end))]

    # Padroniza os textos e converte para uppercase onde necessário
    df["nome_modelo"] = df["nome_modelo"].astype(str).str.strip()
    df["nome_equipamento"] = df["nome_equipamento"].astype(str).str.strip()
    df["nome_tipo_estado"] = df["nome_tipo_estado"].astype(str).str.strip().str.upper()

    # Filtra os modelos permitidos e remove registros indesejados
    df = df[df["nome_modelo"].isin(ALLOWED_MODELS)]
    df = df[df["nome_equipamento"].str.upper() != "TRIMAK"]

    if equipment_filter:
        df = df[df["nome_equipamento"].isin(equipment_filter)]

    if df.empty:
        fig = px.timeline(title=title)
        fig.update_layout(xaxis_title="Hora", yaxis_title="Equipamento")
        return fig

    seg_df = compute_segments(df, day_end)

    # Cria colunas formatadas para tooltip
    seg_df["start_str"] = seg_df["start"].dt.strftime("%H:%M:%S")
    seg_df["end_str"] = seg_df["end"].dt.strftime("%H:%M:%S")

    all_equips = sorted(df["nome_equipamento"].unique())
    dynamic_height = max(600, len(all_equips) * 60 + 150)

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
    return fig

# ===================== LAYOUT PRINCIPAL =====================
layout = dbc.Container([
    dbc.Row(
        dbc.Col(
            html.H1(
                "Relatório 5 – Timeline de Apontamentos por Equipamento",
                className="text-center my-4",
                style={"fontFamily": "Arial, sans-serif"}
            ),
            width=12
        )
    ),
    dcc.Tabs(
        id="rel5-tabs",
        value="hoje",
        children=[
            dcc.Tab(label="Hoje", value="hoje"),
            dcc.Tab(label="Ontem", value="ontem")
        ],
        style={"marginTop": "20px", "marginBottom": "10px"}
    ),
    dbc.Row(
        dbc.Col(
            dcc.Dropdown(
                id="rel5-equipment-dropdown",
                placeholder="Filtrar por Equipamento (opcional)",
                multi=True,
                style={"fontFamily": "Arial, sans-serif", "marginTop": "10px"}
            ),
            width=12
        ),
        className="mb-3"
    ),
    dbc.Row(
        dbc.Col(
            html.Div(
                dcc.Graph(
                    id="rel5-graph",
                    config={"displayModeBar": False, "responsive": True}
                ),
                style={"height": "calc(100vh - 200px)", "overflowY": "auto"}
            )
        )
    )
], fluid=True)

@dash.callback(
    Output("rel5-equipment-dropdown", "options"),
    Input("rel5-tabs", "value")
)
def update_equipment_options(selected_day):
    if selected_day == "hoje":
        day_start = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = datetime.now()
    elif selected_day == "ontem":
        day_end = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        day_start = day_end - timedelta(days=1)
    else:
        day_start = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
    df = get_fato_hora(day_start, day_end)
    if df.empty:
        return []
    df = df[df["nome_modelo"].isin(ALLOWED_MODELS)]
    equips = sorted(df["nome_equipamento"].dropna().unique())
    return [{"label": equip, "value": equip} for equip in equips]

@dash.callback(
    Output("rel5-graph", "figure"),
    Input("rel5-tabs", "value"),
    Input("rel5-equipment-dropdown", "value")
)
def update_graph(selected_day, equipment_filter):
    return create_timeline_graph(selected_day, equipment_filter)
