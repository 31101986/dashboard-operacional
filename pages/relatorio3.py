import logging
from datetime import datetime, timedelta
from io import BytesIO

import dash
from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc
import dash_table
import pandas as pd
from dash_table.Format import Format, Scheme
from dash_table import FormatTemplate
from pandas.api.types import CategoricalDtype

from db import query_to_df

# Configuração do log
logging.basicConfig(
    level=logging.INFO,
    filename="relatorio3.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Variáveis de datas padrão
today = datetime.today().date()
start_default = today - timedelta(days=45)
end_default = today

# Mapas de custo e preço
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

CUSTO_CARGA_MINERO = 4.90818672114214
CUSTO_CARGA_ESTERIL = 3.72386776463452
CUSTO_ESPALHAMENTO_ESTERIL = 1.58371634448642

PRECO_60_MAP = {
    "ESCAVADEIRA HIDRÁULICA VOLVO EC750DL": 652.784394340166,
    "ESCAVADEIRA HIDRAULICA SANY SY750H": 652.784394340166,
    "ESCAVADEIRA HIDRÁULICA CAT 374DL": 652.784394340166,
    "ESCAVADEIRA HIDRÁULICA CAT 352": 462.241922478712,
    "ESCAVADEIRA HIDRÁULICA CAT 336NGX": 299.927964967103,
    "ESCAVADEIRA HIDRÁULICA CAT 320": 229.356679092491,
    "ESCAVADEIRA HIDRÁULICA CAT 320 (ROMPEDOR)": 395.19920089783,
    "MERCEDES BENZ AROCS 4851/45 8X4": 201.128164742646,
    "VOLVO FMX 500 8X4": 201.128164742646,
    "MERCEDES BENZ AXOR 3344 6X4 (PIPA)": 165.842521805339,
    "PERFURATRIZ HIDRAULICA SANDVIK DP1500I": 1030.5313162412,
    "ESCAVADEIRA HIDRÁULICA VOLVO EC480DL": 839.916000000000
}

ESTADOS_PARADA = ["Falta de Frente", "Falta de Combustível", "Aguardando Geologia", "Detonação", "Poeira"]

# Formato numérico com 2 casas e separador de milhar
num_format = Format(precision=2, scheme=Scheme.fixed, group=True)

# ===================== Funções Auxiliares =====================

def get_search_period(start_date, end_date):
    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date)
    return start_dt, end_dt

def execute_query(query):
    try:
        return query_to_df(query)
    except Exception as e:
        logging.error(f"Erro na execução da query: {e}")
        return pd.DataFrame()

def calc_custo_por_faixa(df, nome_operacao, custo_map):
    df_filtro = df[df["nome_operacao"] == nome_operacao]
    if df_filtro.empty:
        return pd.DataFrame()
    df_group = (
        df_filtro.drop_duplicates(subset=["cod_viagem", "dmt_bin"])
                 .groupby("dmt_bin", as_index=False)
                 .agg(total_volume=("volume", "sum"))
    )
    df_group["custo_unitario"] = df_group["dmt_bin"].map(custo_map)
    df_group["custo_total"] = df_group["total_volume"] * df_group["custo_unitario"]
    return df_group

def calc_custo_adicional(df):
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
    return df_adic

def calc_faturamento_transporte(df):
    df_minero = calc_custo_por_faixa(df, "Movimentação Minério", CUSTO_MINERO_MAP)
    total_minero = df_minero["custo_total"].sum() if not df_minero.empty else 0
    df_esteril = calc_custo_por_faixa(df, "Movimentação Estéril", CUSTO_ESTERIL_MAP)
    total_esteril = df_esteril["custo_total"].sum() if not df_esteril.empty else 0
    df_adic = calc_custo_adicional(df)
    total_adic = df_adic["custo_total (R$)"].sum()
    return total_minero + total_esteril + total_adic

