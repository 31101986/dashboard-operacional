import logging
from datetime import datetime, timedelta

import dash
from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc
import dash_table
import pandas as pd
import plotly.express as px
from dash_table.Format import Format, Scheme
from dash_table import FormatTemplate
from pandas.api.types import CategoricalDtype

# -------------------- Configuração de Logging --------------------
logging.basicConfig(
    level=logging.INFO,
    filename="relatorio3.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Constante para o período de busca: do dia atual até 45 dias atrás
today = datetime.today().date()
start_default = today - timedelta(days=45)
end_default = today

# Tabelas de custo unitário (R$/m³) por faixa para Movimentação Minério e Estéril
CUSTO_MINERO_MAP = {
    "0-500": 10.9517831011859,
    "501-1000": 11.4656811042058,
    "1001-1500": 11.9061651067943,
    "1501-2000": 12.1631141083042,
    "2001-2500": 12.9494196213316,
    "2501-3000": 14.3882440237018,
    "3001-3500": 16.1468071821542,
    "3501-4000": 17.9053703406067,
    "4001-4500": 19.8238028771002,
    "4501-5000": 22.0619741696761,
    "5001-5500": 24.3001454622519,
    "5501-6000": 26.85805551091,
    "6001-6500": 29.4159655595681,
    "6501-7000": 32.1337449862673
}

CUSTO_ESTERIL_MAP = {
    "0-500": 10.515151785518,
    "501-1000": 10.9135122505256,
    "1001-1500": 11.2756581278053,
    "1501-2000": 11.4929456541731,
    "2001-2500": 11.7102331805409,
    "2501-3000": 11.9637352946367,
    "3001-3500": 12.7757073622779,
    "3501-4000": 14.195230402531,
    "4001-4500": 15.6147534427841,
    "4501-5000": 17.5074508297882,
    "5001-5500": 19.242423434542,
    "5501-6000": 21.2928456037964,
    "6001-6500": 23.3432677730509,
    "6501-7000": 25.3936899423054
}

# Custos adicionais fixos (R$/m³)
CUSTO_CARGA_MINERO = 4.90818672114214
CUSTO_CARGA_ESTERIL = 3.72386776463452
CUSTO_ESPALHAMENTO_ESTERIL = 1.58371634448642

# Preço 60% por modelo (R$/h) para horas paradas
PRECO_60_MAP = {
    "ESCAVADEIRA HIDRÁULICA VOLVO EC750DL": 652.784394340166,
    "ESCAVADEIRA HIDRAULICA SANY SY750H": 652.784394340166,
    "ESCAVADEIRA HIDRÁULICA CAT 374DL": 652.784394340166,
    "ESCAVADEIRA HIDRÁULICA CAT 352": 462.241922478712,
    "ESCAVADEIRA HIDRAULICA CAT 336NGX": 299.927964967103,
    "ESCAVADEIRA HIDRÁULICA CAT 320": 229.356679092491,
    "ESCAVADEIRA HIDRÁULICA CAT 320 (ROMPEDOR)": 395.199200897830,
    "PÁ CARREGADEIRA CAT 966L": 292.870836379642,
    "MOTONIVELADORA CAT 140K": 257.585193442336,
    "MERCEDES BENZ AROCS 4851/45 8X4": 201.128164742646,
    "VOLVO FMX 500 8X4": 201.128164742646,
    "MERCEDES BENZ AXOR 3344 6X4 (PIPA)": 165.842521805339,
    "RETRO ESCAVADEIRA CAT 416F2": 151.728264630417,
    "TRATOR DE ESTEIRAS CAT D7": 504.584694003480,
    "TRATOR DE ESTEIRAS CAT D6T": 335.213607904410,
    "PERFURATRIZ HIDRAULICA SANDVIK DP1500I": 1030.531316241200,
    "PERFURATRIZ HIDRAULICA SANDVIK DX800": 808.111794550188,
    "ESCAVADEIRA HIDRÁULICA VOLVO EC480DL": 839.916000000000,
}

# Estados de parada para a tabela de horas paradas
ESTADOS_PARADA = ["Falta de Frente", "Falta de Combustível", "Aguardando Geologia", "Detonação", "Poeira"]

# Importa a função para consulta ao banco
from db import query_to_df

# -------------------- Funções Auxiliares --------------------
def get_search_period(start_date, end_date):
    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date)
    return start_dt, end_dt

