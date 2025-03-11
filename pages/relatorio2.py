import json
from datetime import datetime, timedelta

import dash
from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc
from dash.dash_table import DataTable, FormatTemplate
import plotly.express as px
import pandas as pd

# Import da função para consultar o banco e das variáveis de meta
from db import query_to_df
from config import META_MINERIO, META_ESTERIL

# Para formatar colunas numéricas no DataTable com separador de milhares e 2 casas decimais
from dash.dash_table.Format import Format, Scheme
num_format = Format(precision=2, scheme=Scheme.fixed, group=True)

layout = dbc.Container(
    [
        # Cabeçalho e Filtros
        dbc.Row(
            dbc.Col(
                html.H1("Relatório 2 - Fato Produção", className="text-center my-4 text-primary"),
                width=12
            )
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Label("Selecione o Período:", className="fw-bold text-secondary"),
                        dcc.DatePickerRange(
                            id="date-picker-range",
                            min_date_allowed=datetime(2020, 1, 1),
                            max_date_allowed=datetime.today().date(),
                            start_date=(datetime.today().date() - timedelta(days=7)),
                            end_date=datetime.today().date(),
                            display_format="DD/MM/YYYY",
                            className="mb-2"
                        ),
                        dbc.Button("Aplicar Filtro", id="apply-button", n_clicks=0, className="btn btn-primary mt-2")
                    ],
                    md=4
                ),
                dbc.Col(
                    [
                        html.Label("Filtrar por Operação (Produção):", className="fw-bold text-secondary"),
                        dcc.Dropdown(
                            id="operacao-dropdown",
                            placeholder="(Opcional) Selecione uma ou mais operações",
                            multi=True,
                            className="mb-2"
                        )
                    ],
                    md=8
                )
            ],
            className="my-2"
        ),
        dcc.Store(id="data-store"),
        html.Hr(),

        # Tabelas de Movimentação
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(html.H5("Movimentação (Último dia)", className="mb-0")),
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
                                        style_table={"overflowX": "auto"},
                                        style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
                                        style_cell={"textAlign": "center", "whiteSpace": "normal"}
                                    ),
                                    type="default"
                                )
                            )
                        ],
                        className="mb-4 shadow"
                    ),
                    md=6
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(html.H5("Movimentação (Acumulado)", className="mb-0")),
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
                                        style_table={"overflowX": "auto"},
                                        style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
                                        style_cell={"textAlign": "center", "whiteSpace": "normal"}
                                    ),
                                    type="default"
                                )
                            )
                        ],
                        className="mb-4 shadow"
                    ),
                    md=6
                )
            ],
            className="mt-2"
        ),
        html.Hr(),

        # Gráficos de Volume e Massa
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(html.H5("Gráfico de Volume")),
                            dbc.CardBody(
                                dcc.Loading(
                                    dcc.Graph(id="grafico-volume", config={"displayModeBar": False}),
                                    type="default"
                                )
                            )
                        ],
                        className="mb-4 shadow"
                    ),
                    md=12
                )
            ],
            className="mt-2"
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(html.H5("Gráfico de Massa")),
                            dbc.CardBody(
                                dcc.Loading(
                                    dcc.Graph(id="grafico-massa", config={"displayModeBar": False}),
                                    type="default"
                                )
                            )
                        ],
                        className="mb-4 shadow"
                    ),
                    md=12
                )
            ],
            className="mt-2"
        ),

        # Gráfico de Viagens por Hora Trabalhada (Último Dia)
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(html.H5("Viagens por Hora Trabalhada (Último Dia)")),
                            dbc.CardBody(
                                dcc.Loading(
                                    dcc.Graph(id="grafico-viagens-hora", config={"displayModeBar": False}),
                                    type="default"
                                )
                            )
                        ],
                        className="mb-4 shadow"
                    ),
                    md=12
                )
            ],
            className="mt-2"
        ),
        html.Hr(),

        # Filtro de Modelo para Indicadores
        dbc.Row(
            dbc.Col(
                [
                    html.Label("Filtrar por Modelo (Indicadores):", className="fw-bold text-secondary"),
                    dcc.Dropdown(
                        id="modelo-dropdown",
                        placeholder="(Opcional) Selecione um ou mais modelos (Equipamento)",
                        multi=True
                    )
                ],
                md=12
            ),
            className="mt-2"
        ),
        dcc.Store(id="data-store-hora"),
        html.Hr(),

        # Tabelas de Indicadores (apenas indicadores percentuais) – Último Dia e Acumulado
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(html.H5("Indicadores - Último Dia")),
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
                                        style_table={"overflowX": "auto"},
                                        style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
                                        style_cell={"textAlign": "center"}
                                    ),
                                    type="default"
                                )
                            )
                        ],
                        className="mb-4 shadow"
                    ),
                    md=6
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(html.H5("Indicadores - Acumulado")),
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
                                        style_table={"overflowX": "auto"},
                                        style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
                                        style_cell={"textAlign": "center"}
                                    ),
                                    type="default"
                                )
                            )
                        ],
                        className="mb-4 shadow"
                    ),
                    md=6
                )
            ],
            className="mt-4"
        ),
        html.Hr(),

        # Link de Navegação
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


