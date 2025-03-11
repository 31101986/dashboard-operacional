import math
import logging
from datetime import datetime, timedelta

import dash
from dash import dcc, html, callback, Input, Output
import dash_bootstrap_components as dbc
import dash_table
import plotly.express as px
import pandas as pd

from dash.dash_table.Format import Format, Scheme
from dash.dash_table import FormatTemplate

# Import da função para consultar o banco e das variáveis de meta
from db import query_to_df
from config import META_MINERIO, META_ESTERIL

logging.basicConfig(
    level=logging.INFO,
    filename="relatorio4.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)

num_format = Format(precision=2, scheme=Scheme.fixed, group=True)

###############################################################################
# Modelos para as 3 tabelas de indicadores
###############################################################################
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

###############################################################################
# Layout
###############################################################################
layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.H1("Relatório 4 - Dia Atual ou Dia Anterior", className="text-center my-4 text-primary"),
                width=12
            )
        ),

        # Seletor: Dia Atual ou Dia Anterior
        dbc.Row(
            dbc.Col(
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
                ),
                width=12
            ),
            className="mb-4"
        ),

        # 1) TABELA DE MOVIMENTAÇÃO
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader(html.H5("Movimentação (Dia Atual/Anterior)", className="mb-0")),
                        dbc.CardBody(
                            dcc.Loading(
                                dash_table.DataTable(
                                    id="rel4-tabela-movimentacao",
                                    columns=[
                                        {"name": "Operação", "id": "nome_operacao", "type": "text"},
                                        {"name": "Viagens", "id": "viagens", "type": "numeric", "format": num_format},
                                        {"name": "Volume", "id": "volume", "type": "numeric", "format": num_format},
                                        {
                                            "name": "Ritmo (m³/h)",
                                            "id": "ritmo_volume",
                                            "type": "numeric",
                                            "format": num_format
                                        },
                                    ],
                                    style_table={"overflowX": "auto"},
                                    style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
                                    style_cell={"textAlign": "center", "whiteSpace": "normal"},
                                    style_data_conditional=[],
                                    page_size=10
                                ),
                                type="default"
                            )
                        )
                    ],
                    className="mb-4 shadow"
                ),
                width=12
            ),
            className="mt-2"
        ),

        # 2) GRÁFICO DE VIAGENS POR HORA TRABALHADA
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader(html.H5("Viagens por Hora Trabalhada (Dia Atual/Anterior)")),
                        dbc.CardBody(
                            dcc.Loading(
                                dcc.Graph(id="rel4-grafico-viagens-hora", config={"displayModeBar": False}),
                                type="default"
                            )
                        )
                    ],
                    className="mb-4 shadow"
                ),
                width=12
            ),
            className="mt-2"
        ),

        # 3) TABELAS DE INDICADORES - 3 grupos
        dbc.Row([
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader(html.H5("Indicadores - Escavação")),
                    dbc.CardBody(
                        dcc.Loading(
                            dash_table.DataTable(
                                id="rel4-tabela-ind-escavacao",
                                columns=[],
                                data=[],
                                style_table={"overflowX": "auto"},
                                style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
                                style_cell={"textAlign": "center"},
                                style_data_conditional=[],
                                page_size=10
                            ),
                            type="default"
                        )
                    )
                ], className="mb-4 shadow"),
                md=4
            ),
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader(html.H5("Indicadores - Transporte")),
                    dbc.CardBody(
                        dcc.Loading(
                            dash_table.DataTable(
                                id="rel4-tabela-ind-transporte",
                                columns=[],
                                data=[],
                                style_table={"overflowX": "auto"},
                                style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
                                style_cell={"textAlign": "center"},
                                style_data_conditional=[],
                                page_size=10
                            ),
                            type="default"
                        )
                    )
                ], className="mb-4 shadow"),
                md=4
            ),
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader(html.H5("Indicadores - Perfuração")),
                    dbc.CardBody(
                        dcc.Loading(
                            dash_table.DataTable(
                                id="rel4-tabela-ind-perfuracao",
                                columns=[],
                                data=[],
                                style_table={"overflowX": "auto"},
                                style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
                                style_cell={"textAlign": "center"},
                                style_data_conditional=[],
                                page_size=10
                            ),
                            type="default"
                        )
                    )
                ], className="mb-4 shadow"),
                md=4
            ),
        ], className="mt-2"),

        # Link para voltar ao Portal
        dbc.Row(
            dbc.Col(
                dcc.Link("Voltar para o Portal", href="/", className="btn btn-secondary"),
                width=12,
                className="text-center my-4"
            )
        )
    ],
    fluid=True
)

