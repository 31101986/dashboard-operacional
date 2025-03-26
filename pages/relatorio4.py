import math
import logging
from datetime import datetime, timedelta

import dash
from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc
import dash_table
import plotly.express as px
import pandas as pd
from dash.dash_table.Format import Format, Scheme
from dash.dash_table import FormatTemplate
from pandas.api.types import CategoricalDtype

# Import da função para consultar o banco e das variáveis de meta
from db import query_to_df
from config import META_MINERIO, META_ESTERIL

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

def consulta_producao(dia_str):
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
    filtro_data = datetime.strptime(dia_str, "%d/%m/%Y").date()
    df = df[df["dt_registro_turno"].dt.date == filtro_data]
    return df

def consulta_hora(dia_str):
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
    filtro_data = datetime.strptime(dia_str, "%d/%m/%Y").date()
    df = df[df["dt_registro_turno"].dt.date == filtro_data]
    return df

def calcular_horas_desde_7h(day_choice):
    """
    Calcula as horas decorridas:
      - Se 'ontem', retorna 24 horas.
      - Se 'hoje', calcula a diferença desde as 07:00 do dia atual.
    """
    if day_choice == "ontem":
        return 24.0
    now = datetime.now()
    start_7h = now.replace(hour=7, minute=0, second=0, microsecond=0)
    if now < start_7h:
        start_7h -= timedelta(days=1)
    horas_passadas = (now - start_7h).total_seconds() / 3600.0
    return max(horas_passadas, 0.01)

def calc_indicadores_agrupados_por_modelo(df, modelos_lista):
    """
    Agrupa os dados (do fato_hora) por modelo, calculando Disponibilidade, Utilização e Rendimento.
    Retorna (data, columns, style_data_conditional) para o DataTable.
    """
    needed_cols = {"nome_modelo", "nome_tipo_estado", "tempo_hora"}
    if not needed_cols.issubset(df.columns):
        return [], [], []
    df_f = df[df["nome_modelo"].isin(modelos_lista)].copy()
    if df_f.empty:
        return [], [], []
    df_f["tempo_hora"] = pd.to_numeric(df_f["tempo_hora"], errors="coerce").fillna(0)

    def calc_indicadores(subdf):
        horas_totais = subdf["tempo_hora"].sum()
        horas_fora = subdf.loc[subdf["nome_tipo_estado"] == "Fora de Frota", "tempo_hora"].sum()
        horas_cal = horas_totais - horas_fora
        horas_manut = subdf.loc[subdf["nome_tipo_estado"].isin(
            ["Manutenção Preventiva", "Manutenção Corretiva", "Manutenção Operacional"]
        ), "tempo_hora"].sum()
        horas_disp = horas_cal - horas_manut
        horas_trab = subdf.loc[subdf["nome_tipo_estado"].isin(
            ["Operando", "Serviço Auxiliar", "Atraso Operacional"]
        ), "tempo_hora"].sum()
        disp = (horas_disp / horas_cal * 100) if horas_cal > 0 else 0.0
        util = (horas_trab / horas_disp * 100) if horas_disp > 0 else 0.0
        rend = (disp * util) / 100.0
        return disp, util, rend

    rows = []
    for modelo, df_grp in df_f.groupby("nome_modelo"):
        disp, util, rend = calc_indicadores(df_grp)
        rows.append({
            "nome_modelo": modelo,
            "disponibilidade": disp,
            "utilizacao": util,
            "rendimento": rend
        })
    disp_all, util_all, rend_all = calc_indicadores(df_f)
    total_row = pd.DataFrame([{
        "nome_modelo": "TOTAL",
        "disponibilidade": disp_all,
        "utilizacao": util_all,
        "rendimento": rend_all
    }])
    df_ind = pd.concat([pd.DataFrame(rows), total_row], ignore_index=True)
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
        dbc.Row(
            dbc.Col(
                html.H1(
                    "Produção e Indicadores",
                    className="text-center my-4 text-primary",
                    style={"fontFamily": "Arial, sans-serif"}
                ),
                width=12
            )
        ),
        dbc.Row(
            dbc.Col(
                html.Div(
                    [
                        html.P(
                            "Escolha se deseja visualizar o dia atual ou o dia anterior.",
                            style={"fontFamily": "Arial, sans-serif"}
                        ),
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
        # Stores para armazenar dados de produção e hora
        dcc.Store(id="rel4-producao-store"),
        dcc.Store(id="rel4-hora-store"),
        # 1) Tabela de Movimentação
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader(
                            html.H5(
                                "Movimentação (Dia Atual ou Dia Anterior)",
                                className="mb-0",
                                style={"fontFamily": "Arial, sans-serif"}
                            ),
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
                            html.H5(
                                "Viagens por Hora Trabalhada (Dia Atual ou Dia Anterior)",
                                style={"fontFamily": "Arial, sans-serif"}
                            ),
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
        dbc.Row([
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader(
                        html.H5(
                            "Indicadores - Escavação",
                            className="mb-0",
                            style={"fontFamily": "Arial, sans-serif"}
                        ),
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
                                page_size=10
                            ),
                            type="default"
                        )
                    )
                ], className="mb-4 shadow animate__animated animate__fadeInUp", style={"marginBottom": "30px"}),
                md=4
            ),
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader(
                        html.H5(
                            "Indicadores - Transporte",
                            className="mb-0",
                            style={"fontFamily": "Arial, sans-serif"}
                        ),
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
                                page_size=10
                            ),
                            type="default"
                        )
                    )
                ], className="mb-4 shadow animate__animated animate__fadeInUp", style={"marginBottom": "30px"}),
                md=4
            ),
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader(
                        html.H5(
                            "Indicadores - Perfuração",
                            className="mb-0",
                            style={"fontFamily": "Arial, sans-serif"}
                        ),
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
                                page_size=10
                            ),
                            type="default"
                        )
                    )
                ], className="mb-4 shadow animate__animated animate__fadeInUp", style={"marginBottom": "30px"}),
                md=4
            ),
        ], className="mt-2"),
        dbc.Row(
            dbc.Col(
                dcc.Link(
                    "Voltar para o Portal",
                    href="/",
                    className="btn btn-secondary",
                    style={"fontFamily": "Arial, sans-serif", "fontSize": "16px"}
                ),
                width=12,
                className="text-center my-4"
            )
        )
    ],
    fluid=True
)