def no_data_fig(title):
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

def execute_query(query):
    try:
        df = query_to_df(query)
        return df
    except Exception as e:
        logging.error(f"Erro na execução da query: {e}")
        return pd.DataFrame()

# -------------------- Layout do Relatório 3 (Boletim de Medição) --------------------
layout = dbc.Container([
    # Título Principal
    dbc.Row(
        dbc.Col(
            html.H2("Boletim de Medição - Relatório 3", className="text-center my-4 text-primary"),
            width=12
        )
    ),
    
    # Seção de Filtros
    dbc.Row([
        dbc.Col([
            html.Label("Selecione o Período:", className="fw-bold text-secondary mb-1"),
            dcc.DatePickerRange(
                id="rel3-date-picker-range",
                min_date_allowed=datetime(2020, 1, 1).date(),
                max_date_allowed=today,
                start_date=start_default,
                end_date=end_default,
                display_format="DD/MM/YYYY",
                className="mb-2"
            ),
        ], md=4),
        dbc.Col(
            dbc.Button("Aplicar Filtro", id="rel3-apply-button", n_clicks=0, color="primary", className="mt-4 w-100"),
            md=2
        ),
        dbc.Col(html.Div(), md=6)
    ], className="align-items-end mb-4"),
    
    # Armazenamento dos dados
    dcc.Store(id="rel3-data-store"),        # dados de fato_producao
    dcc.Store(id="rel3-fato-hora-store"),     # dados de fato_hora
    
    # 1) Tabela Principal (fato_producao)
    dbc.Card([
        dbc.CardHeader(html.H5("Tabela de Produção (fato_producao)", className="mb-0")),
        dbc.CardBody(
            dcc.Loading(
                dash_table.DataTable(
                    id="rel3-table",
                    columns=[],
                    data=[],
                    page_size=10,
                    style_table={"overflowX": "auto", "margin": "auto"},
                    style_cell={"textAlign": "center", "padding": "5px", "fontFamily": "Arial"}
                ),
                type="default"
            )
        )
    ], className="shadow mb-4"),
    
    # 2) Custos de Movimentação (Minério e Estéril)
    dbc.Card([
        dbc.CardHeader(html.H5("Custos de Movimentação", className="mb-0")),
        dbc.CardBody([
            html.H6("Movimentação Minério", className="text-secondary mt-2"),
            dcc.Loading(
                dash_table.DataTable(
                    id="rel3-custo-minero",
                    columns=[],
                    data=[],
                    page_size=5,
                    style_table={"overflowX": "auto", "margin": "auto"},
                    style_cell={
                        "textAlign": "center",
                        "padding": "5px",
                        "fontFamily": "Arial",
                        "whiteSpace": "normal"
                    },
                    style_data_conditional=[
                        {
                            'if': {'filter_query': '{dmt_bin} = "TOTAL"'},
                            'backgroundColor': '#fff9c4',
                            'fontWeight': 'bold'
                        }
                    ],
                    export_format="csv"
                ),
                type="default"
            ),
            html.Hr(),
            html.H6("Movimentação Estéril", className="text-secondary mt-2"),
            dcc.Loading(
                dash_table.DataTable(
                    id="rel3-custo-esteril",
                    columns=[],
                    data=[],
                    page_size=5,
                    style_table={"overflowX": "auto", "margin": "auto"},
                    style_cell={
                        "textAlign": "center",
                        "padding": "5px",
                        "fontFamily": "Arial",
                        "whiteSpace": "normal"
                    },
                    style_data_conditional=[
                        {
                            'if': {'filter_query': '{dmt_bin} = "TOTAL"'},
                            'backgroundColor': '#fff9c4',
                            'fontWeight': 'bold'
                        }
                    ],
                    export_format="csv"
                ),
                type="default"
            ),
        ])
    ], className="shadow mb-4"),
    
    # 3) Custos Adicionais
    dbc.Card([
        dbc.CardHeader(html.H5("Custos Adicionais", className="mb-0")),
        dbc.CardBody(
            dcc.Loading(
                dash_table.DataTable(
                    id="rel3-custo-adicional",
                    columns=[],
                    data=[],
                    page_size=10,
                    style_table={"overflowX": "auto", "margin": "auto"},
                    style_cell={
                        "textAlign": "center",
                        "padding": "5px",
                        "fontFamily": "Arial",
                        "whiteSpace": "normal"
                    },
                    export_format="csv"
                ),
                type="default"
            )
        )
    ], className="shadow mb-4"),
    
    # 4) Tabela de fato_hora (Estados Improdutivos/Serviço Auxiliar)
    dbc.Card([
        dbc.CardHeader(html.H5("fato_hora - Estados Improdutivos/Serviço Auxiliar", className="mb-0")),
        dbc.CardBody(
            dcc.Loading(
                dash_table.DataTable(
                    id="rel3-fato-hora-table",
                    columns=[],
                    data=[],
                    page_size=10,
                    style_table={"overflowX": "auto", "margin": "auto"},
                    style_cell={"textAlign": "center", "padding": "5px", "fontFamily": "Arial"}
                ),
                type="default"
            )
        )
    ], className="shadow mb-4"),
    
    # 5) Tabela de Horas Paradas (Preço 60%) com linha TOTAL destacada
    dbc.Card([
        dbc.CardHeader(html.H5("Custo de Horas Paradas por Modelo (Preço 60%)", className="mb-0")),
        dbc.CardBody(
            dcc.Loading(
                dash_table.DataTable(
                    id="rel3-horas-paradas-table",
                    columns=[],
                    data=[],
                    page_size=10,
                    style_table={"overflowX": "auto", "margin": "auto"},
                    style_cell={"textAlign": "center", "padding": "5px", "fontFamily": "Arial"},
                    style_data_conditional=[
                        {
                            'if': {'filter_query': '{nome_modelo} = "TOTAL"'},
                            'backgroundColor': '#fff9c4',
                            'fontWeight': 'bold'
                        }
                    ],
                    export_format="csv"
                ),
                type="default"
            )
        )
    ], className="shadow mb-4"),
    
    # 6) Faturamento Final (3 linhas)
    dbc.Card([
        dbc.CardHeader(html.H5("Faturamento Final", className="mb-0")),
        dbc.CardBody(
            html.Div(id="rel3-total-geral", style={
                "fontSize": "20px",
                "fontWeight": "bold",
                "padding": "10px",
                "backgroundColor": "#fff9c4",
                "borderRadius": "5px"
            })
        )
    ], className="shadow mb-4")
    
], fluid=True)