###############################################################################
# FUNÇÕES AUXILIARES
###############################################################################
def get_datestr(day_choice):
    """
    Retorna a data no formato DD/MM/YYYY.
    - Se day_choice == "hoje": data atual
    - Se day_choice == "ontem": data atual - 1 dia
    """
    now = datetime.now()
    if day_choice == "ontem":
        now = now - timedelta(days=1)
    return now.strftime("%d/%m/%Y")

def get_producao_dia(day_choice):
    """
    Consulta 'usp_fato_producao' para a data (hoje ou ontem).
    Filtra dt_registro_turno para a data exata.
    """
    data_str = get_datestr(day_choice)
    query = f"EXEC dw_sdp_mt_fas..usp_fato_producao '{data_str}', '{data_str}'"
    try:
        df = query_to_df(query)
    except Exception as e:
        logging.error(f"Erro ao consultar fato_producao (rel4) - day={day_choice}: {e}")
        return pd.DataFrame()

    if df.empty:
        return df

    # Convert dt_registro_turno e filtra
    if "dt_registro_turno" in df.columns:
        df["dt_registro_turno"] = pd.to_datetime(df["dt_registro_turno"], errors="coerce")
        filter_date = datetime.strptime(data_str, "%d/%m/%Y").date()
        df = df[df["dt_registro_turno"].dt.date == filter_date]

    return df

def get_hora_dia(day_choice):
    """
    Consulta 'usp_fato_hora' para a data (hoje ou ontem).
    Filtra dt_registro_turno para a data exata.
    """
    data_str = get_datestr(day_choice)
    query = f"EXEC dw_sdp_mt_fas..usp_fato_hora '{data_str}', '{data_str}'"
    try:
        df = query_to_df(query)
    except Exception as e:
        logging.error(f"Erro ao consultar fato_hora (rel4) - day={day_choice}: {e}")
        return pd.DataFrame()

    if df.empty:
        return df

    if "dt_registro_turno" in df.columns:
        df["dt_registro_turno"] = pd.to_datetime(df["dt_registro_turno"], errors="coerce")
        filter_date = datetime.strptime(data_str, "%d/%m/%Y").date()
        df = df[df["dt_registro_turno"].dt.date == filter_date]

    return df

def calcular_horas_desde_7h(day_choice):
    """
    - Se day_choice == "ontem": assumimos 24h (dia anterior fechado).
    - Se day_choice == "hoje": calcula horas passadas desde 07:00 do dia atual.
    """
    if day_choice == "ontem":
        return 24.0
    else:
        now = datetime.now()
        start_7h = datetime(now.year, now.month, now.day, 7, 0)
        if now < start_7h:
            start_7h -= timedelta(days=1)
        horas_passadas = (now - start_7h).total_seconds() / 3600.0
        return max(horas_passadas, 0.01)