# -------------------- Callbacks --------------------

# Callback para carregar dados de fato_producao
@callback(
    Output("data-store", "data"),
    Input("apply-button", "n_clicks"),
    State("date-picker-range", "start_date"),
    State("date-picker-range", "end_date"),
    prevent_initial_call=True
)
def apply_filter(n_clicks, start_date, end_date):
    if not start_date or not end_date:
        return {}
    start_date_obj = datetime.fromisoformat(start_date)
    end_date_obj = datetime.fromisoformat(end_date)
    start_date_str = start_date_obj.strftime("%d/%m/%Y")
    end_date_str = end_date_obj.strftime("%d/%m/%Y")

    query = f"""
    EXEC dw_sdp_mt_fas..usp_fato_producao
        '{start_date_str}',
        '{end_date_str}'
    """
    try:
        df = query_to_df(query)
    except Exception as e:
        return {"error": str(e)}

    if df.empty:
        return {}

    # Converte dt_registro_turno para datetime, se existir
    if "dt_registro_turno" in df.columns:
        df["dt_registro_turno"] = pd.to_datetime(df["dt_registro_turno"], errors="coerce")
        df.dropna(subset=["dt_registro_turno"], inplace=True)

    # Filtra dentro do range
    df = df[(df["dt_registro_turno"] >= start_date_obj) & (df["dt_registro_turno"] <= end_date_obj)]

    # Remove linhas sem nome_operacao
    df.dropna(subset=["nome_operacao"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df.to_json(date_format="iso", orient="records")


# Callback para atualizar o dropdown de operação
@callback(
    Output("operacao-dropdown", "options"),
    Input("data-store", "data")
)
def update_operacoes_options(json_data):
    if not json_data:
        return []
    if isinstance(json_data, dict) and "error" in json_data:
        return []
    df = pd.read_json(json_data, orient="records")
    if df.empty:
        return []
    ops_unicas = sorted(df["nome_operacao"].unique())
    return [{"label": op, "value": op} for op in ops_unicas]


# Callback para as Tabelas de Movimentação (Último dia e Acumulado)
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
def update_tables(json_data, operacoes_selecionadas, start_date, end_date):
    if not json_data:
        return [], [], [], [], [], []
    if isinstance(json_data, dict) and "error" in json_data:
        return [], [], [], [], [], []

    df = pd.read_json(json_data, orient="records")
    if df.empty:
        return [], [], [], [], [], []

    # Garante que dt_registro_turno esteja em formato datetime
    if "dt_registro_turno" not in df.columns:
        return [], [], [], [], [], []
    if not pd.api.types.is_datetime64_any_dtype(df["dt_registro_turno"]):
        df["dt_registro_turno"] = pd.to_datetime(df["dt_registro_turno"], errors="coerce")
    df.dropna(subset=["dt_registro_turno"], inplace=True)
    if df.empty:
        return [], [], [], [], [], []

    if operacoes_selecionadas:
        df = df[df["nome_operacao"].isin(operacoes_selecionadas)]
    if df.empty:
        return [], [], [], [], [], []

    # Movimentação (Último dia)
    ultimo_dia = df["dt_registro_turno"].dt.date.max()
    df_last_day = df[df["dt_registro_turno"].dt.date == ultimo_dia]

    df_t1 = df_last_day.groupby("nome_operacao", as_index=False).agg(
        viagens=("nome_operacao", "size"),
        volume=("volume", "sum"),
        massa=("massa", "sum")
    )
    total_t1 = pd.DataFrame({
        "nome_operacao": ["TOTAL"],
        "viagens": [df_t1["viagens"].sum()],
        "volume": [df_t1["volume"].sum()],
        "massa": [df_t1["massa"].sum()]
    })
    df_t1 = pd.concat([df_t1, total_t1], ignore_index=True)

    # Movimentação (Acumulado)
    df_t2 = df.groupby("nome_operacao", as_index=False).agg(
        viagens=("nome_operacao", "size"),
        volume=("volume", "sum"),
        massa=("massa", "sum")
    )
    total_t2 = pd.DataFrame({
        "nome_operacao": ["TOTAL"],
        "viagens": [df_t2["viagens"].sum()],
        "volume": [df_t2["volume"].sum()],
        "massa": [df_t2["massa"].sum()]
    })
    df_t2 = pd.concat([df_t2, total_t2], ignore_index=True)

    # Formatação condicional para tabela-1 (último dia)
    meta_total_last = META_MINERIO + META_ESTERIL
    style_cond_t1 = [
        {"if": {"filter_query": '{nome_operacao} = "TOTAL" && {volume} >= ' + str(meta_total_last),
                "column_id": "volume"},
         "color": "rgb(0,55,158)"},
        {"if": {"filter_query": '{nome_operacao} = "TOTAL" && {volume} < ' + str(meta_total_last),
                "column_id": "volume"},
         "color": "red"},
        {"if": {"filter_query": '{nome_operacao} = "TOTAL"'},
         "backgroundColor": "#fff9c4", "fontWeight": "bold"}
    ]

    # Formatação condicional para tabela-2 (acumulado)
    start_date_obj = datetime.fromisoformat(start_date)
    end_date_obj = datetime.fromisoformat(end_date)
    n_days = (end_date_obj - start_date_obj).days + 1
    meta_total_acc = n_days * (META_MINERIO + META_ESTERIL)
    style_cond_t2 = [
        {"if": {"filter_query": '{nome_operacao} = "TOTAL" && {volume} >= ' + str(meta_total_acc),
                "column_id": "volume"},
         "color": "rgb(0,55,158)"},
        {"if": {"filter_query": '{nome_operacao} = "TOTAL" && {volume} < ' + str(meta_total_acc),
                "column_id": "volume"},
         "color": "red"},
        {"if": {"filter_query": '{nome_operacao} = "TOTAL"'},
         "backgroundColor": "#fff9c4", "fontWeight": "bold"}
    ]

    data_t1 = df_t1.to_dict("records")
    data_t2 = df_t2.to_dict("records")
    columns = [
        {"name": "Operação", "id": "nome_operacao"},
        {"name": "Viagens", "id": "viagens"},
        {"name": "Volume", "id": "volume", "type": "numeric", "format": num_format},
        {"name": "Massa", "id": "massa", "type": "numeric", "format": num_format}
    ]
    return data_t1, columns, style_cond_t1, data_t2, columns, style_cond_t2


# Callback para os Gráficos de Volume e Massa
@callback(
    Output("grafico-volume", "figure"),
    Output("grafico-massa", "figure"),
    Input("data-store", "data"),
    Input("operacao-dropdown", "value")
)
def update_graphs(json_data, operacoes_selecionadas):
    if not json_data:
        fig_empty = px.bar(title="Selecione um período para ver o gráfico.", template="plotly_white")
        return fig_empty, fig_empty
    if isinstance(json_data, dict) and "error" in json_data:
        msg = f"Erro ao consultar: {json_data['error']}"
        fig_err = px.bar(title=msg, template="plotly_white")
        return fig_err, fig_err

    df = pd.read_json(json_data, orient="records")
    if df.empty:
        fig_empty = px.bar(title="Sem dados no período.", template="plotly_white")
        return fig_empty, fig_empty

    # Converte dt_registro_turno para datetime, se ainda não estiver
    if "dt_registro_turno" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["dt_registro_turno"]):
        df["dt_registro_turno"] = pd.to_datetime(df["dt_registro_turno"], errors="coerce")
    if "dt_registro_turno" not in df.columns:
        fig_err = px.bar(title="Coluna dt_registro_turno inexistente.", template="plotly_white")
        return fig_err, fig_err
    df.dropna(subset=["dt_registro_turno"], inplace=True)

    if operacoes_selecionadas:
        df = df[df["nome_operacao"].isin(operacoes_selecionadas)]
    if df.empty:
        fig_empty = px.bar(title="Sem dados para esse filtro.", template="plotly_white")
        return fig_empty, fig_empty

    df["dia"] = df["dt_registro_turno"].dt.date

    df_grouped = df.groupby("dia", as_index=False).agg(volume=("volume", "sum"), massa=("massa", "sum")).sort_values("dia")

    # Meta total diária
    meta_total = META_MINERIO + META_ESTERIL
    df_grouped["bar_color"] = df_grouped["volume"].apply(lambda x: "rgb(149,211,36)" if x >= meta_total else "red")

    # Gráfico de Volume
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

    # Gráfico de Massa
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


# Callback para o Gráfico de Viagens por Hora Trabalhada (Último Dia)
@callback(
    Output("grafico-viagens-hora", "figure"),
    Input("data-store", "data"),
    Input("data-store-hora", "data"),
    Input("date-picker-range", "end_date"),
    Input("operacao-dropdown", "value")
)
def update_grafico_viagens_hora(json_prod, json_hora, end_date, operacoes_selecionadas):
    if not json_prod or not json_hora or not end_date:
        return px.bar(title="Sem dados para gerar o gráfico de Viagens por Hora Trabalhada.", template="plotly_white")

    try:
        df_prod = pd.read_json(json_prod, orient="records")
        df_hora = pd.read_json(json_hora, orient="records")
    except Exception as e:
        return px.bar(title=f"Erro ao carregar dados: {str(e)}", template="plotly_white")

    # Converter dt_registro_turno para datetime (produção)
    if "dt_registro_turno" not in df_prod.columns:
        return px.bar(title="dt_registro_turno ausente em Produção.", template="plotly_white")
    if not pd.api.types.is_datetime64_any_dtype(df_prod["dt_registro_turno"]):
        df_prod["dt_registro_turno"] = pd.to_datetime(df_prod["dt_registro_turno"], errors="coerce")
    df_prod.dropna(subset=["dt_registro_turno"], inplace=True)

    # Converter dt_registro_turno para datetime (hora)
    if "dt_registro_turno" not in df_hora.columns:
        return px.bar(title="dt_registro_turno ausente em Hora.", template="plotly_white")
    if not pd.api.types.is_datetime64_any_dtype(df_hora["dt_registro_turno"]):
        df_hora["dt_registro_turno"] = pd.to_datetime(df_hora["dt_registro_turno"], errors="coerce")
    df_hora.dropna(subset=["dt_registro_turno"], inplace=True)

    filtro_dia = datetime.fromisoformat(end_date).date()
    df_prod = df_prod[df_prod["dt_registro_turno"].dt.date == filtro_dia]
    df_hora = df_hora[df_hora["dt_registro_turno"].dt.date == filtro_dia]

    if operacoes_selecionadas:
        df_prod = df_prod[df_prod["nome_operacao"].isin(operacoes_selecionadas)]

    if df_prod.empty or df_hora.empty:
        return px.bar(title="Sem dados para gerar o gráfico de Viagens por Hora Trabalhada.", template="plotly_white")

    df_viagens = df_prod.groupby("nome_equipamento_utilizado", as_index=False).agg(
        viagens=("nome_equipamento_utilizado", "count")
    )

    # Estados considerados "horas trabalhadas"
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

    df_merged["viagens_por_hora"] = df_merged.apply(
        lambda row: row["viagens"] / row["horas_trabalhadas"] if row["horas_trabalhadas"] > 0 else 0,
        axis=1
    )
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


# Callback para carregar dados de fato_hora
@callback(
    Output("data-store-hora", "data"),
    Output("modelo-dropdown", "options"),
    Input("apply-button", "n_clicks"),
    State("date-picker-range", "start_date"),
    State("date-picker-range", "end_date"),
    prevent_initial_call=True
)
def query_fato_hora(n_clicks, start_date, end_date):
    if not start_date or not end_date:
        return {}, []
    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date)
    s_start = start_dt.strftime("%d/%m/%Y")
    s_end = end_dt.strftime("%d/%m/%Y")

    query_hora = f"EXEC dw_sdp_mt_fas..usp_fato_hora '{s_start}', '{s_end}'"
    try:
        df_h = query_to_df(query_hora)
    except Exception as e:
        return {"error": str(e)}, []

    if df_h.empty:
        return {}, []

    if "dt_registro" in df_h.columns:
        df_h["dt_registro"] = pd.to_datetime(df_h["dt_registro"], errors="coerce")

    # Verificar colunas necessárias
    for col in ["nome_modelo", "nome_tipo_equipamento", "nome_tipo_estado", "tempo_hora"]:
        if col not in df_h.columns:
            return ({"error": f"Coluna '{col}' não existe em fato_hora"}, [])

    modelos_unicos = sorted(df_h["nome_modelo"].dropna().unique())
    op_modelos = [{"label": m, "value": m} for m in modelos_unicos]

    return df_h.to_json(date_format="iso", orient="records"), op_modelos