# -------------------- Callbacks --------------------

# Callback 1: Atualiza o Store de fato_producao
@callback(
    Output("rel3-data-store", "data"),
    Input("rel3-apply-button", "n_clicks"),
    State("rel3-date-picker-range", "start_date"),
    State("rel3-date-picker-range", "end_date"),
    prevent_initial_call=True
)
def update_data_store(n_clicks, start_date, end_date):
    if not start_date or not end_date:
        return {}
    start_dt, end_dt = get_search_period(start_date, end_date)
    query = (
        f"EXEC dw_sdp_mt_fas..usp_fato_producao "
        f"'{start_dt.strftime('%d/%m/%Y %H:%M:%S')}', "
        f"'{end_dt.strftime('%d/%m/%Y %H:%M:%S')}'"
    )
    df = execute_query(query)
    if df.empty:
        return {}
    df["dt_registro_turno"] = pd.to_datetime(df["dt_registro_turno"], errors="coerce")
    df = df[(df["dt_registro_turno"] >= start_dt) & (df["dt_registro_turno"] <= end_dt)]
    df = df[df["cod_viagem"].notnull() & (df["cod_viagem"] != "")]
    df = df[df["nome_tipo_operacao_modelo"] == "Transporte"]
    
    df["dmt_mov_cheio"] = df["dmt_mov_cheio"].fillna(0)
    df["dmt_tratado"] = df["dmt_mov_cheio"]
    cond = (df["dmt_mov_cheio"] <= 50) | (df["dmt_mov_cheio"] > 7000)
    
    group_means = df.groupby(["nome_origem", "nome_destino"])["dmt_mov_cheio"].transform("mean")
    group_counts = df.groupby(["nome_origem", "nome_destino"])["dmt_mov_cheio"].transform("count")
    mask = cond & (group_counts > 1)
    df.loc[mask, "dmt_tratado"] = group_means[mask].apply(lambda x: 7000 if x > 7000 else x)
    
    bins = [0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500, 7000]
    labels = [
        "0-500", "501-1000", "1001-1500", "1501-2000", "2001-2500",
        "2501-3000", "3001-3500", "3501-4000", "4001-4500", "4501-5000",
        "5001-5500", "5501-6000", "6001-6500", "6501-7000"
    ]
    cat_type = CategoricalDtype(categories=labels, ordered=True)
    df["dmt_bin"] = pd.cut(df["dmt_tratado"], bins=bins, labels=labels, include_lowest=True, right=True).astype(cat_type)
    
    return df.to_json(date_format="iso", orient="records")

