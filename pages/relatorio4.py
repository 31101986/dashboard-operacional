import math
import logging
import time
from datetime import datetime, timedelta
from typing import Tuple, List, Dict, Any, Union  # Importações adicionadas

import dash
from dash import dcc, html, callback, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
import numpy as np  # Importação para operações vetorizadas
from dash.dash_table.Format import Format, Scheme
from pandas.api.types import CategoricalDtype

# Import da função para consultar o banco e das variáveis de meta, incluindo o fuso horário
from db import query_to_df
from config import META_MINERIO, META_ESTERIL, TIMEZONE

# Configuração do log
logging.basicConfig(
    level=logging.INFO,
    filename="relatorio4.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Formato numérico para tabelas
num_format = Format(precision=2, scheme=Scheme.fixed, group=True)

# Modelos para indicadores
ESCAVACAO_MODELOS = [
    "ESCAVADEIRA HIDRAULICA SANY SY750H",
    "ESCAVADEIRA HIDRÁULICA CAT 352",
    "ESCAVADEIRA HIDRÁULICA CAT 374DL",
    "ESCAVADEIRA HIDRÁULICA VOLVO EC750DL",
]
TRANSPORTE_MODELOS = [
    "MERCEDES BENZ AROCS 4851/45 8X4",
    "VOLVO FMX 500 8X4"
]
PERFURACAO_MODELOS = [
    "PERFURATRIZ HIDRAULICA SANDVIK DP1500I",
    "PERFURATRIZ HIDRAULICA SANDVIK DX800"
]

# ===================== Funções Auxiliares =====================

def consulta_producao(dia_str: str) -> pd.DataFrame:
    """Consulta o fato_producao para o dia informado e retorna o DataFrame filtrado."""
    query = f"EXEC dw_sdp_mt_fas..usp_fato_producao '{dia_str}', '{dia_str}'"
    try:
        df = query_to_df(query)
    except Exception as e:
        logging.error(f"[Rel4] Erro ao consultar fato_producao: {e}")
        return pd.DataFrame()
    if df.empty or "dt_registro_turno" not in df.columns:
        return df
    df["dt_registro_turno"] = pd.to_datetime(df["dt_registro_turno"], errors="coerce")
    if df["dt_registro_turno"].dt.tz is None:
        df["dt_registro_turno"] = df["dt_registro_turno"].dt.tz_localize(TIMEZONE)
    filtro_data = datetime.strptime(dia_str, "%d/%m/%Y").replace(tzinfo=TIMEZONE).date()
    df = df.loc[df["dt_registro_turno"].dt.date == filtro_data]
    return df

def consulta_hora(dia_str: str) -> pd.DataFrame:
    """Consulta o fato_hora para o dia informado e retorna o DataFrame filtrado."""
    query = f"EXEC dw_sdp_mt_fas..usp_fato_hora '{dia_str}', '{dia_str}'"
    try:
        df = query_to_df(query)
    except Exception as e:
        logging.error(f"[Rel4] Erro ao consultar fato_hora: {e}")
        return pd.DataFrame()
    if df.empty or "dt_registro_turno" not in df.columns:
        return df
    df["dt_registro_turno"] = pd.to_datetime(df["dt_registro_turno"], errors="coerce")
    if df["dt_registro_turno"].dt.tz is None:
        df["dt_registro_turno"] = df["dt_registro_turno"].dt.tz_localize(TIMEZONE)
    filtro_data = datetime.strptime(dia_str, "%d/%m/%Y").replace(tzinfo=TIMEZONE).date()
    df = df.loc[df["dt_registro_turno"].dt.date == filtro_data]
    return df

def calcular_horas_desde_7h(day_choice: str) -> float:
    """
    Calcula as horas decorridas:
      - Se 'ontem', retorna 24 horas.
      - Se 'hoje', calcula a diferença desde as 07:00 do dia atual.
    """
    if day_choice == "ontem":
        return 24.0
    now = datetime.now(TIMEZONE)
    start_7h = now.replace(hour=7, minute=0, second=0, microsecond=0)
    if now < start_7h:
        start_7h -= timedelta(days=1)
    horas_passadas = (now - start_7h).total_seconds() / 3600.0
    return max(horas_passadas, 0.01)

def calc_indicadores_agrupados_por_modelo(df: pd.DataFrame, modelos_lista: List[str]) -> Tuple[List[dict], List[dict], List[dict]]:
    """
    Agrupa os dados (do fato_hora) por modelo, calculando Disponibilidade, Utilização e Rendimento.
    Retorna (data, columns, style_data_conditional) para o DataTable.
    Esta versão utiliza operações vetorizadas para performance.
    """
    needed_cols = {"nome_modelo", "nome_tipo_estado", "tempo_hora"}
    if not needed_cols.issubset(df.columns):
        return [], [], []
    df_f = df.loc[df["nome_modelo"].isin(modelos_lista)].copy()
    if df_f.empty:
        return [], [], []
    df_f["tempo_hora"] = pd.to_numeric(df_f["tempo_hora"], errors="coerce").fillna(0)
    
    grp_total = df_f.groupby("nome_modelo", as_index=False)["tempo_hora"].sum().rename(columns={"tempo_hora": "total"})
    grp_fora = df_f[df_f["nome_tipo_estado"]=="Fora de Frota"].groupby("nome_modelo", as_index=False)["tempo_hora"].sum().rename(columns={"tempo_hora": "fora"})
    grp_manut = df_f[df_f["nome_tipo_estado"].isin(["Manutenção Preventiva", "Manutenção Corretiva", "Manutenção Operacional"])].groupby("nome_modelo", as_index=False)["tempo_hora"].sum().rename(columns={"tempo_hora": "manut"})
    grp_trab = df_f[df_f["nome_tipo_estado"].isin(["Operando", "Serviço Auxiliar", "Atraso Operacional"])].groupby("nome_modelo", as_index=False)["tempo_hora"].sum().rename(columns={"tempo_hora": "trab"})
    
    df_ind = pd.merge(grp_total, grp_fora, on="nome_modelo", how="left").fillna(0)
    df_ind = pd.merge(df_ind, grp_manut, on="nome_modelo", how="left").fillna(0)
    df_ind = pd.merge(df_ind, grp_trab, on="nome_modelo", how="left").fillna(0)
    
    df_ind["cal"] = df_ind["total"] - df_ind["fora"]
    df_ind["disp"] = df_ind["cal"] - df_ind["manut"]
    df_ind["disponibilidade"] = np.where(df_ind["cal"] > 0, 100 * df_ind["disp"] / df_ind["cal"], 0)
    df_ind["utilizacao"] = np.where(df_ind["disp"] > 0, 100 * df_ind["trab"] / df_ind["disp"], 0)
    df_ind["rendimento"] = df_ind["disponibilidade"] * df_ind["utilizacao"] / 100.0

    df_ind = df_ind[["nome_modelo", "disponibilidade", "utilizacao", "rendimento"]]
    
    # Cálculo global utilizando todos os dados
    total_total = df_f["tempo_hora"].sum()
    total_fora = df_f.loc[df_f["nome_tipo_estado"]=="Fora de Frota", "tempo_hora"].sum()
    total_manut = df_f.loc[df_f["nome_tipo_estado"].isin(["Manutenção Preventiva", "Manutenção Corretiva", "Manutenção Operacional"]), "tempo_hora"].sum()
    total_trab = df_f.loc[df_f["nome_tipo_estado"].isin(["Operando", "Serviço Auxiliar", "Atraso Operacional"]), "tempo_hora"].sum()
    total_cal = total_total - total_fora
    total_disp = total_cal - total_manut
    overall_disp = (100 * total_disp / total_cal) if total_cal > 0 else 0
    overall_util = (100 * total_trab / total_disp) if total_disp > 0 else 0
    overall_rend = overall_disp * overall_util / 100.0

    total_row = pd.DataFrame([{
         "nome_modelo": "TOTAL",
         "disponibilidade": overall_disp,
         "utilizacao": overall_util,
         "rendimento": overall_rend
    }])
    df_ind = pd.concat([df_ind, total_row], ignore_index=True)
    data = df_ind.to_dict("records")
    columns = [
       {"name": "Modelo", "id": "nome_modelo", "type": "text"},
       {"name": "Disponibilidade (%)", "id": "disponibilidade", "type": "numeric", "format": num_format},
       {"name": "Utilização (%)", "id": "utilizacao", "type": "numeric", "format": num_format},
       {"name": "Rendimento (%)", "id": "rendimento", "type": "numeric", "format": num_format},
    ]
    style_cond = [
       {"if": {"filter_query": "{disponibilidade} >= 80", "column_id": "disponibilidade"}, "color": "green"},
       {"if": {"filter_query": "{disponibilidade} < 80", "column_id": "disponibilidade"}, "color": "red"},
       {"if": {"filter_query": "{utilizacao} >= 75", "column_id": "utilizacao"}, "color": "green"},
       {"if": {"filter_query": "{utilizacao} < 75", "column_id": "utilizacao"}, "color": "red"},
       {"if": {"filter_query": "{rendimento} >= 60", "column_id": "rendimento"}, "color": "green"},
       {"if": {"filter_query": "{rendimento} < 60", "column_id": "rendimento"}, "color": "red"},
       {"if": {"filter_query": '{nome_modelo} = "TOTAL"'}, "backgroundColor": "#fff9c4", "fontWeight": "bold"}
    ]
    return data, columns, style_cond

# ===================== LAYOUT =====================

layout = dbc.Container(
    [
        dbc.Row([
            dbc.Col(
                html.H1("Produção e Indicadores", className="text-center text-primary",
                        style={"fontFamily": "Arial, sans-serif"}),
                xs=12, md=10
            ),
            dbc.Col(
                dbc.Button("Voltar ao Portal", href="/", color="secondary", className="w-100"),
                xs=12, md=2
            )
        ], className="my-4"),
        dbc.Row(
            dbc.Col(
                html.Div(
                    [
                        html.P("Escolha se deseja visualizar o dia atual ou o dia anterior.",
                               style={"fontFamily": "Arial, sans-serif"}),
                        dbc.RadioItems(
                            id="rel4-day-selector",
                            className="btn-group",
                            inputClassName="btn-check",
                            labelClassName="btn btn-outline-primary",
                            labelCheckedClassName="active",
                            options=[
                                {"label": "Dia Atual", "value": "hoje"},
                                {"label": "Dia Anterior", "value": "ontem"},
                            ],
                            value="hoje",
                            inline=True
                        )
                    ],
                    style={"marginBottom": "10px"}
                ),
                width=12
            ),
            className="mb-4"
        ),
        # Stores para dados de produção e hora
        dcc.Store(id="rel4-producao-store"),
        dcc.Store(id="rel4-hora-store"),
        # 1) Tabela de Movimentação
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader(
                            html.H5("Movimentação (Dia Atual ou Dia Anterior)", className="mb-0",
                                    style={"fontFamily": "Arial, sans-serif"}),
                            className="bg-light"
                        ),
                        dbc.CardBody(
                            dcc.Loading(
                                dash_table.DataTable(
                                    id="rel4-tabela-movimentacao",
                                    columns=[
                                        {"name": "Operação", "id": "nome_operacao", "type": "text"},
                                        {"name": "Viagens", "id": "viagens", "type": "numeric", "format": num_format},
                                        {"name": "Volume", "id": "volume", "type": "numeric", "format": num_format},
                                        {"name": "Ritmo (m³/h)", "id": "ritmo_volume", "type": "numeric", "format": num_format},
                                    ],
                                    style_table={"overflowX": "auto"},
                                    style_header={
                                        "backgroundColor": "#f8f9fa",
                                        "fontWeight": "bold",
                                        "textAlign": "center"
                                    },
                                    style_cell={
                                        "textAlign": "center",
                                        "whiteSpace": "normal",
                                        "fontFamily": "Arial, sans-serif"
                                    },
                                    page_size=10
                                ),
                                type="default"
                            )
                        )
                    ],
                    className="mb-4 shadow animate__animated animate__fadeInUp",
                    style={"marginBottom": "30px"}
                ),
                width=12
            ),
            className="mt-2"
        ),
        # 2) Gráfico de Viagens por Hora Trabalhada
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader(
                            html.H5("Viagens por Hora Trabalhada", style={"fontFamily": "Arial, sans-serif"}),
                            className="bg-light"
                        ),
                        dbc.CardBody(
                            dcc.Loading(
                                dcc.Graph(
                                    id="rel4-grafico-viagens-hora",
                                    config={"displayModeBar": False},
                                    style={"minHeight": "450px"}
                                ),
                                type="default"
                            )
                        )
                    ],
                    className="mb-4 shadow animate__animated animate__fadeInUp",
                    style={"marginBottom": "30px"}
                ),
                width=12
            ),
            className="mt-2"
        ),
        # 3) Tabelas de Indicadores
        # Indicadores - Escavação
        dbc.Row(
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader(
                        html.H5("Indicadores - Escavação", className="mb-0", style={"fontFamily": "Arial, sans-serif"}),
                        className="bg-light"
                    ),
                    dbc.CardBody(
                        dcc.Loading(
                            dash_table.DataTable(
                                id="rel4-tabela-ind-escavacao",
                                columns=[],
                                data=[],
                                style_table={"overflowX": "auto"},
                                style_header={
                                    "backgroundColor": "#f8f9fa",
                                    "fontWeight": "bold",
                                    "textAlign": "center"
                                },
                                style_cell={
                                    "textAlign": "center",
                                    "fontFamily": "Arial, sans-serif"
                                },
                                style_data={
                                    "minWidth": "100px",
                                    ":first-child": {"minWidth": "300px"},  # Coluna "Modelo"
                                    ":nth-child(2)": {"minWidth": "150px"},  # Coluna "Disponibilidade (%)"
                                    ":nth-child(3)": {"minWidth": "150px"},  # Coluna "Utilização (%)"
                                    ":nth-child(4)": {"minWidth": "150px"},  # Coluna "Rendimento (%)"
                                },
                                page_size=10
                            ),
                            type="default"
                        )
                    )
                ], className="mb-4 shadow animate__animated animate__fadeInUp", style={"marginBottom": "30px"}),
                width=12
            ),
            className="mt-2"
        ),
        # Indicadores - Transporte
        dbc.Row(
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader(
                        html.H5("Indicadores - Transporte", className="mb-0", style={"fontFamily": "Arial, sans-serif"}),
                        className="bg-light"
                    ),
                    dbc.CardBody(
                        dcc.Loading(
                            dash_table.DataTable(
                                id="rel4-tabela-ind-transporte",
                                columns=[],
                                data=[],
                                style_table={"overflowX": "auto"},
                                style_header={
                                    "backgroundColor": "#f8f9fa",
                                    "fontWeight": "bold",
                                    "textAlign": "center"
                                },
                                style_cell={
                                    "textAlign": "center",
                                    "fontFamily": "Arial, sans-serif"
                                },
                                style_data={
                                    "minWidth": "100px",
                                    ":first-child": {"minWidth": "300px"},  # Coluna "Modelo"
                                    ":nth-child(2)": {"minWidth": "150px"},  # Coluna "Disponibilidade (%)"
                                    ":nth-child(3)": {"minWidth": "150px"},  # Coluna "Utilização (%)"
                                    ":nth-child(4)": {"minWidth": "150px"},  # Coluna "Rendimento (%)"
                                },
                                page_size=10
                            ),
                            type="default"
                        )
                    )
                ], className="mb-4 shadow animate__animated animate__fadeInUp", style={"marginBottom": "30px"}),
                width=12
            ),
            className="mt-2"
        ),
        # Indicadores - Perfuração
        dbc.Row(
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader(
                        html.H5("Indicadores - Perfuração", className="mb-0", style={"fontFamily": "Arial, sans-serif"}),
                        className="bg-light"
                    ),
                    dbc.CardBody(
                        dcc.Loading(
                            dash_table.DataTable(
                                id="rel4-tabela-ind-perfuracao",
                                columns=[],
                                data=[],
                                style_table={"overflowX": "auto"},
                                style_header={
                                    "backgroundColor": "#f8f9fa",
                                    "fontWeight": "bold",
                                    "textAlign": "center"
                                },
                                style_cell={
                                    "textAlign": "center",
                                    "fontFamily": "Arial, sans-serif"
                                },
                                style_data={
                                    "minWidth": "100px",
                                    ":first-child": {"minWidth": "300px"},  # Coluna "Modelo"
                                    ":nth-child(2)": {"minWidth": "150px"},  # Coluna "Disponibilidade (%)"
                                    ":nth-child(3)": {"minWidth": "150px"},  # Coluna "Utilização (%)"
                                    ":nth-child(4)": {"minWidth": "150px"},  # Coluna "Rendimento (%)"
                                },
                                page_size=10
                            ),
                            type="default"
                        )
                    )
                ], className="mb-4 shadow animate__animated animate__fadeInUp", style={"marginBottom": "30px"}),
                width=12
            ),
            className="mt-2"
        ),
        # Indicadores - Auxiliares
        dbc.Row(
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader(
                        html.H5("Indicadores - Auxiliares", className="mb-0", style={"fontFamily": "Arial, sans-serif"}),
                        className="bg-light"
                    ),
                    dbc.CardBody(
                        dcc.Loading(
                            dash_table.DataTable(
                                id="rel4-tabela-ind-auxiliares",
                                columns=[],
                                data=[],
                                style_table={"overflowX": "auto"},
                                style_header={
                                    "backgroundColor": "#f8f9fa",
                                    "fontWeight": "bold",
                                    "textAlign": "center"
                                },
                                style_cell={
                                    "textAlign": "center",
                                    "fontFamily": "Arial, sans-serif"
                                },
                                style_data={
                                    "minWidth": "100px",
                                    ":first-child": {"minWidth": "300px"},  # Coluna "Modelo"
                                    ":nth-child(2)": {"minWidth": "150px"},  # Coluna "Disponibilidade (%)"
                                    ":nth-child(3)": {"minWidth": "150px"},  # Coluna "Utilização (%)"
                                    ":nth-child(4)": {"minWidth": "150px"},  # Coluna "Rendimento (%)"
                                },
                                page_action="none"
                            ),
                            type="default"
                        )
                    )
                ], className="mb-4 shadow animate__animated animate__fadeInUp", style={"marginBottom": "30px"}),
                width=12
            ),
            className="mt-2"
        ),
        dbc.Row(
            dbc.Col(
                dcc.Link(
                    "Voltar para o Portal",
                    href="/",
                    className="btn btn-secondary",
                    style={"fontFamily": "Arial, sans-serif", "fontSize": "16px"}
                ),
                xs=12,
                className="text-center my-4"
            )
        )
    ],
    fluid=True
)