def calc_faturamento_hora_60(df_hora):
    df_parada = df_hora[df_hora["nome_estado"].isin(ESTADOS_PARADA)]
    if df_parada.empty or "nome_modelo" not in df_parada.columns:
        return 0.0
    df_group = df_parada.groupby("nome_modelo", as_index=False).agg(horas_paradas=("tempo_hora", "sum"))
    df_group["preco_60"] = df_group["nome_modelo"].map(PRECO_60_MAP).fillna(0)
    df_group["custo_total"] = df_group["horas_paradas"] * df_group["preco_60"]
    return df_group["custo_total"].sum()

def build_export_excel_single_sheet(json_producao, json_hora):
    """
    Em vez de exportar a tabela base, essa função recria as seções exibidas no relatório:
    - Custos de Movimentação (Minério e Estéril)
    - Custos Adicionais
    - Horas Paradas por Modelo
    - Faturamento Final
    Tudo em uma única aba, com títulos separando cada seção.
    """
    df_prod = pd.read_json(json_producao, orient="records") if json_producao and not isinstance(json_producao, dict) else pd.DataFrame()
    df_hora = pd.read_json(json_hora, orient="records") if json_hora and not isinstance(json_hora, dict) else pd.DataFrame()
    
    # Seção 1: Custos de Movimentação - Minério
    if not df_prod.empty:
        df_minero = calc_custo_por_faixa(df_prod, "Movimentação Minério", CUSTO_MINERO_MAP)
        if not df_minero.empty:
            total_vol = df_minero["total_volume"].sum()
            total_custo = df_minero["custo_total"].sum()
            df_total_minero = pd.DataFrame([{
                "dmt_bin": "TOTAL",
                "total_volume": total_vol,
                "custo_unitario": "",
                "custo_total": total_custo
            }])
            df_minero = pd.concat([df_minero, df_total_minero], ignore_index=True)
        else:
            df_minero = pd.DataFrame()
    else:
        df_minero = pd.DataFrame()
    
    # Seção 2: Custos de Movimentação - Estéril
    if not df_prod.empty:
        df_esteril = calc_custo_por_faixa(df_prod, "Movimentação Estéril", CUSTO_ESTERIL_MAP)
        if not df_esteril.empty:
            total_vol = df_esteril["total_volume"].sum()
            total_custo = df_esteril["custo_total"].sum()
            df_total_esteril = pd.DataFrame([{
                "dmt_bin": "TOTAL",
                "total_volume": total_vol,
                "custo_unitario": "",
                "custo_total": total_custo
            }])
            df_esteril = pd.concat([df_esteril, df_total_esteril], ignore_index=True)
        else:
            df_esteril = pd.DataFrame()
    else:
        df_esteril = pd.DataFrame()
    
    # Seção 3: Custos Adicionais
    if not df_prod.empty:
        df_adic = calc_custo_adicional(df_prod)
    else:
        df_adic = pd.DataFrame()
    
    # Seção 4: Horas Paradas por Modelo
    if not df_hora.empty:
        df_parada = df_hora[df_hora["nome_estado"].isin(ESTADOS_PARADA)]
        if not df_parada.empty and "nome_modelo" in df_parada.columns:
            df_group = df_parada.groupby("nome_modelo", as_index=False).agg(horas_paradas=("tempo_hora", "sum"))
            df_group["preco_60"] = df_group["nome_modelo"].map(PRECO_60_MAP).fillna(0)
            df_group["custo_total"] = df_group["horas_paradas"] * df_group["preco_60"]
            total_horas = df_group["horas_paradas"].sum()
            total_custo = df_group["custo_total"].sum()
            df_total_horas = pd.DataFrame([{
                "nome_modelo": "TOTAL",
                "horas_paradas": total_horas,
                "preco_60": "",
                "custo_total": total_custo
            }])
            df_horas = pd.concat([df_group, df_total_horas], ignore_index=True)
        else:
            df_horas = pd.DataFrame()
    else:
        df_horas = pd.DataFrame()
    
    # Seção 5: Faturamento Final
    faturamento_transporte = calc_faturamento_transporte(df_prod) if not df_prod.empty else 0.0
    faturamento_hora = calc_faturamento_hora_60(df_hora) if not df_hora.empty else 0.0
    faturamento_total = faturamento_transporte + faturamento_hora
    df_faturamento = pd.DataFrame({
         "Descrição": ["Faturamento (Escavação e Transporte)", "Faturamento Hora 60%", "Faturamento Total"],
         "Valor": [faturamento_transporte, faturamento_hora, faturamento_total]
    })
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        sheet_name = "Dados"
        current_row = 0
        worksheet = writer.book.add_worksheet(sheet_name)
        writer.sheets[sheet_name] = worksheet
        
        # Seção 1: Custos de Movimentação - Minério
        worksheet.write(current_row, 0, "Custos de Movimentação - Minério")
        current_row += 1
        if not df_minero.empty:
            df_minero.to_excel(writer, sheet_name=sheet_name, startrow=current_row, index=False)
            current_row += len(df_minero.index) + 3
        else:
            worksheet.write(current_row, 0, "Sem dados")
            current_row += 3
        
        # Seção 2: Custos de Movimentação - Estéril
        worksheet.write(current_row, 0, "Custos de Movimentação - Estéril")
        current_row += 1
        if not df_esteril.empty:
            df_esteril.to_excel(writer, sheet_name=sheet_name, startrow=current_row, index=False)
            current_row += len(df_esteril.index) + 3
        else:
            worksheet.write(current_row, 0, "Sem dados")
            current_row += 3
        
        # Seção 3: Custos Adicionais
        worksheet.write(current_row, 0, "Custos Adicionais")
        current_row += 1
        if not df_adic.empty:
            df_adic.to_excel(writer, sheet_name=sheet_name, startrow=current_row, index=False)
            current_row += len(df_adic.index) + 3
        else:
            worksheet.write(current_row, 0, "Sem dados")
            current_row += 3
        
        # Seção 4: Horas Paradas por Modelo
        worksheet.write(current_row, 0, "Horas Paradas por Modelo")
        current_row += 1
        if not df_horas.empty:
            df_horas.to_excel(writer, sheet_name=sheet_name, startrow=current_row, index=False)
            current_row += len(df_horas.index) + 3
        else:
            worksheet.write(current_row, 0, "Sem dados")
            current_row += 3
        
        # Seção 5: Faturamento Final
        worksheet.write(current_row, 0, "Faturamento Final")
        current_row += 1
        df_faturamento.to_excel(writer, sheet_name=sheet_name, startrow=current_row, index=False)
    processed_data = output.getvalue()
    return processed_data