# Callback 2: Atualiza a tabela principal (fato_producao)
@callback(
    Output("rel3-table", "data"),
    Output("rel3-table", "columns"),
    Input("rel3-data-store", "data")
)
def update_table(json_data):
    if not json_data:
        return [], []
    df = pd.read_json(json_data, orient="records", convert_dates=["dt_registro_turno"])
    if df.empty:
        return [], []
    columns = [{"name": col, "id": col} for col in df.columns]
    data = df.to_dict("records")
    return data, columns

# Callback 3: Custo da Movimentação - Minério
@callback(
    Output("rel3-custo-minero", "data"),
    Output("rel3-custo-minero", "columns"),
    Input("rel3-data-store", "data")
)
def update_custo_minero(json_data):
    if not json_data:
        return [], []
    df = pd.read_json(json_data, orient="records")
    df_minero = df[df["nome_operacao"] == "Movimentação Minério"]
    if df_minero.empty:
        return [], []
    df_group = df_minero.drop_duplicates(subset=["cod_viagem", "dmt_bin"]).groupby("dmt_bin", as_index=False).agg(total_volume=("volume", "sum"))
    df_group["custo_unitario"] = df_group["dmt_bin"].map(CUSTO_MINERO_MAP)
    df_group["custo_total"] = df_group["total_volume"] * df_group["custo_unitario"]
    
    total_vol = df_group["total_volume"].sum()
    total_custo = df_group["custo_total"].sum()
    df_total = pd.DataFrame([{
        "dmt_bin": "TOTAL",
        "total_volume": total_vol,
        "custo_unitario": "",
        "custo_total": total_custo
    }])
    df_group = pd.concat([df_group, df_total], ignore_index=True)
    
    columns = [
        {"name": "Faixa de DMT", "id": "dmt_bin"},
        {"name": "Volume Total (m³)", "id": "total_volume", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed, group=True)},
        {"name": "Custo Unitário (R$/m³)", "id": "custo_unitario", "type": "numeric", "format": FormatTemplate.money(2)},
        {"name": "Custo Total (R$)", "id": "custo_total", "type": "numeric", "format": FormatTemplate.money(2)}
    ]
    data = df_group.to_dict("records")
    return data, columns