# ===================== CALLBACKS =====================

@dash.callback(
    Output("rel4-producao-store", "data"),
    Output("rel4-hora-store", "data"),
    Input("rel4-day-selector", "value")
)
def fetch_data_dia_escolhido(day_choice: str) -> Tuple[Any, Any]:
    """
    Busca os dados de produção e de hora para o dia selecionado.
    Se o dia escolhido for "ontem", utiliza a data de ontem; caso contrário, utiliza o dia atual.
    Retorna os dados serializados em JSON.
    """
    if day_choice == "ontem":
        data_str = (datetime.now(TIMEZONE) - timedelta(days=1)).strftime("%d/%m/%Y")
    else:
        data_str = datetime.now(TIMEZONE).strftime("%d/%m/%Y")
    df_prod = consulta_producao(data_str)
    df_hora = consulta_hora(data_str)
    return (
        df_prod.to_json(date_format="iso", orient="records") if not df_prod.empty else {},
        df_hora.to_json(date_format="iso", orient="records") if not df_hora.empty else {}
    )

@dash.callback(
    Output("rel4-tabela-movimentacao", "data"),
    Output("rel4-tabela-movimentacao", "style_data_conditional"),
    Input("rel4-producao-store", "data"),
    Input("rel4-day-selector", "value")
)
def update_tabela_movimentacao(json_prod: Union[str, dict], day_choice: str) -> Tuple[List[dict], List[dict]]:
    """
    Atualiza a tabela de movimentação a partir dos dados de produção.
    Agrupa por operação e calcula o ritmo (volume ajustado para 24h).
    Aplica formatação condicional para a linha TOTAL.
    """
    if not json_prod or isinstance(json_prod, dict):
        return [], []
    df = pd.read_json(json_prod, orient="records")
    if df.empty:
        return [], []
    df = df.loc[df["nome_operacao"].isin(["Movimentação Minério", "Movimentação Estéril"])]
    if df.empty:
        return [], []
    df_grp = df.groupby("nome_operacao", as_index=False).agg(
        viagens=("nome_operacao", "size"),
        volume=("volume", "sum")
    )
    total_line = pd.DataFrame({
        "nome_operacao": ["TOTAL"],
        "viagens": [df_grp["viagens"].sum()],
        "volume": [df_grp["volume"].sum()]
    })
    df_grp = pd.concat([df_grp, total_line], ignore_index=True)
    horas_decorridas = calcular_horas_desde_7h(day_choice)
    df_grp["ritmo_volume"] = (df_grp["volume"] / horas_decorridas) * 24.0
    meta_total = META_MINERIO + META_ESTERIL
    style_data_conditional = [
        {
            "if": {"filter_query": '{nome_operacao} = "TOTAL" && {volume} >= ' + str(meta_total),
                   "column_id": "volume"},
            "color": "rgb(0,55,158)"
        },
        {
            "if": {"filter_query": '{nome_operacao} = "TOTAL" && {volume} < ' + str(meta_total),
                   "column_id": "volume"},
            "color": "red"
        },
        {
            "if": {"filter_query": '{nome_operacao} = "TOTAL"'},
            "backgroundColor": "#fff9c4",
            "fontWeight": "bold"
        }
    ]
    data = df_grp.to_dict("records")
    return data, style_data_conditional