# ===================== LAYOUT =====================
layout = dbc.Container([
    dbc.Row(
        dbc.Col(
            html.H2(
                "Boletim de Medição",
                className="text-center my-4 text-primary",
                style={"fontFamily": "Arial, sans-serif"}
            ),
            width=12
        )
    ),
    dbc.Row([
        dbc.Col([
            html.Label(
                "Selecione o Período:",
                className="fw-bold text-secondary mb-1",
                style={"fontFamily": "Arial, sans-serif", "fontSize": "16px"}
            ),
            dcc.DatePickerRange(
                id="rel3-date-picker-range",
                min_date_allowed=datetime(2020, 1, 1).date(),
                max_date_allowed=today,
                start_date=start_default,
                end_date=end_default,
                display_format="DD/MM/YYYY",
                className="mb-2",
                style={"width": "100%"}
            )
        ], xs=12, md=4),
        dbc.Col(
            dbc.Button(
                "Aplicar Filtro",
                id="rel3-apply-button",
                n_clicks=0,
                color="primary",
                className="mt-4 w-100",
                style={"fontFamily": "Arial, sans-serif", "fontSize": "16px"}
            ),
            xs=12, md=2
        ),
        dbc.Col(html.Div(), xs=12, md=6)
    ], className="align-items-end mb-4"),

    # Stores para os dados de Produção e Hora
    dcc.Store(id="rel3-data-store"),
    dcc.Store(id="rel3-fato-hora-store"),

    # (2) Custos de Movimentação
    dbc.Card([
        dbc.CardHeader(
            html.H5("Custos de Movimentação", className="mb-0", style={"fontFamily": "Arial, sans-serif"}),
            className="bg-light"
        ),
        dbc.CardBody([
            html.H6("Movimentação Minério", className="text-secondary mt-2", style={"fontFamily": "Arial, sans-serif"}),
            dcc.Loading(
                dash_table.DataTable(
                    id="rel3-custo-minero",
                    columns=[],
                    data=[],
                    page_action="none",
                    style_table={"overflowX": "auto", "width": "100%", "margin": "auto"},
                    style_cell={
                        "textAlign": "center",
                        "padding": "5px",
                        "fontFamily": "Arial, sans-serif",
                        "fontSize": "10px",
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
            html.H6("Movimentação Estéril", className="text-secondary mt-2", style={"fontFamily": "Arial, sans-serif"}),
            dcc.Loading(
                dash_table.DataTable(
                    id="rel3-custo-esteril",
                    columns=[],
                    data=[],
                    page_action="none",
                    style_table={"overflowX": "auto", "width": "100%", "margin": "auto"},
                    style_cell={
                        "textAlign": "center",
                        "padding": "5px",
                        "fontFamily": "Arial, sans-serif",
                        "fontSize": "10px",
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
            )
        ])
    ], className="shadow mb-4 animate__animated animate__fadeInUp"),

    # (3) Custos Adicionais
    dbc.Card([
        dbc.CardHeader(
            html.H5("Custos Adicionais", className="mb-0", style={"fontFamily": "Arial, sans-serif"}),
            className="bg-light"
        ),
        dbc.CardBody(
            dcc.Loading(
                dash_table.DataTable(
                    id="rel3-custo-adicional",
                    columns=[],
                    data=[],
                    page_action="none",
                    style_table={"overflowX": "auto", "width": "100%", "margin": "auto"},
                    style_cell={
                        "textAlign": "center",
                        "padding": "5px",
                        "fontFamily": "Arial, sans-serif",
                        "fontSize": "10px",
                        "whiteSpace": "normal"
                    },
                    export_format="csv"
                ),
                type="default"
            )
        )
    ], className="shadow mb-4 animate__animated animate__fadeInUp"),

    # (5) Custo de Horas Paradas por Modelo (Preço 60%)
    dbc.Card([
        dbc.CardHeader(
            html.H5("Custo de Horas Paradas por Modelo (Preço 60%)", className="mb-0", style={"fontFamily": "Arial, sans-serif"}),
            className="bg-light"
        ),
        dbc.CardBody(
            dcc.Loading(
                dash_table.DataTable(
                    id="rel3-horas-paradas-table",
                    columns=[],
                    data=[],
                    page_action="none",
                    style_table={"overflowX": "auto", "width": "100%", "margin": "auto"},
                    style_cell={
                        "textAlign": "center",
                        "padding": "5px",
                        "fontFamily": "Arial, sans-serif",
                        "fontSize": "10px",
                        "whiteSpace": "normal"
                    },
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
    ], className="shadow mb-4 animate__animated animate__fadeInUp"),

    # (6) Faturamento Final
    dbc.Card([
        dbc.CardHeader(
            html.H5("Faturamento Final", className="mb-0", style={"fontFamily": "Arial, sans-serif"}),
            className="bg-light"
        ),
        dbc.CardBody(
            html.Div(id="rel3-total-geral", style={
                "fontSize": "20px",
                "fontWeight": "bold",
                "padding": "10px",
                "backgroundColor": "#fff9c4",
                "borderRadius": "5px",
                "fontFamily": "Arial, sans-serif"
            })
        )
    ], className="shadow mb-4 animate__animated animate__fadeInUp"),

    dbc.Card([
        dbc.CardBody(
            dbc.Button(
                "Exportar para Excel (1 Aba)",
                id="export-excel-button",
                color="success",
                className="w-100",
                style={"fontFamily": "Arial, sans-serif", "fontSize": "16px"}
            )
        )
    ], className="shadow mb-4 animate__animated animate__fadeInUp"),

    dcc.Download(id="download-excel")

], fluid=True)

# ===================== Callbacks =====================

@dash.callback(
    Output("rel3-data-store", "data"),
    Output("rel3-fato-hora-store", "data"),
    Input("rel3-apply-button", "n_clicks"),
    State("rel3-date-picker-range", "start_date"),
    State("rel3-date-picker-range", "end_date"),
    prevent_initial_call=True
)
def apply_filter_unified(n_clicks, start_date, end_date):
    if not start_date or not end_date:
        return {}, {}
    start_dt, end_dt = get_search_period(start_date, end_date)
    query_prod = (
        f"EXEC dw_sdp_mt_fas..usp_fato_producao "
        f"'{start_dt:%d/%m/%Y %H:%M:%S}', '{end_dt:%d/%m/%Y %H:%M:%S}'"
    )
    df_prod = execute_query(query_prod)
    if not df_prod.empty and "dt_registro_turno" in df_prod.columns:
        df_prod["dt_registro_turno"] = pd.to_datetime(df_prod["dt_registro_turno"], errors="coerce")
        df_prod.dropna(subset=["dt_registro_turno"], inplace=True)
        df_prod = df_prod[(df_prod["dt_registro_turno"] >= start_dt) & (df_prod["dt_registro_turno"] <= end_dt)]
        df_prod = df_prod[df_prod["cod_viagem"].notnull() & (df_prod["cod_viagem"] != "")]
        df_prod = df_prod[df_prod["nome_tipo_operacao_modelo"] == "Transporte"]
        df_prod["dmt_mov_cheio"] = df_prod["dmt_mov_cheio"].fillna(0)
        df_prod["dmt_tratado"] = df_prod["dmt_mov_cheio"]
        cond = (df_prod["dmt_mov_cheio"] <= 50) | (df_prod["dmt_mov_cheio"] > 7000)
        group_means = df_prod.groupby(["nome_origem", "nome_destino"])["dmt_mov_cheio"].transform("mean")
        group_counts = df_prod.groupby(["nome_origem", "nome_destino"])["dmt_mov_cheio"].transform("count")
        mask = cond & (group_counts > 1)
        df_prod.loc[mask, "dmt_tratado"] = group_means[mask].apply(lambda x: 7000 if x > 7000 else x)
        bins = [0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500, 7000]
        labels = [
            "0-500", "501-1000", "1001-1500", "1501-2000", "2001-2500",
            "2501-3000", "3001-3500", "3501-4000", "4001-4500", "4501-5000",
            "5001-5500", "5501-6000", "6001-6500", "6501-7000"
        ]
        cat_type = CategoricalDtype(categories=labels, ordered=True)
        df_prod["dmt_bin"] = pd.cut(
            df_prod["dmt_tratado"], bins=bins, labels=labels, include_lowest=True, right=True
        ).astype(cat_type)
    data_prod_json = df_prod.to_json(date_format="iso", orient="records") if not df_prod.empty else {}
    query_hora = (
        f"EXEC dw_sdp_mt_fas..usp_fato_hora "
        f"'{start_dt:%d/%m/%Y %H:%M:%S}', '{end_dt:%d/%m/%Y %H:%M:%S}'"
    )
    df_hora = execute_query(query_hora)
    if not df_hora.empty and "dt_registro_turno" in df_hora.columns:
        df_hora["dt_registro_turno"] = pd.to_datetime(df_hora["dt_registro_turno"], errors="coerce")
        df_hora.dropna(subset=["dt_registro_turno"], inplace=True)
        df_hora = df_hora[(df_hora["dt_registro_turno"] >= start_dt) & (df_hora["dt_registro_turno"] <= end_dt)]
        estados_filtro = ["Improdutiva Interna", "Improdutiva Externa", "Serviço Auxiliar"]
        df_hora = df_hora[df_hora["nome_tipo_estado"].isin(estados_filtro)]
    data_hora_json = df_hora.to_json(date_format="iso", orient="records") if not df_hora.empty else {}
    return data_prod_json, data_hora_json

@dash.callback(
    Output("operacao-dropdown", "options", allow_duplicate=True),
    Input("rel3-data-store", "data"),
    prevent_initial_call="initial_duplicate"
)
def update_operacoes_options(json_data):
    if not json_data or isinstance(json_data, dict):
        return []
    df = pd.read_json(json_data, orient="records")
    if df.empty:
        return []
    ops_unicas = sorted(df["nome_operacao"].dropna().unique())
    return [{"label": op, "value": op} for op in ops_unicas]

@dash.callback(
    Output("rel3-custo-minero", "data"),
    Output("rel3-custo-minero", "columns"),
    Input("rel3-data-store", "data")
)
def update_custo_minero(json_data):
    if not json_data or isinstance(json_data, dict):
        return [], []
    df = pd.read_json(json_data, orient="records")
    if df.empty:
        return [], []
    df_minero = calc_custo_por_faixa(df, "Movimentação Minério", CUSTO_MINERO_MAP)
    if df_minero.empty:
        return [], []
    total_vol = df_minero["total_volume"].sum()
    total_custo = df_minero["custo_total"].sum()
    df_total = pd.DataFrame([{
        "dmt_bin": "TOTAL",
        "total_volume": total_vol,
        "custo_unitario": "",
        "custo_total": total_custo
    }])
    df_minero = pd.concat([df_minero, df_total], ignore_index=True)
    columns = [
        {"name": "Faixa de DMT", "id": "dmt_bin"},
        {"name": "Volume Total (m³)", "id": "total_volume", "type": "numeric",
         "format": Format(precision=2, scheme=Scheme.fixed, group=True)},
        {"name": "Custo Unitário (R$/m³)", "id": "custo_unitario", "type": "numeric",
         "format": FormatTemplate.money(2)},
        {"name": "Custo Total (R$)", "id": "custo_total", "type": "numeric",
         "format": FormatTemplate.money(2)}
    ]
    data = df_minero.to_dict("records")
    return data, columns

@dash.callback(
    Output("rel3-custo-esteril", "data"),
    Output("rel3-custo-esteril", "columns"),
    Input("rel3-data-store", "data")
)
def update_custo_esteril(json_data):
    if not json_data or isinstance(json_data, dict):
        return [], []
    df = pd.read_json(json_data, orient="records")
    if df.empty:
        return [], []
    df_esteril = calc_custo_por_faixa(df, "Movimentação Estéril", CUSTO_ESTERIL_MAP)
    if df_esteril.empty:
        return [], []
    total_vol = df_esteril["total_volume"].sum()
    total_custo = df_esteril["custo_total"].sum()
    df_total = pd.DataFrame([{
        "dmt_bin": "TOTAL",
        "total_volume": total_vol,
        "custo_unitario": "",
        "custo_total": total_custo
    }])
    df_esteril = pd.concat([df_esteril, df_total], ignore_index=True)
    columns = [
        {"name": "Faixa de DMT", "id": "dmt_bin"},
        {"name": "Volume Total (m³)", "id": "total_volume", "type": "numeric",
         "format": Format(precision=2, scheme=Scheme.fixed, group=True)},
        {"name": "Custo Unitário (R$/m³)", "id": "custo_unitario", "type": "numeric",
         "format": FormatTemplate.money(2)},
        {"name": "Custo Total (R$)", "id": "custo_total", "type": "numeric",
         "format": FormatTemplate.money(2)}
    ]
    data = df_esteril.to_dict("records")
    return data, columns

@dash.callback(
    Output("rel3-custo-adicional", "data"),
    Output("rel3-custo-adicional", "columns"),
    Input("rel3-data-store", "data")
)
def update_custo_adicional_cb(json_data):
    if not json_data or isinstance(json_data, dict):
        return [], []
    df = pd.read_json(json_data, orient="records")
    if df.empty:
        return [], []
    df_adic = calc_custo_adicional(df)
    columns = [
        {"name": "Item", "id": "item"},
        {"name": "Volume Total (m³)", "id": "volume_total (m³)", "type": "numeric",
         "format": Format(precision=2, scheme=Scheme.fixed, group=True)},
        {"name": "Custo Unitário (R$/m³)", "id": "custo_unitario (R$/m³)", "type": "numeric",
         "format": FormatTemplate.money(2)},
        {"name": "Custo Total (R$)", "id": "custo_total (R$)", "type": "numeric",
         "format": FormatTemplate.money(2)}
    ]
    data = df_adic.to_dict("records")
    return data, columns

@dash.callback(
    Output("rel3-horas-paradas-table", "data"),
    Output("rel3-horas-paradas-table", "columns"),
    Input("rel3-fato-hora-store", "data")
)
def update_horas_paradas_table(json_data):
    if not json_data or isinstance(json_data, dict):
        return [], []
    df = pd.read_json(json_data, orient="records")
    if df.empty:
        return [], []
    df_parada = df[df["nome_estado"].isin(ESTADOS_PARADA)]
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
        {"name": "Horas Paradas (h)", "id": "horas_paradas", "type": "numeric",
         "format": Format(precision=2, scheme=Scheme.fixed, group=True)},
        {"name": "Preço 60% (R$/h)", "id": "preco_60", "type": "numeric",
         "format": FormatTemplate.money(2)},
        {"name": "Custo Total (R$)", "id": "custo_total", "type": "numeric",
         "format": FormatTemplate.money(2)}
    ]
    data = df_group.to_dict("records")
    return data, columns

@dash.callback(
    Output("rel3-total-geral", "children"),
    Input("rel3-data-store", "data"),
    Input("rel3-fato-hora-store", "data")
)
def update_faturamento_final(json_producao, json_hora):
    if not json_producao or isinstance(json_producao, dict):
        faturamento_transporte = 0.0
    else:
        df_prod = pd.read_json(json_producao, orient="records")
        faturamento_transporte = calc_faturamento_transporte(df_prod) if not df_prod.empty else 0.0
    if not json_hora or isinstance(json_hora, dict):
        faturamento_hora = 0.0
    else:
        df_hora = pd.read_json(json_hora, orient="records")
        faturamento_hora = calc_faturamento_hora_60(df_hora) if not df_hora.empty else 0.0
    faturamento_total = faturamento_transporte + faturamento_hora
    return html.Div([
        html.Div(f"Faturamento (Escavação e Transporte): R$ {faturamento_transporte:,.2f}",
                 style={"backgroundColor": "#fff9c4", "padding": "5px", "marginBottom": "5px", "fontFamily": "Arial, sans-serif"}),
        html.Div(f"Faturamento Hora 60%: R$ {faturamento_hora:,.2f}",
                 style={"backgroundColor": "#fff9c4", "padding": "5px", "marginBottom": "5px", "fontFamily": "Arial, sans-serif"}),
        html.Div(f"Faturamento Total: R$ {faturamento_total:,.2f}",
                 style={"backgroundColor": "#fff9c4", "padding": "5px", "marginBottom": "5px", "fontFamily": "Arial, sans-serif"})
    ])

@dash.callback(
    Output("download-excel", "data"),
    Input("export-excel-button", "n_clicks"),
    State("rel3-data-store", "data"),
    State("rel3-fato-hora-store", "data"),
    prevent_initial_call=True
)
def export_to_excel(n_clicks, json_producao, json_hora):
    if n_clicks:
        processed_data = build_export_excel_single_sheet(json_producao, json_hora)
        return dcc.send_bytes(lambda file: file.write(processed_data), "relatorio3.xlsx")
    return dash.no_update