# Callback 4: Custo da Movimentação - Estéril
@callback(
    Output("rel3-custo-esteril", "data"),
    Output("rel3-custo-esteril", "columns"),
    Input("rel3-data-store", "data")
)
def update_custo_esteril(json_data):
    if not json_data:
        return [], []
    df = pd.read_json(json_data, orient="records")
    df_esteril = df[df["nome_operacao"] == "Movimentação Estéril"]
    if df_esteril.empty:
        return [], []
    df_group = df_esteril.drop_duplicates(subset=["cod_viagem", "dmt_bin"]).groupby("dmt_bin", as_index=False).agg(total_volume=("volume", "sum"))
    df_group["custo_unitario"] = df_group["dmt_bin"].map(CUSTO_ESTERIL_MAP)
    df_group["custo_total"] = df_group["total_volume"] * df_group["custo_unitario"]
    
    total_vol = df_group["total_volume"].sum()
    total_custo = df_group["custo_total"].sum()
    df_total = pd.DataFrame([{
        "dmt_bin": "TOTAL",
        "total_volume": total_vol,
        "custo_unitario": "",
        "custo_total": total_custo
    }])
    df_group = pd.concat([df_group, df_total], ignore_index=True)
    
    columns = [
        {"name": "Faixa de DMT", "id": "dmt_bin"},
        {"name": "Volume Total (m³)", "id": "total_volume", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed, group=True)},
        {"name": "Custo Unitário (R$/m³)", "id": "custo_unitario", "type": "numeric", "format": FormatTemplate.money(2)},
        {"name": "Custo Total (R$)", "id": "custo_total", "type": "numeric", "format": FormatTemplate.money(2)}
    ]
    data = df_group.to_dict("records")
    return data, columns

# Callback 5: Custos Adicionais (sem linha TOTAL)
@callback(
    Output("rel3-custo-adicional", "data"),
    Output("rel3-custo-adicional", "columns"),
    Input("rel3-data-store", "data")
)
def update_custo_adicional(json_data):
    if not json_data:
        return [], []
    df = pd.read_json(json_data, orient="records")
    df_minero = df[df["nome_operacao"] == "Movimentação Minério"].drop_duplicates(subset=["cod_viagem"])
    df_esteril = df[df["nome_operacao"] == "Movimentação Estéril"].drop_duplicates(subset=["cod_viagem"])
    
    vol_minero = df_minero["volume"].sum() if not df_minero.empty else 0
    vol_esteril = df_esteril["volume"].sum() if not df_esteril.empty else 0
    
    custo_carga_minero = vol_minero * CUSTO_CARGA_MINERO
    custo_carga_esteril = vol_esteril * CUSTO_CARGA_ESTERIL
    custo_espalhamento = vol_esteril * CUSTO_ESPALHAMENTO_ESTERIL
    
    df_adic = pd.DataFrame([
        {
            "item": "Carga de Minério da Mina para Britagem/Pátio",
            "volume_total (m³)": vol_minero,
            "custo_unitario (R$/m³)": CUSTO_CARGA_MINERO,
            "custo_total (R$)": custo_carga_minero
        },
        {
            "item": "Carga de Estéril para Depósitos/Barragem",
            "volume_total (m³)": vol_esteril,
            "custo_unitario (R$/m³)": CUSTO_CARGA_ESTERIL,
            "custo_total (R$)": custo_carga_esteril
        },
        {
            "item": "Espalhamento de Estéril nos Depósitos",
            "volume_total (m³)": vol_esteril,
            "custo_unitario (R$/m³)": CUSTO_ESPALHAMENTO_ESTERIL,
            "custo_total (R$)": custo_espalhamento
        }
    ])
    
    columns = [
        {"name": "Item", "id": "item"},
        {"name": "Volume Total (m³)", "id": "volume_total (m³)", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed, group=True)},
        {"name": "Custo Unitário (R$/m³)", "id": "custo_unitario (R$/m³)", "type": "numeric", "format": FormatTemplate.money(2)},
        {"name": "Custo Total (R$)", "id": "custo_total (R$)", "type": "numeric", "format": FormatTemplate.money(2)}
    ]
    data = df_adic.to_dict("records")
    return data, columns