def calc_indicadores_agrupados_por_modelo(df, modelos_lista):
    if "nome_modelo" not in df.columns or "nome_tipo_estado" not in df.columns or "tempo_hora" not in df.columns:
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
    df_ind = pd.DataFrame(rows)

    # Linha TOTAL
    disp_all, util_all, rend_all = calc_indicadores(df_f)
    total_row = pd.DataFrame([{
        "nome_modelo": "TOTAL",
        "disponibilidade": disp_all,
        "utilizacao": util_all,
        "rendimento": rend_all
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

###############################################################################
# CALLBACK 1 - Tabela de Movimentação
###############################################################################
@callback(
    Output("rel4-tabela-movimentacao", "data"),
    Output("rel4-tabela-movimentacao", "style_data_conditional"),
    Input("rel4-tabela-movimentacao", "id"),
    Input("rel4-day-selector", "value")
)
def update_tabela_movimentacao(_, day_choice):
    df = get_producao_dia(day_choice)
    if df.empty:
        return [], []

    # Filtrar 2 operações
    df = df[df["nome_operacao"].isin(["Movimentação Minério", "Movimentação Estéril"])]
    if df.empty:
        return [], []

    # Agrupar
    df_grp = df.groupby("nome_operacao", as_index=False).agg(
        viagens=("nome_operacao", "size"),
        volume=("volume", "sum")
    )

    # Linha TOTAL
    total_line = pd.DataFrame({
        "nome_operacao": ["TOTAL"],
        "viagens": [df_grp["viagens"].sum()],
        "volume": [df_grp["volume"].sum()]
    })
    df_grp = pd.concat([df_grp, total_line], ignore_index=True)

    # Calcula Ritmo
    horas_decorridas = calcular_horas_desde_7h(day_choice)
    df_grp["ritmo_volume"] = (df_grp["volume"] / horas_decorridas) * 24.0

    meta_total = META_MINERIO + META_ESTERIL
    style_data_conditional = [
        {
            "if": {"filter_query": '{nome_operacao} = "TOTAL" && {volume} >= ' + str(meta_total)},
            "color": "rgb(0,55,158)",
            "column_id": "volume"
        },
        {
            "if": {"filter_query": '{nome_operacao} = "TOTAL" && {volume} < ' + str(meta_total)},
            "color": "red",
            "column_id": "volume"
        },
        {
            "if": {"filter_query": '{nome_operacao} = "TOTAL"'},
            "backgroundColor": "#fff9c4",
            "fontWeight": "bold"
        }
    ]

    data = df_grp.to_dict("records")
    return data, style_data_conditional

###############################################################################
# CALLBACK 2 - Gráfico de Viagens/Hora
###############################################################################
@callback(
    Output("rel4-grafico-viagens-hora", "figure"),
    Input("rel4-grafico-viagens-hora", "id"),
    Input("rel4-day-selector", "value")
)
def update_grafico_viagens_hora(_, day_choice):
    df_prod = get_producao_dia(day_choice)
    df_hora = get_hora_dia(day_choice)
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

    df_merged = pd.merge(df_viagens, df_horas,
                         left_on="nome_equipamento_utilizado",
                         right_on="nome_equipamento",
                         how="inner")
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

###############################################################################
# CALLBACKS - 3 Tabelas Indicadores
###############################################################################
@callback(
    Output("rel4-tabela-ind-escavacao", "data"),
    Output("rel4-tabela-ind-escavacao", "columns"),
    Output("rel4-tabela-ind-escavacao", "style_data_conditional"),
    Input("rel4-tabela-ind-escavacao", "id"),
    Input("rel4-day-selector", "value")
)
def update_tabela_ind_escavacao(_, day_choice):
    df_h = get_hora_dia(day_choice)
    if df_h.empty:
        return [], [], []
    return calc_indicadores_agrupados_por_modelo(df_h, ESCAVACAO_MODELOS)

@callback(
    Output("rel4-tabela-ind-transporte", "data"),
    Output("rel4-tabela-ind-transporte", "columns"),
    Output("rel4-tabela-ind-transporte", "style_data_conditional"),
    Input("rel4-tabela-ind-transporte", "id"),
    Input("rel4-day-selector", "value")
)
def update_tabela_ind_transporte(_, day_choice):
    df_h = get_hora_dia(day_choice)
    if df_h.empty:
        return [], [], []
    return calc_indicadores_agrupados_por_modelo(df_h, TRANSPORTE_MODELOS)

@callback(
    Output("rel4-tabela-ind-perfuracao", "data"),
    Output("rel4-tabela-ind-perfuracao", "columns"),
    Output("rel4-tabela-ind-perfuracao", "style_data_conditional"),
    Input("rel4-tabela-ind-perfuracao", "id"),
    Input("rel4-day-selector", "value")
)
def update_tabela_ind_perfuracao(_, day_choice):
    df_h = get_hora_dia(day_choice)
    if df_h.empty:
        return [], [], []
    return calc_indicadores_agrupados_por_modelo(df_h, PERFURACAO_MODELOS)