@dash.callback(
    Output("rel4-grafico-viagens-hora", "figure"),
    Input("rel4-producao-store", "data"),
    Input("rel4-hora-store", "data")
)
def update_grafico_viagens_hora(json_prod: Union[str, dict], json_hora: Union[str, dict]) -> Any:
    """
    Cria o gráfico de Viagens por Hora Trabalhada a partir dos dados de produção e fato_hora.
    Se não houver dados, retorna gráfico vazio com mensagem.
    """
    if (not json_prod or isinstance(json_prod, dict)) or (not json_hora or isinstance(json_hora, dict)):
        return px.bar(title="Sem dados para o período.", template="plotly_white")
    df_prod = pd.read_json(json_prod, orient="records")
    df_hora = pd.read_json(json_hora, orient="records")
    if df_prod.empty or df_hora.empty:
        return px.bar(title="Sem dados para o período.", template="plotly_white")
    df_prod = df_prod.loc[df_prod["nome_operacao"].isin(["Movimentação Minério", "Movimentação Estéril"])]
    if df_prod.empty:
        return px.bar(title="Sem dados (Minério/Estéril).", template="plotly_white")
    df_viagens = df_prod.groupby("nome_equipamento_utilizado", as_index=False).agg(
        viagens=("nome_equipamento_utilizado", "count")
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
        return px.bar(title="Sem dados para gerar Viagens/Hora.", template="plotly_white")
    df_merged["viagens_por_hora"] = df_merged["viagens"] / df_merged["horas_trabalhadas"].replace(0, np.nan)
    df_merged["viagens_por_hora"] = df_merged["viagens_por_hora"].fillna(0)
    df_merged.sort_values("viagens_por_hora", inplace=True)
    fig = px.bar(
        df_merged,
        x="nome_equipamento_utilizado",
        y="viagens_por_hora",
        title="Viagens por Hora Trabalhada",
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

@dash.callback(
    Output("rel4-tabela-ind-escavacao", "data"),
    Output("rel4-tabela-ind-escavacao", "columns"),
    Output("rel4-tabela-ind-escavacao", "style_data_conditional"),
    Input("rel4-hora-store", "data")
)
def update_tabela_ind_escavacao(json_hora: Union[str, dict]) -> Tuple[List[dict], List[dict], List[dict]]:
    if not json_hora or isinstance(json_hora, dict):
        return [], [], []
    df_h = pd.read_json(json_hora, orient="records")
    if df_h.empty:
        return [], [], []
    data, columns, style_cond = calc_indicadores_agrupados_por_modelo(df_h, ESCAVACAO_MODELOS)
    return data, columns, style_cond

@dash.callback(
    Output("rel4-tabela-ind-transporte", "data"),
    Output("rel4-tabela-ind-transporte", "columns"),
    Output("rel4-tabela-ind-transporte", "style_data_conditional"),
    Input("rel4-hora-store", "data")
)
def update_tabela_ind_transporte(json_hora: Union[str, dict]) -> Tuple[List[dict], List[dict], List[dict]]:
    if not json_hora or isinstance(json_hora, dict):
        return [], [], []
    df_h = pd.read_json(json_hora, orient="records")
    if df_h.empty:
        return [], [], []
    data, columns, style_cond = calc_indicadores_agrupados_por_modelo(df_h, TRANSPORTE_MODELOS)
    return data, columns, style_cond

@dash.callback(
    Output("rel4-tabela-ind-perfuracao", "data"),
    Output("rel4-tabela-ind-perfuracao", "columns"),
    Output("rel4-tabela-ind-perfuracao", "style_data_conditional"),
    Input("rel4-hora-store", "data")
)
def update_tabela_ind_perfuracao(json_hora: Union[str, dict]) -> Tuple[List[dict], List[dict], List[dict]]:
    if not json_hora or isinstance(json_hora, dict):
        return [], [], []
    df_h = pd.read_json(json_hora, orient="records")
    if df_h.empty:
        return [], [], []
    data, columns, style_cond = calc_indicadores_agrupados_por_modelo(df_h, PERFURACAO_MODELOS)
    return data, columns, style_cond

@dash.callback(
    Output("rel4-tabela-ind-auxiliares", "data"),
    Output("rel4-tabela-ind-auxiliares", "columns"),
    Output("rel4-tabela-ind-auxiliares", "style_data_conditional"),
    Input("rel4-hora-store", "data")
)
def update_tabela_ind_auxiliares(json_hora: Union[str, dict]) -> Tuple[List[dict], List[dict], List[dict]]:
    if not json_hora or isinstance(json_hora, dict):
        return [], [], []
    df_h = pd.read_json(json_hora, orient="records")
    if df_h.empty:
        return [], [], []
    # Lista de todos os modelos exceto os das outras tabelas
    todos_modelos = df_h["nome_modelo"].unique().tolist()
    modelos_existentes = ESCAVACAO_MODELOS + TRANSPORTE_MODELOS + PERFURACAO_MODELOS
    auxiliares_modelos = [modelo for modelo in todos_modelos if modelo not in modelos_existentes]
    if not auxiliares_modelos:
        return [], [], []
    data, columns, style_cond = calc_indicadores_agrupados_por_modelo(df_h, auxiliares_modelos)
    return data, columns, style_cond