# Callback 6: Consulta fato_hora e armazena no rel3-fato-hora-store
@callback(
    Output("rel3-fato-hora-store", "data"),
    Input("rel3-apply-button", "n_clicks"),
    State("rel3-date-picker-range", "start_date"),
    State("rel3-date-picker-range", "end_date"),
    prevent_initial_call=True
)
def update_fato_hora_store(n_clicks, start_date, end_date):
    if not start_date or not end_date:
        return {}
    start_dt, end_dt = get_search_period(start_date, end_date)
    query = (
        f"EXEC dw_sdp_mt_fas..usp_fato_hora "
        f"'{start_dt.strftime('%d/%m/%Y %H:%M:%S')}', "
        f"'{end_dt.strftime('%d/%m/%Y %H:%M:%S')}'"
    )
    df = execute_query(query)
    if df.empty:
        return {}
    df["dt_registro_turno"] = pd.to_datetime(df["dt_registro_turno"], errors="coerce")
    df = df[(df["dt_registro_turno"] >= start_dt) & (df["dt_registro_turno"] <= end_dt)]
    # Filtra para estados improdutivos/serviço auxiliar
    estados_filtro = ["Improdutiva Interna", "Improdutiva Externa", "Serviço Auxiliar"]
    df = df[df["nome_tipo_estado"].isin(estados_filtro)]
    return df.to_json(date_format="iso", orient="records")

# Callback 7: Atualiza a tabela de fato_hora
@callback(
    Output("rel3-fato-hora-table", "data"),
    Output("rel3-fato-hora-table", "columns"),
    Input("rel3-fato-hora-store", "data")
)
def update_fato_hora_table(json_data):
    if not json_data:
        return [], []
    df = pd.read_json(json_data, orient="records", convert_dates=["dt_registro_turno"])
    if df.empty:
        return [], []
    columns = [{"name": col, "id": col} for col in df.columns]
    data = df.to_dict("records")
    return data, columns

# Callback 8: Tabela de Horas Paradas (Preço 60%) por modelo com linha TOTAL destacada
@callback(
    Output("rel3-horas-paradas-table", "data"),
    Output("rel3-horas-paradas-table", "columns"),
    Input("rel3-fato-hora-store", "data")
)
def update_horas_paradas_table(json_data):
    if not json_data:
        return [], []
    df = pd.read_json(json_data, orient="records", convert_dates=["dt_registro_turno"])
    if df.empty:
        return [], []
    
    estados_parada = ["Falta de Frente", "Falta de Combustível", "Aguardando Geologia", "Detonação", "Poeira"]
    df_parada = df[df["nome_estado"].isin(estados_parada)]
    if df_parada.empty or "nome_modelo" not in df_parada.columns:
        return [], []
    
    df_group = df_parada.groupby("nome_modelo", as_index=False).agg(horas_paradas=("tempo_hora", "sum"))
    df_group["preco_60"] = df_group["nome_modelo"].map(PRECO_60_MAP).fillna(0)
    df_group["custo_total"] = df_group["horas_paradas"] * df_group["preco_60"]
    
    total_horas = df_group["horas_paradas"].sum()
    total_custo = df_group["custo_total"].sum()
    df_total = pd.DataFrame([{
        "nome_modelo": "TOTAL",
        "horas_paradas": total_horas,
        "preco_60": "",
        "custo_total": total_custo
    }])
    df_group = pd.concat([df_group, df_total], ignore_index=True)
    
    columns = [
        {"name": "Modelo", "id": "nome_modelo"},
        {"name": "Horas Paradas (h)", "id": "horas_paradas", "type": "numeric", "format": Format(precision=2, scheme=Scheme.fixed, group=True)},
        {"name": "Preço 60% (R$/h)", "id": "preco_60", "type": "numeric", "format": FormatTemplate.money(2)},
        {"name": "Custo Total (R$)", "id": "custo_total", "type": "numeric", "format": FormatTemplate.money(2)}
    ]
    data = df_group.to_dict("records")
    return data, columns