# ===================== Callbacks =====================

@callback(
    Output("rel4-producao-store", "data"),
    Output("rel4-hora-store", "data"),
    Input("rel4-day-selector", "value")
)
def fetch_data_dia_escolhido(day_choice):
    if day_choice == "ontem":
        data_str = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
    else:
        data_str = datetime.now().strftime("%d/%m/%Y")
    df_prod = consulta_producao(data_str)
    df_hora = consulta_hora(data_str)
    return (
        df_prod.to_json(date_format="iso", orient="records") if not df_prod.empty else {},
        df_hora.to_json(date_format="iso", orient="records") if not df_hora.empty else {}
    )

@callback(
    Output("rel4-tabela-movimentacao", "data"),
    Output("rel4-tabela-movimentacao", "style_data_conditional"),
    Input("rel4-producao-store", "data"),
    Input("rel4-day-selector", "value")
)
def update_tabela_movimentacao(json_prod, day_choice):
    if not json_prod or isinstance(json_prod, dict):
        return [], []
    df = pd.read_json(json_prod, orient="records")
    if df.empty:
        return [], []
    df = df[df["nome_operacao"].isin(["Movimentação Minério", "Movimentação Estéril"])]
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

@callback(
    Output("rel4-grafico-viagens-hora", "figure"),
    Input("rel4-producao-store", "data"),
    Input("rel4-hora-store", "data")
)
def update_grafico_viagens_hora(json_prod, json_hora):
    if (not json_prod or isinstance(json_prod, dict)) or (not json_hora or isinstance(json_hora, dict)):
        return px.bar(title="Sem dados para o período.", template="plotly_white")
    df_prod = pd.read_json(json_prod, orient="records")
    df_hora = pd.read_json(json_hora, orient="records")
    if df_prod.empty or df_hora.empty:
        return px.bar(title="Sem dados para o período.", template="plotly_white")
    df_prod = df_prod[df_prod["nome_operacao"].isin(["Movimentação Minério", "Movimentação Estéril"])]
    if df_prod.empty:
        return px.bar(title="Sem dados (Minério/Estéril).", template="plotly_white")
    df_viagens = df_prod.groupby("nome_equipamento_utilizado", as_index=False).agg(
        viagens=("nome_equipamento_utilizado", "count")
    )
    estados_trabalho = ["Operando", "Serviço Auxiliar", "Atraso Operacional"]
    df_hora_filtrada = df_hora[df_hora["nome_tipo_estado"].isin(estados_trabalho)]
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
    df_merged["viagens_por_hora"] = df_merged.apply(
        lambda row: row["viagens"] / row["horas_trabalhadas"] if row["horas_trabalhadas"] > 0 else 0,
        axis=1
    )
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

@callback(
    Output("rel4-tabela-ind-escavacao", "data"),
    Output("rel4-tabela-ind-escavacao", "columns"),
    Output("rel4-tabela-ind-escavacao", "style_data_conditional"),
    Input("rel4-hora-store", "data")
)
def update_tabela_ind_escavacao(json_hora):
    if not json_hora or isinstance(json_hora, dict):
        return [], [], []
    df_h = pd.read_json(json_hora, orient="records")
    if df_h.empty:
        return [], [], []
    data, columns, style_cond = calc_indicadores_agrupados_por_modelo(df_h, ESCAVACAO_MODELOS)
    return data, columns, style_cond

@callback(
    Output("rel4-tabela-ind-transporte", "data"),
    Output("rel4-tabela-ind-transporte", "columns"),
    Output("rel4-tabela-ind-transporte", "style_data_conditional"),
    Input("rel4-hora-store", "data")
)
def update_tabela_ind_transporte(json_hora):
    if not json_hora or isinstance(json_hora, dict):
        return [], [], []
    df_h = pd.read_json(json_hora, orient="records")
    if df_h.empty:
        return [], [], []
    data, columns, style_cond = calc_indicadores_agrupados_por_modelo(df_h, TRANSPORTE_MODELOS)
    return data, columns, style_cond

@callback(
    Output("rel4-tabela-ind-perfuracao", "data"),
    Output("rel4-tabela-ind-perfuracao", "columns"),
    Output("rel4-tabela-ind-perfuracao", "style_data_conditional"),
    Input("rel4-hora-store", "data")
)
def update_tabela_ind_perfuracao(json_hora):
    if not json_hora or isinstance(json_hora, dict):
        return [], [], []
    df_h = pd.read_json(json_hora, orient="records")
    if df_h.empty:
        return [], [], []
    data, columns, style_cond = calc_indicadores_agrupados_por_modelo(df_h, PERFURACAO_MODELOS)
    return data, columns, style_cond
