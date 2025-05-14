import logging
import time
from datetime import datetime, timedelta
from io import BytesIO
from typing import Tuple, Union, Any, Dict, List

import dash
from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc
import dash_table
import pandas as pd
from dash_table.Format import Format, Scheme
from dash_table import FormatTemplate
from pandas.api.types import CategoricalDtype
import numpy as np

# Import do método para consultar o banco
from db import query_to_df

# ===================== CONFIG DO LOG =====================
logging.basicConfig(
    level=logging.INFO,
    filename="relatorio3.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ===================== DATAS PADRÃO =====================
today: datetime.date = datetime.today().date()
start_default: datetime.date = today - timedelta(days=45)
end_default: datetime.date = today

# ===================== MAPAS DE CUSTO E PREÇO =====================
CUSTO_MINERO_MAP: Dict[str, float] = {
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
CUSTO_ESTERIL_MAP: Dict[str, float] = {
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

CUSTO_CARGA_MINERO: float = 4.90818672114214
CUSTO_CARGA_ESTERIL: float = 3.72386776463452
CUSTO_ESPALHAMENTO_ESTERIL: float = 1.58371634448642

PRECO_60_MAP: Dict[str, float] = {
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

ESTADOS_PARADA: List[str] = ["Falta de Frente", "Falta de Combustível", "Aguardando Geologia", "Detonação", "Poeira"]

PRECO_LOCACAO_MAP: Dict[str, float] = {
    "ESCAVADEIRA HIDRÁULICA SANY SY750H": 1025.90663891272,
    "ESCAVADEIRA HIDRÁULICA CAT 320": 471.362509770711,
    "ESCAVADEIRA HIDRÁULICA CAT 352": 726.452809176037,
    "ESCAVADEIRA HIDRÁULICA CAT 374DL": 1025.90663891272,
    "ESCAVADEIRA HIDRÁULICA VOLVO EC480DL": 1320.00,
    "ESCAVADEIRA HIDRÁULICA VOLVO EC750DL": 1025.90663891272,
    "MERCEDES BENZ AROCS 4851/45 8X4": 316.090153610947,
    "MERCEDES BENZ AXOR 3344 6X4 (PIPA)": 260.635740696746,
    "MOTONIVELADORA CAT 140K": 0.0,
    "PERFURATRIZ HIDRAULICA SANDVIK DP1500I": 1619.56831092441,
    "PERFURATRIZ HIDRAULICA SANDVIK DX800": 1270.01696456104,
    "PÁ CARREGADEIRA CAT 966L": 0.0,
    "RETRO ESCAVADEIRA CAT 416F2": 0.0,
    "TRATOR DE ESTEIRAS CAT D6T": 526.816922684912,
    "TRATOR DE ESTEIRAS CAT D7": 792.998104673078,
    "TRATOR DE ESTEIRAS CAT D8": 792.998104673078,
    "TRATOR DE ESTEIRAS KOMATSU D155": 792.998104673078,
    "VOLVO FMX 500 8X4": 316.090153610947
}
ESTADOS_LOCACAO: List[str] = [
    "Dobrando Bloco", "Limpeza de Detonação", "Limpeza para Perfuração", "Perfurando Repé",
    "Retaludando", "Tombando Material", "Perfuração Geologia", "Perfuração Pré-Corte",
    "Perfurando Extra", "Repasse"
]

# ===================== TABELAS ESTÁTICAS =====================
df_manut_canteiro: pd.DataFrame = pd.DataFrame([
    {
        "Item": "Manutenção do Canteiro de Serviços",
        "Unidade": 1,
        "Valor Unitário (R$)": 205181.327782545,
        "Valor Total (R$)": 205181.327782545
    },
    {
        "Item": "TOTAL",
        "Unidade": "",
        "Valor Unitário (R$)": "",
        "Valor Total (R$)": 205181.327782545
    }
])
manut_canteiro_columns: List[Dict[str, Any]] = [
    {"name": "Item", "id": "Item"},
    {"name": "Unidade", "id": "Unidade", "type": "numeric",
     "format": Format(precision=0, scheme=Scheme.fixed, group=True)},
    {"name": "Valor Unitário (R$)", "id": "Valor Unitário (R$)",
     "type": "numeric", "format": FormatTemplate.money(2)},
    {"name": "Valor Total (R$)", "id": "Valor Total (R$)",
     "type": "numeric", "format": FormatTemplate.money(2)}
]
manut_canteiro_data: List[Dict[str, Any]] = df_manut_canteiro.to_dict("records")

df_servicos_eventuais: pd.DataFrame = pd.DataFrame([
    {
        "Equipamento": "ESCAVADEIRA HIDRÁULICA CAT 320 (ROMPEDOR)",
        "Horas Mínimas Garantidas": 500,
        "Preço Unitário (R$/h)": 621.089424639054,
        "Valor Total (R$)": 500 * 621.089424639054
    },
    {
        "Equipamento": "VOLVO FMX 500 8X4",
        "Horas Mínimas Garantidas": 2500,
        "Preço Unitário (R$/h)": 316.090153610947,
        "Valor Total (R$)": 2500 * 316.090153610947
    },
    {
        "Equipamento": "MERCEDES BENZ AXOR 3344 6X4 (PIPA)",
        "Horas Mínimas Garantidas": 500,
        "Preço Unitário (R$/h)": 260.635740696746,
        "Valor Total (R$)": 500 * 260.635740696746
    },
    {
        "Equipamento": "PÁ CARREGADEIRA CAT 966L",
        "Horas Mínimas Garantidas": 3500,
        "Preço Unitário (R$/h)": 460.271627187871,
        "Valor Total (R$)": 3500 * 460.271627187871
    },
    {
        "Equipamento": "TOTAL",
        "Horas Mínimas Garantidas": 7000,
        "Preço Unitário (R$/h)": "",
        "Valor Total (R$)": (
            500 * 621.089424639054
            + 2500 * 316.090153610947
            + 500 * 260.635740696746
            + 3500 * 460.271627187871
        )
    }
])
servicos_eventuais_columns: List[Dict[str, Any]] = [
    {"name": "Equipamento", "id": "Equipamento"},
    {"name": "Horas Mínimas Garantidas", "id": "Horas Mínimas Garantidas",
     "type": "numeric", "format": Format(precision=0, scheme=Scheme.fixed, group=True)},
    {"name": "Preço Unitário (R$/h)", "id": "Preço Unitário (R$/h)",
     "type": "numeric", "format": FormatTemplate.money(2)},
    {"name": "Valor Total (R$)", "id": "Valor Total (R$)",
     "type": "numeric", "format": FormatTemplate.money(2)}
]
servicos_eventuais_data: List[Dict[str, Any]] = df_servicos_eventuais.to_dict("records")

# ===================== FUNÇÕES AUXILIARES (consultas e cálculos) =====================

def get_search_period(start_date: str, end_date: str) -> Tuple[datetime, datetime]:
    """
    Converte as strings start_date e end_date para objetos datetime.
    """
    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date)
    return start_dt, end_dt

# Importa o objeto cache inicializado no app.py
from app import cache

@cache.memoize(timeout=300)
def cached_query(query: str) -> pd.DataFrame:
    """
    Executa a query utilizando o cache. Em caso de erro, registra no log e retorna um DataFrame vazio.
    """
    try:
        return query_to_df(query)
    except Exception as e:
        logging.error(f"Erro na execução da query: {e}")
        return pd.DataFrame()

def execute_query(query: str) -> pd.DataFrame:
    """
    Executa a query sem cache, registrando erros.
    """
    try:
        return query_to_df(query)
    except Exception as e:
        logging.error(f"Erro na execução da query: {e}")
        return pd.DataFrame()

@cache.memoize(timeout=60)
def parse_json_to_df(json_data: Union[str, dict]) -> pd.DataFrame:
    """
    Converte dados em JSON para DataFrame.
    """
    return pd.read_json(json_data, orient="records")

# -----------------------------------------------------------------
# Decorador para Profiling
# -----------------------------------------------------------------
def profile_time(func):
    """
    Decorador simples para medir o tempo de execução da função.
    Registra o tempo decorrido via logging.
    """
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = func(*args, **kwargs)
        t1 = time.perf_counter()
        logging.info(f"[Profile] {func.__name__} executada em {t1-t0:.4f} segundos")
        return result
    return wrapper

@profile_time
def calc_custo_por_faixa(df: pd.DataFrame, nome_operacao: str, custo_map: Dict[str, float]) -> pd.DataFrame:
    """
    Calcula o custo por faixa de DMT para uma operação específica usando um mapa de custos.
    """
    df_filtro = df.loc[df["nome_operacao"] == nome_operacao]
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

@profile_time
def calc_custo_adicional(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula os custos adicionais para movimentação de minério e estéril.
    """
    df_minero = df.loc[df["nome_operacao"] == "Movimentação Minério"].drop_duplicates(subset=["cod_viagem"])
    df_esteril = df.loc[df["nome_operacao"] == "Movimentação Estéril"].drop_duplicates(subset=["cod_viagem"])
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

@profile_time
def calc_faturamento_transporte(df: pd.DataFrame) -> float:
    """
    Calcula o faturamento total de transporte combinando custos de minério, estéril e adicionais.
    """
    df_minero = calc_custo_por_faixa(df, "Movimentação Minério", CUSTO_MINERO_MAP)
    total_minero = df_minero["custo_total"].sum() if not df_minero.empty else 0
    df_esteril = calc_custo_por_faixa(df, "Movimentação Estéril", CUSTO_ESTERIL_MAP)
    total_esteril = df_esteril["custo_total"].sum() if not df_esteril.empty else 0
    df_adic = calc_custo_adicional(df)
    total_adic = df_adic["custo_total (R$)"].sum()
    return total_minero + total_esteril + total_adic

@profile_time
def calc_faturamento_hora_60(df_hora: pd.DataFrame) -> float:
    """
    Calcula o faturamento com base nas horas paradas, utilizando preço 60%.
    """
    df_parada = df_hora.loc[df_hora["nome_estado"].isin(ESTADOS_PARADA)]
    if df_parada.empty or "nome_modelo" not in df_parada.columns:
        return 0.0
    df_group = df_parada.groupby("nome_modelo", as_index=False).agg(horas_paradas=("tempo_hora", "sum"))
    df_group["preco_60"] = df_group["nome_modelo"].map(PRECO_60_MAP).fillna(0)
    df_group["custo_total"] = df_group["horas_paradas"] * df_group["preco_60"]
    return df_group["custo_total"].sum()

@profile_time
def calc_horas_locacao(df_hora: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula as horas de locação e os custos associados por modelo.
    """
    if df_hora.empty:
        return pd.DataFrame()
    df_subset = df_hora.loc[df_hora["nome_estado"].isin(ESTADOS_LOCACAO)]
    if df_subset.empty or "nome_modelo" not in df_subset.columns:
        return pd.DataFrame()
    df_group = df_subset.groupby("nome_modelo", as_index=False).agg(horas_locacao=("tempo_hora", "sum"))
    df_group["preco_locacao"] = df_group["nome_modelo"].map(PRECO_LOCACAO_MAP).fillna(0)
    df_group["custo_total"] = df_group["horas_locacao"] * df_group["preco_locacao"]
    total_horas = df_group["horas_locacao"].sum()
    total_custo = df_group["custo_total"].sum()
    df_total = pd.DataFrame([{
        "nome_modelo": "TOTAL",
        "horas_locacao": total_horas,
        "preco_locacao": "",
        "custo_total": total_custo
    }])
    return pd.concat([df_group, df_total], ignore_index=True)

def build_export_excel_single_sheet(json_producao: Union[str, dict],
                                    json_hora: Union[str, dict]) -> bytes:
    """
    Prepara um arquivo Excel com todos os dados de medição para exportação.
    Utiliza o context manager para garantir o fechamento correto do arquivo.
    """
    df_prod: pd.DataFrame = pd.read_json(json_producao, orient="records") if json_producao and not isinstance(json_producao, dict) else pd.DataFrame()
    df_hora: pd.DataFrame = pd.read_json(json_hora, orient="records") if json_hora and not isinstance(json_hora, dict) else pd.DataFrame()

    df_manut_excel: pd.DataFrame = df_manut_canteiro.copy()
    df_serv_event_excel: pd.DataFrame = df_servicos_eventuais.copy()

    if not df_prod.empty:
        df_minero = calc_custo_por_faixa(df_prod, "Movimentação Minério", CUSTO_MINERO_MAP)
        if not df_minero.empty:
            vol_min = df_minero["total_volume"].sum()
            cust_min = df_minero["custo_total"].sum()
            df_minero.loc[len(df_minero)] = {"dmt_bin": "TOTAL", "total_volume": vol_min, "custo_unitario": "", "custo_total": cust_min}
        else:
            df_minero = pd.DataFrame()
        df_esteril = calc_custo_por_faixa(df_prod, "Movimentação Estéril", CUSTO_ESTERIL_MAP)
        if not df_esteril.empty:
            vol_est = df_esteril["total_volume"].sum()
            cust_est = df_esteril["custo_total"].sum()
            df_esteril.loc[len(df_esteril)] = {"dmt_bin": "TOTAL", "total_volume": vol_est, "custo_unitario": "", "custo_total": cust_est}
        else:
            df_esteril = pd.DataFrame()
    else:
        df_minero = pd.DataFrame()
        df_esteril = pd.DataFrame()

    if not df_prod.empty:
        df_adic = calc_custo_adicional(df_prod)
    else:
        df_adic = pd.DataFrame()

    df_locacao = calc_horas_locacao(df_hora)

    if not df_hora.empty:
        df_parada = df_hora.loc[df_hora["nome_estado"].isin(ESTADOS_PARADA)]
        if not df_parada.empty and "nome_modelo" in df_parada.columns:
            df_group = df_parada.groupby("nome_modelo", as_index=False).agg(horas_paradas=("tempo_hora", "sum"))
            df_group["preco_60"] = df_group["nome_modelo"].map(PRECO_60_MAP).fillna(0)
            df_group["custo_total"] = df_group["horas_paradas"] * df_group["preco_60"]
            total_h = df_group["horas_paradas"].sum()
            total_c = df_group["custo_total"].sum()
            df_group.loc[len(df_group)] = {"nome_modelo": "TOTAL", "horas_paradas": total_h, "preco_60": "", "custo_total": total_c}
            df_horas = df_group
        else:
            df_horas = pd.DataFrame()
    else:
        df_horas = pd.DataFrame()

    fat_trans: float = calc_faturamento_transporte(df_prod) if not df_prod.empty else 0.0
    fat_hora: float = calc_faturamento_hora_60(df_hora) if not df_hora.empty else 0.0

    manut_total = df_manut_excel.loc[df_manut_excel["Item"] == "TOTAL", "Valor Total (R$)"].values[0]
    serv_event_total = df_servicos_eventuais.loc[df_servicos_eventuais["Equipamento"] == "TOTAL", "Valor Total (R$)"].values[0]
    fat_total: float = fat_trans + fat_hora + manut_total + serv_event_total

    df_faturamento = pd.DataFrame({
        "Descrição": [
            "Faturamento (Escavação e Transporte)",
            "Faturamento Hora 60%",
            "Manutenção do Canteiro de Serviços",
            "Serviços Eventuais",
            "Faturamento Total"
        ],
        "Valor": [
            fat_trans,
            fat_hora,
            manut_total,
            serv_event_total,
            fat_total
        ]
    })

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        workbook = writer.book
        worksheet = workbook.add_worksheet("Dados")
        writer.sheets["Dados"] = worksheet

        bold_fmt = workbook.add_format({"bold": True})
        money_fmt = workbook.add_format({"num_format": "#,##0.00"})
        numeric_fmt = workbook.add_format({"num_format": "#,##0.00"})

        row_cursor = 0

        def write_table(title: str, df_table: pd.DataFrame, total_col: Union[str, None] = None) -> None:
            nonlocal row_cursor
            worksheet.write(row_cursor, 0, title, bold_fmt)
            row_cursor += 1

            if df_table.empty:
                worksheet.write(row_cursor, 0, "Sem dados")
                row_cursor += 2
                return

            df_table.to_excel(writer, sheet_name="Dados", startrow=row_cursor, startcol=0, index=False)
            n_rows, n_cols = df_table.shape
            for c_idx, c_name in enumerate(df_table.columns):
                for r_i in range(n_rows):
                    excel_row = row_cursor + 1 + r_i
                    val = df_table.iloc[r_i, c_idx]
                    if total_col and str(df_table.iloc[r_i][total_col]).upper() == "TOTAL":
                        worksheet.write(excel_row, c_idx, val, bold_fmt)
                    else:
                        if isinstance(val, (int, float)):
                            if any(x in c_name.lower() for x in ["custo", "valor", "preço"]):
                                worksheet.write_number(excel_row, c_idx, val, money_fmt)
                            else:
                                worksheet.write_number(excel_row, c_idx, val, numeric_fmt)
            row_cursor += n_rows + 2

        write_table("Manutenção do Canteiro de Serviços", df_manut_excel, total_col="Item")
        write_table("Serviços Eventuais", df_serv_event_excel, total_col="Equipamento")
        write_table("Custos de Movimentação - Minério", df_minero, total_col="dmt_bin")
        write_table("Custos de Movimentação - Estéril", df_esteril, total_col="dmt_bin")
        write_table("Custos Adicionais", df_adic, total_col=None)
        write_table("Horas de Locação por Modelo", df_locacao, total_col="nome_modelo")
        write_table("Custo de Horas Paradas por Modelo (Preço 60%)", df_horas, total_col="nome_modelo")
        write_table("Faturamento Final", df_faturamento, total_col="Descrição")

    return output.getvalue()

# ===================== LAYOUT =====================
common_table_style: Dict[str, Any] = {
    "style_table": {
        "overflowX": "auto",
        "width": "100%",
        "margin": "auto",
        "borderRadius": "8px"
    },
    "style_cell": {
        "textAlign": "center",
        "padding": "8px",
        "fontFamily": "Arial, sans-serif",
        "fontSize": "0.9rem",
        "whiteSpace": "normal",
        "border": "1px solid #e9ecef"
    },
    "style_header": {
        "background": "linear-gradient(90deg, #343a40, #495057)",
        "fontWeight": "bold",
        "textAlign": "center",
        "color": "white",
        "fontFamily": "Arial, sans-serif",
        "fontSize": "0.9rem",
        "border": "1px solid #e9ecef"
    }
}

# Navbar personalizada com botão de retorno e horário local
navbar = dbc.Navbar(
    dbc.Container([
        # Título com ícone estilizado
        dbc.NavbarBrand([
            html.I(className="fas fa-calculator mr-2"),  # Ícone representando boletim de medição
            "Boletim de Medição"
        ], href="/relatorio3", className="ms-2 d-flex align-items-center", style={"fontSize": "1.1rem"}),
        # Botão de retorno à página inicial
        dcc.Link([
            html.I(className="fas fa-home mr-1"),  # Ícone de retorno
            "Voltar"
        ], href="/", className="btn btn-sm", style={
            "borderRadius": "10px",
            "background": "linear-gradient(45deg, #007bff, #00aaff)",
            "color": "#fff",
            "padding": "6px 12px",
            "transition": "all 0.3s"
        }),
        # Horário local em badge
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
        "background": "linear-gradient(90deg, #343a40, #495057)",  # Gradiente suave
        "borderBottom": "1px solid rgba(255,255,255,0.1)",
        "padding": "0.5rem 0",
        "fontSize": "0.9rem"
    }
)

layout = dbc.Container([
    navbar,
    dbc.Row(
        dbc.Col(
            html.H3(
                "Boletim de Medição",
                className="text-center mt-4 mb-4",
                style={
                    "fontFamily": "Arial, sans-serif",
                    "fontSize": "1.6rem",
                    "fontWeight": "500"
                }
            ),
            width=12
        ),
        className="mb-3"
    ),
    dbc.Row([
        dbc.Col([
            html.Label(
                "Selecione o Período:",
                className="fw-bold text-secondary",
                style={"fontFamily": "Arial, sans-serif", "fontSize": "0.9rem"}
            ),
            dcc.DatePickerRange(
                id="rel3-date-picker-range",
                min_date_allowed=datetime(2020, 1, 1).date(),
                max_date_allowed=today,
                start_date=start_default,
                end_date=end_default,
                display_format="DD/MM/YYYY",
                className="mb-2",
                style={
                    "fontSize": "0.9rem",
                    "borderRadius": "8px",
                    "backgroundColor": "#f8f9fa",
                    "width": "100%"
                }
            ),
            dbc.Button(
                [
                    html.I(className="fas fa-filter mr-1"),  # Ícone de filtro
                    "Aplicar Filtro"
                ],
                id="rel3-apply-button",
                n_clicks=0,
                className="w-100",
                style={
                    "fontSize": "0.9rem",
                    "borderRadius": "10px",
                    "background": "linear-gradient(45deg, #007bff, #00aaff)",
                    "color": "#fff",
                    "transition": "all 0.3s",
                    "padding": "6px 12px"
                }
            )
        ], xs=12, md=4)
    ], className="mb-3 align-items-end"),
    dcc.Store(id="rel3-data-store"),
    dcc.Store(id="rel3-fato-hora-store"),
    dcc.Download(id="download-excel"),
    html.Hr(),
    dbc.Card([
        dbc.CardHeader(
            html.H5("Manutenção do Canteiro de Serviços", className="mb-0 text-white", style={
                "fontSize": "1.1rem",
                "fontWeight": "500",
                "fontFamily": "Arial, sans-serif"
            }),
            style={"background": "linear-gradient(90deg, #343a40, #495057)"}
        ),
        dbc.CardBody(
            dash_table.DataTable(
                id="rel3-manut-canteiro",
                columns=manut_canteiro_columns,
                data=manut_canteiro_data,
                page_action="none",
                style_data_conditional=[{"if": {"filter_query": '{Item} = "TOTAL"'}, "backgroundColor": "#fff9c4", "fontWeight": "bold"}],
                **common_table_style
            ),
            style={"padding": "0.8rem"}
        )
    ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none"}),
    dbc.Card([
        dbc.CardHeader(
            html.H5("Serviços Eventuais", className="mb-0 text-white", style={
                "fontSize": "1.1rem",
                "fontWeight": "500",
                "fontFamily": "Arial, sans-serif"
            }),
            style={"background": "linear-gradient(90deg, #343a40, #495057)"}
        ),
        dbc.CardBody(
            dash_table.DataTable(
                id="rel3-servicos-eventuais",
                columns=servicos_eventuais_columns,
                data=servicos_eventuais_data,
                page_action="none",
                style_data_conditional=[{"if": {"filter_query": '{Equipamento} = "TOTAL"'}, "backgroundColor": "#fff9c4", "fontWeight": "bold"}],
                **common_table_style
            ),
            style={"padding": "0.8rem"}
        )
    ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none"}),
    dbc.Card([
        dbc.CardHeader(
            html.H5("Custos de Movimentação", className="mb-0 text-white", style={
                "fontSize": "1.1rem",
                "fontWeight": "500",
                "fontFamily": "Arial, sans-serif"
            }),
            style={"background": "linear-gradient(90deg, #343a40, #495057)"}
        ),
        dbc.CardBody([
            html.H6("Movimentação Minério", className="mt-2", style={"fontSize": "1rem"}),
            dcc.Loading(
                dash_table.DataTable(
                    id="rel3-custo-minero",
                    columns=[],
                    data=[],
                    page_action="none",
                    style_data_conditional=[{"if": {"filter_query": '{dmt_bin} = "TOTAL"'}, "backgroundColor": "#fff9c4", "fontWeight": "bold"}],
                    **common_table_style
                )
            ),
            html.Hr(),
            html.H6("Movimentação Estéril", style={"fontSize": "1rem"}),
            dcc.Loading(
                dash_table.DataTable(
                    id="rel3-custo-esteril",
                    columns=[],
                    data=[],
                    page_action="none",
                    style_data_conditional=[{"if": {"filter_query": '{dmt_bin} = "TOTAL"'}, "backgroundColor": "#fff9c4", "fontWeight": "bold"}],
                    **common_table_style
                )
            )
        ], style={"padding": "0.8rem"})
    ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none"}),
    dbc.Card([
        dbc.CardHeader(
            html.H5("Custos Adicionais", className="mb-0 text-white", style={
                "fontSize": "1.1rem",
                "fontWeight": "500",
                "fontFamily": "Arial, sans-serif"
            }),
            style={"background": "linear-gradient(90deg, #343a40, #495057)"}
        ),
        dbc.CardBody(
            dcc.Loading(
                dash_table.DataTable(
                    id="rel3-custo-adicional",
                    columns=[],
                    data=[],
                    page_action="none",
                    **common_table_style
                )
            ),
            style={"padding": "0.8rem"}
        )
    ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none"}),
    dbc.Card([
        dbc.CardHeader(
            html.H5("Horas de Locação por Modelo", className="mb-0 text-white", style={
                "fontSize": "1.1rem",
                "fontWeight": "500",
                "fontFamily": "Arial, sans-serif"
            }),
            style={"background": "linear-gradient(90deg, #343a40, #495057)"}
        ),
        dbc.CardBody(
            dcc.Loading(
                dash_table.DataTable(
                    id="horas-locacao-table",
                    columns=[],
                    data=[],
                    page_action="none",
                    style_data_conditional=[{"if": {"filter_query": '{nome_modelo} = "TOTAL"'}, "backgroundColor": "#fff9c4", "fontWeight": "bold"}],
                    **common_table_style
                )
            ),
            style={"padding": "0.8rem"}
        )
    ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none"}),
    dbc.Card([
        dbc.CardHeader(
            html.H5("Custo de Horas Paradas por Modelo (Preço 60%)", className="mb-0 text-white", style={
                "fontSize": "1.1rem",
                "fontWeight": "500",
                "fontFamily": "Arial, sans-serif"
            }),
            style={"background": "linear-gradient(90deg, #343a40, #495057)"}
        ),
        dbc.CardBody(
            dcc.Loading(
                dash_table.DataTable(
                    id="rel3-horas-paradas-table",
                    columns=[],
                    data=[],
                    page_action="none",
                    style_data_conditional=[{"if": {"filter_query": '{nome_modelo} = "TOTAL"'}, "backgroundColor": "#fff9c4", "fontWeight": "bold"}],
                    **common_table_style
                )
            ),
            style={"padding": "0.8rem"}
        )
    ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none"}),
    dbc.Card([
        dbc.CardHeader(
            html.H5("Faturamento Final", className="mb-0", style={
                "fontSize": "1.1rem",
                "fontWeight": "500",
                "fontFamily": "Arial, sans-serif"
            }),
            style={"background": "linear-gradient(90deg, #f8f9fa, #e9ecef)"}
        ),
        dbc.CardBody(
            dcc.Loading(
                dash_table.DataTable(
                    id="rel3-total-geral",
                    columns=[
                        {"name": "Descrição", "id": "Descrição"},
                        {"name": "Valor (R$)", "id": "Valor", "type": "numeric", "format": FormatTemplate.money(2)}
                    ],
                    data=[],
                    page_action="none",
                    style_data_conditional=[{"if": {"filter_query": '{Descrição} = "Faturamento Total"'}, "backgroundColor": "#fff9c4", "fontWeight": "bold"}],
                    **common_table_style
                )
            ),
            style={"padding": "0.8rem"}
        )
    ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none"}),
    dbc.Card([
        dbc.CardBody(
            dbc.Button(
                [
                    html.I(className="fas fa-file-excel mr-1"),  # Ícone de exportação
                    "Exportar para Excel (1 Aba)"
                ],
                id="export-excel-button",
                className="w-100",
                style={
                    "fontSize": "0.9rem",
                    "borderRadius": "10px",
                    "background": "linear-gradient(45deg, #28a745, #34c759)",
                    "color": "#fff",
                    "transition": "all 0.3s",
                    "padding": "6px 12px"
                }
            )
        )
    ], className="shadow-md mb-3 animate__animated animate__zoomIn", style={"borderRadius": "12px", "border": "none"})
], fluid=True)

# ===================== CALLBACKS =====================

@dash.callback(
    Output("rel3-data-store", "data"),
    Output("rel3-fato-hora-store", "data"),
    Input("rel3-apply-button", "n_clicks"),
    State("rel3-date-picker-range", "start_date"),
    State("rel3-date-picker-range", "end_date"),
    prevent_initial_call=True
)
def apply_filter_unified(n_clicks: int, start_date: str, end_date: str) -> Tuple[Any, Any]:
    if not start_date or not end_date:
        return {}, {}

    start_dt, end_dt = get_search_period(start_date, end_date)

    query_prod = (
        f"EXEC dw_sdp_mt_fas..usp_fato_producao "
        f"'{start_dt:%d/%m/%Y %H:%M:%S}', '{end_dt:%d/%m/%Y %H:%M:%S}'"
    )
    df_prod: pd.DataFrame = cached_query(query_prod)
    if not df_prod.empty and "dt_registro_turno" in df_prod.columns:
        df_prod["dt_registro_turno"] = pd.to_datetime(df_prod["dt_registro_turno"], errors="coerce")
        df_prod.dropna(subset=["dt_registro_turno"], inplace=True)
        df_prod = df_prod.loc[(df_prod["dt_registro_turno"] >= start_dt) & (df_prod["dt_registro_turno"] <= end_dt)]
        df_prod = df_prod.loc[df_prod["cod_viagem"].notnull() & (df_prod["cod_viagem"] != "")]
        df_prod = df_prod.loc[df_prod["nome_tipo_operacao_modelo"] == "Transporte"]

        df_prod["dmt_mov_cheio"] = df_prod["dmt_mov_cheio"].fillna(0)
        df_prod["dmt_tratado"] = df_prod["dmt_mov_cheio"]

        cond = (df_prod["dmt_mov_cheio"] <= 50) | (df_prod["dmt_mov_cheio"] > 7000)
        group_means = df_prod.groupby(["nome_origem", "nome_destino"])["dmt_mov_cheio"].transform("mean")
        group_counts = df_prod.groupby(["nome_origem", "nome_destino"])["dmt_mov_cheio"].transform("count")
        mask = cond & (group_counts > 1)
        df_prod.loc[mask, "dmt_tratado"] = np.where(group_means[mask] > 7000, 7000, group_means[mask])

        bins = [0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500, 7000]
        labels = [
            "0-500", "501-1000", "1001-1500", "1501-2000",
            "2001-2500", "2501-3000", "3001-3500", "3501-4000",
            "4001-4500", "4501-5000", "5001-5500", "5501-6000",
            "6001-6500", "6501-7000"
        ]
        cat_type = CategoricalDtype(categories=labels, ordered=True)
        df_prod["dmt_bin"] = pd.cut(df_prod["dmt_tratado"], bins=bins, labels=labels, include_lowest=True, right=True).astype(cat_type)

    data_prod_json: Union[str, dict] = df_prod.to_json(orient="records") if not df_prod.empty else {}

    query_hora = (
        f"EXEC dw_sdp_mt_fas..usp_fato_hora "
        f"'{start_dt:%d/%m/%Y %H:%M:%S}', '{end_dt:%d/%m/%Y %H:%M:%S}'"
    )
    df_hora: pd.DataFrame = cached_query(query_hora)
    if not df_hora.empty and "dt_registro_turno" in df_hora.columns:
        df_hora["dt_registro_turno"] = pd.to_datetime(df_hora["dt_registro_turno"], errors="coerce")
        df_hora.dropna(subset=["dt_registro_turno"], inplace=True)
        df_hora = df_hora.loc[(df_hora["dt_registro_turno"] >= start_dt) & (df_hora["dt_registro_turno"] <= end_dt)]
        estados_filtro = ["Improdutiva Interna", "Improdutiva Externa", "Serviço Auxiliar"]
        df_hora = df_hora.loc[df_hora["nome_tipo_estado"].isin(estados_filtro)]
    data_hora_json: Union[str, dict] = df_hora.to_json(orient="records") if not df_hora.empty else {}

    return data_prod_json, data_hora_json

@dash.callback(
    Output("rel3-custo-minero", "data"),
    Output("rel3-custo-minero", "columns"),
    Input("rel3-data-store", "data")
)
def update_custo_minero_cb(json_data: Union[str, dict]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not json_data or isinstance(json_data, dict):
        return [], []
    df: pd.DataFrame = parse_json_to_df(json_data)
    if df.empty:
        return [], []

    df_minero: pd.DataFrame = calc_custo_por_faixa(df, "Movimentação Minério", CUSTO_MINERO_MAP)
    if df_minero.empty:
        return [], []

    total_vol = df_minero["total_volume"].sum()
    total_custo = df_minero["custo_total"].sum()
    df_total = pd.DataFrame([{"dmt_bin": "TOTAL", "total_volume": total_vol, "custo_unitario": "", "custo_total": total_custo}])
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
def update_custo_esteril_cb(json_data: Union[str, dict]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not json_data or isinstance(json_data, dict):
        return [], []
    df: pd.DataFrame = parse_json_to_df(json_data)
    if df.empty:
        return [], []

    df_esteril: pd.DataFrame = calc_custo_por_faixa(df, "Movimentação Estéril", CUSTO_ESTERIL_MAP)
    if df_esteril.empty:
        return [], []

    total_vol = df_esteril["total_volume"].sum()
    total_custo = df_esteril["custo_total"].sum()
    df_total = pd.DataFrame([{"dmt_bin": "TOTAL", "total_volume": total_vol, "custo_unitario": "", "custo_total": total_custo}])
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
def update_custo_adicional_cb(json_data: Union[str, dict]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not json_data or isinstance(json_data, dict):
        return [], []
    df: pd.DataFrame = parse_json_to_df(json_data)
    if df.empty:
        return [], []

    df_adic: pd.DataFrame = calc_custo_adicional(df)
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
    Output("horas-locacao-table", "data"),
    Output("horas-locacao-table", "columns"),
    Input("rel3-fato-hora-store", "data")
)
def update_horas_locacao_table_cb(json_data: Union[str, dict]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not json_data or isinstance(json_data, dict):
        return [], []
    df: pd.DataFrame = pd.read_json(json_data, orient="records")
    if df.empty:
        return [], []

    df_subset = df.loc[df["nome_estado"].isin(ESTADOS_LOCACAO)]
    if df_subset.empty or "nome_modelo" not in df_subset.columns:
        return [], []

    df_group = df_subset.groupby("nome_modelo", as_index=False).agg(horas_locacao=("tempo_hora", "sum"))
    df_group["preco_locacao"] = df_group["nome_modelo"].map(PRECO_LOCACAO_MAP).fillna(0)
    df_group["custo_total"] = df_group["horas_locacao"] * df_group["preco_locacao"]

    total_horas = df_group["horas_locacao"].sum()
    total_custo = df_group["custo_total"].sum()
    df_total = pd.DataFrame([{"nome_modelo": "TOTAL", "horas_locacao": total_horas, "preco_locacao": "", "custo_total": total_custo}])
    df_final = pd.concat([df_group, df_total], ignore_index=True)

    columns = [
        {"name": "Modelo", "id": "nome_modelo"},
        {"name": "Horas Locação (h)", "id": "horas_locacao", "type": "numeric",
         "format": Format(precision=2, scheme=Scheme.fixed, group=True)},
        {"name": "Preço Locação (R$/h)", "id": "preco_locacao", "type": "numeric",
         "format": FormatTemplate.money(2)},
        {"name": "Custo Total (R$)", "id": "custo_total", "type": "numeric",
         "format": FormatTemplate.money(2)}
    ]
    data = df_final.to_dict("records")
    return data, columns

@dash.callback(
    Output("rel3-horas-paradas-table", "data"),
    Output("rel3-horas-paradas-table", "columns"),
    Input("rel3-fato-hora-store", "data")
)
def update_horas_paradas_table_cb(json_data: Union[str, dict]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not json_data or isinstance(json_data, dict):
        return [], []
    df: pd.DataFrame = pd.read_json(json_data, orient="records")
    if df.empty:
        return [], []

    df_parada = df.loc[df["nome_estado"].isin(ESTADOS_PARADA)]
    if df_parada.empty or "nome_modelo" not in df_parada.columns:
        return [], []
    df_group = df_parada.groupby("nome_modelo", as_index=False).agg(horas_paradas=("tempo_hora", "sum"))
    df_group["preco_60"] = df_group["nome_modelo"].map(PRECO_60_MAP).fillna(0)
    df_group["custo_total"] = df_group["horas_paradas"] * df_group["preco_60"]

    total_horas = df_group["horas_paradas"].sum()
    total_custo = df_group["custo_total"].sum()
    df_total = pd.DataFrame([{"nome_modelo": "TOTAL", "horas_paradas": total_horas, "preco_60": "", "custo_total": total_custo}])
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
    Output("rel3-total-geral", "data"),
    Input("rel3-data-store", "data"),
    Input("rel3-fato-hora-store", "data")
)
def update_faturamento_final_cb(json_producao: Union[str, dict], json_hora: Union[str, dict]) -> List[Dict]:
    if not json_producao or isinstance(json_producao, dict):
        fat_transporte: float = 0.0
    else:
        df_prod: pd.DataFrame = pd.read_json(json_producao, orient="records")
        fat_transporte = calc_faturamento_transporte(df_prod) if not df_prod.empty else 0.0

    if not json_hora or isinstance(json_hora, dict):
        fat_horas: float = 0.0
    else:
        df_hora: pd.DataFrame = pd.read_json(json_hora, orient="records")
        fat_horas = calc_faturamento_hora_60(df_hora) if not df_hora.empty else 0.0

    manut_total = df_manut_canteiro.loc[df_manut_canteiro["Item"] == "TOTAL", "Valor Total (R$)"].values[0]
    serv_event_total = df_servicos_eventuais.loc[df_servicos_eventuais["Equipamento"] == "TOTAL", "Valor Total (R$)"].values[0]
    fat_total = fat_transporte + fat_horas + manut_total + serv_event_total

    df_faturamento = pd.DataFrame({
        "Descrição": [
            "Faturamento (Escavação e Transporte)",
            "Faturamento Hora 60%",
            "Manutenção do Canteiro de Serviços",
            "Serviços Eventuais",
            "Faturamento Total"
        ],
        "Valor": [
            fat_transporte,
            fat_horas,
            manut_total,
            serv_event_total,
            fat_total
        ]
    })
    return df_faturamento.to_dict("records")

@dash.callback(
    Output("download-excel", "data"),
    Input("export-excel-button", "n_clicks"),
    State("rel3-data-store", "data"),
    State("rel3-fato-hora-store", "data"),
    prevent_initial_call=True
)
def export_to_excel_cb(n_clicks: int, json_producao: Union[str, dict], json_hora: Union[str, dict]) -> Any:
    if n_clicks:
        excel_bytes = build_export_excel_single_sheet(json_producao, json_hora)
        return dcc.send_bytes(lambda f: f.write(excel_bytes), "relatorio3.xlsx")
    return dash.no_update