# Callback 9: Faturamento Final (3 linhas)
@callback(
    Output("rel3-total-geral", "children"),
    Input("rel3-data-store", "data"),
    Input("rel3-fato-hora-store", "data")
)
def update_faturamento_final(json_producao, json_hora):
    # 1) Faturamento (Escavação e Transporte)
    if not json_producao:
        faturamento_transporte = 0.0
    else:
        df_prod = pd.read_json(json_producao, orient="records")
        if df_prod.empty:
            faturamento_transporte = 0.0
        else:
            df_minero = df_prod[df_prod["nome_operacao"] == "Movimentação Minério"]
            total_minero = 0
            if not df_minero.empty:
                grp_minero = df_minero.drop_duplicates(subset=["cod_viagem", "dmt_bin"]).groupby("dmt_bin", as_index=False).agg(total_volume=("volume", "sum"))
                grp_minero["custo_unitario"] = grp_minero["dmt_bin"].map(CUSTO_MINERO_MAP)
                grp_minero["custo_total"] = grp_minero["total_volume"] * grp_minero["custo_unitario"]
                total_minero = grp_minero["custo_total"].sum()
            
            df_esteril = df_prod[df_prod["nome_operacao"] == "Movimentação Estéril"]
            total_esteril = 0
            if not df_esteril.empty:
                grp_esteril = df_esteril.drop_duplicates(subset=["cod_viagem", "dmt_bin"]).groupby("dmt_bin", as_index=False).agg(total_volume=("volume", "sum"))
                grp_esteril["custo_unitario"] = grp_esteril["dmt_bin"].map(CUSTO_ESTERIL_MAP)
                grp_esteril["custo_total"] = grp_esteril["total_volume"] * grp_esteril["custo_unitario"]
                total_esteril = grp_esteril["custo_total"].sum()
            
            df_minero_unique = df_prod[df_prod["nome_operacao"] == "Movimentação Minério"].drop_duplicates(subset=["cod_viagem"])
            df_esteril_unique = df_prod[df_prod["nome_operacao"] == "Movimentação Estéril"].drop_duplicates(subset=["cod_viagem"])
            vol_minero = df_minero_unique["volume"].sum() if not df_minero_unique.empty else 0
            vol_esteril = df_esteril_unique["volume"].sum() if not df_esteril_unique.empty else 0
            custo_carga_minero = vol_minero * CUSTO_CARGA_MINERO
            custo_carga_esteril = vol_esteril * CUSTO_CARGA_ESTERIL
            custo_espalhamento = vol_esteril * CUSTO_ESPALHAMENTO_ESTERIL
            
            faturamento_transporte = total_minero + total_esteril + (custo_carga_minero + custo_carga_esteril + custo_espalhamento)
    
    # 2) Faturamento Hora 60%
    if not json_hora:
        faturamento_hora = 0.0
    else:
        df_hora = pd.read_json(json_hora, orient="records")
        if df_hora.empty:
            faturamento_hora = 0.0
        else:
            df_parada = df_hora[df_hora["nome_estado"].isin(["Falta de Frente", "Falta de Combustível", "Aguardando Geologia", "Detonação", "Poeira"])]
            if df_parada.empty or "nome_modelo" not in df_parada.columns:
                faturamento_hora = 0.0
            else:
                df_group = df_parada.groupby("nome_modelo", as_index=False).agg(horas_paradas=("tempo_hora", "sum"))
                df_group["preco_60"] = df_group["nome_modelo"].map(PRECO_60_MAP).fillna(0)
                df_group["custo_total"] = df_group["horas_paradas"] * df_group["preco_60"]
                faturamento_hora = df_group["custo_total"].sum()
    
    # 3) Faturamento Total = soma dos dois
    faturamento_total = faturamento_transporte + faturamento_hora
    
    # Cria uma estrutura com três linhas formatadas, mantendo destaque semelhante às tabelas (fundo amarelo claro)
    return html.Div([
        html.Div(f"Faturamento (Escavação e Transporte): R$ {faturamento_transporte:,.2f}", style={"backgroundColor": "#fff9c4", "padding": "5px", "marginBottom": "5px"}),
        html.Div(f"Faturamento Hora 60%: R$ {faturamento_hora:,.2f}", style={"backgroundColor": "#fff9c4", "padding": "5px", "marginBottom": "5px"}),
        html.Div(f"Faturamento Total: R$ {faturamento_total:,.2f}", style={"backgroundColor": "#fff9c4", "padding": "5px", "marginBottom": "5px"})
    ])
    
layout = layout