# Callback para as Tabelas de Indicadores (Último Dia e Acumulado)
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
def update_tabelas_indicadores(json_data_hora, lista_modelos, end_date):
    if not json_data_hora or (isinstance(json_data_hora, dict) and "error" in json_data_hora):
        return [], [], [], [], [], []

    df_h = pd.read_json(json_data_hora, orient="records")
    if df_h.empty:
        return [], [], [], [], [], []

    # Converter dt_registro_turno se existir
    if "dt_registro_turno" in df_h.columns and not pd.api.types.is_datetime64_any_dtype(df_h["dt_registro_turno"]):
        df_h["dt_registro_turno"] = pd.to_datetime(df_h["dt_registro_turno"], errors="coerce")

    if lista_modelos:
        df_h = df_h[df_h["nome_modelo"].isin(lista_modelos)]
        if df_h.empty:
            return [], [], [], [], [], []

    df_h["tempo_hora"] = pd.to_numeric(df_h["tempo_hora"], errors="coerce").fillna(0)

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

    # Último dia
    if end_date:
        filtro_dia = datetime.fromisoformat(end_date).date()
        if "dt_registro_turno" in df_h.columns:
            df_last = df_h[df_h["dt_registro_turno"].dt.date == filtro_dia]
        else:
            df_last = df_h.copy()
    else:
        df_last = df_h.copy()

    rows_t1 = []
    for equip, df_grp in df_last.groupby("nome_tipo_equipamento"):
        disp, util, rend = calc_indicadores(df_grp)
        rows_t1.append({
            "nome_tipo_equipamento": equip,
            "disponibilidade": disp,
            "utilizacao": util,
            "rendimento": rend
        })
    df_t1 = pd.DataFrame(rows_t1)
    if not df_last.empty:
        disp, util, rend = calc_indicadores(df_last)
        total_1 = pd.DataFrame([{
            "nome_tipo_equipamento": "TOTAL",
            "disponibilidade": disp,
            "utilizacao": util,
            "rendimento": rend
        }])
        df_t1 = pd.concat([df_t1, total_1], ignore_index=True)

    # Acumulado
    rows_t2 = []
    for equip, df_grp in df_h.groupby("nome_tipo_equipamento"):
        disp, util, rend = calc_indicadores(df_grp)
        rows_t2.append({
            "nome_tipo_equipamento": equip,
            "disponibilidade": disp,
            "utilizacao": util,
            "rendimento": rend
        })
    df_t2 = pd.DataFrame(rows_t2)
    if not df_h.empty:
        disp, util, rend = calc_indicadores(df_h)
        total_2 = pd.DataFrame([{
            "nome_tipo_equipamento": "TOTAL",
            "disponibilidade": disp,
            "utilizacao": util,
            "rendimento": rend
        }])
        df_t2 = pd.concat([df_t2, total_2], ignore_index=True)

    data_t1 = df_t1.to_dict("records")
    data_t2 = df_t2.to_dict("records")

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
