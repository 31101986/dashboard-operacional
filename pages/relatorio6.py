from datetime import datetime, timedelta  
import logging
import pandas as pd
from dash import dcc, html, Input, Output, callback
import dash_bootstrap_components as dbc

from db import query_to_df

# Import do objeto cache inicializado no app.py (para performance, se aplicável)
from app import cache

# Configuração do log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define o período para consulta: últimos 7 dias
DAY_END = datetime.now()
DAY_START = DAY_END - timedelta(days=7)

# Definição de mapeamento de imagens por modelo (as imagens devem estar na pasta assets)
model_images = {
    "VOLVO FMX 500 8X4": "/assets/VOLVO FMX 500 8X4.jpg",
    "MERCEDES BENZ AROCS 4851/45 8X4": "/assets/MERCEDES_BENZ_AROCS 4851_45_8X4.jpg",
    "MERCEDES BENZ AXOR 3344 6X4 (PIPA)": "/assets/MERCEDES BENZ AXOR 3344 6X4 (PIPA).jpg",
    "ESCAVADEIRA HIDRÁULICA CAT 374DL": "/assets/ESCAVADEIRA_HIDRÁULICA_CAT_374DL.jpg",
    "ESCAVADEIRA HIDRÁULICA VOLVO EC750DL": "/assets/ESCAVADEIRA_HIDRÁULICA_VOLVO_EC750DL.jpg",
    "PERFURATRIZ HIDRAULICA SANDVIK DP1500I": "/assets/PERFURATRIZ HIDRAULICA SANDVIK DP1500I.jpg",
    "PERFURATRIZ HIDRAULICA SANDVIK DX800": "/assets/PERFURATRIZ HIDRAULICA SANDVIK DP1500I.jpg",
    "TRATOR DE ESTEIRAS CAT D7": "/assets/TRATOR DE ESTEIRAS CAT D7.jpg", 
    "TRATOR DE ESTEIRAS CAT D6T": "/assets/TRATOR DE ESTEIRAS CAT D7.jpg",
    "TRATOR DE ESTEIRAS CAT D8": "/assets/TRATOR DE ESTEIRAS CAT D7.jpg",
    "TRATOR DE ESTEIRAS KOMATSU D155": "/assets/TRATOR DE ESTEIRAS KOMATSU D155.jpg",
    "ESCAVADEIRA HIDRÁULICA CAT 320": "/assets/ESCAVADEIRA HIDRÁULICA CAT 320.jpg",
    "ESCAVADEIRA HIDRÁULICA CAT 320 (ROMPEDOR)": "/assets/ESCAVADEIRA HIDRÁULICA CAT 320 (ROMPEDOR).jpg",
    "ESCAVADEIRA HIDRÁULICA CAT 352": "/assets/ESCAVADEIRA HIDRÁULICA CAT 320.jpg",
    "ESCAVADEIRA HIDRAULICA CAT 336NGX": "/assets/ESCAVADEIRA HIDRÁULICA CAT 320.jpg",  
    "ESCAVADEIRA HIDRAULICA SANY SY750H": "/assets/ESCAVADEIRA HIDRAULICA SANY SY750H.jpg",
    "ESCAVADEIRA HIDRÁULICA VOLVO EC480DL": "/assets/ESCAVADEIRA HIDRÁULICA VOLVO EC480DL.jpg",
    "MOTONIVELADORA CAT 140K": "/assets/MOTONIVELADORA CAT 140K.jpg",
    "PÁ CARREGADEIRA CAT 966L": "/assets/PÁ CARREGADEIRA CAT 966L.jpg",
    "RETRO ESCAVADEIRA CAT 416F2": "/assets/RETRO ESCAVADEIRA CAT 416F2.jpg",          
    # Adicione outros modelos e seus respectivos caminhos, se necessário.
}

# Tempo máximo considerado para a escala de cores (em segundos); por exemplo, 4 horas
MAX_DURATION_SECONDS = 4 * 60 * 60  # 4 horas

def get_color_for_duration(duration: timedelta) -> tuple[str, int]:
    """
    Retorna uma cor interpolada entre amarelo (#FFFF00) e vermelho (#FF0000)
    com base na duração informada, e o valor do componente green utilizado.
      - Duração = 0   -> amarelo
      - Duração >= MAX_DURATION_SECONDS -> vermelho
    """
    seconds = duration.total_seconds()
    fraction = min(seconds / MAX_DURATION_SECONDS, 1)
    green = int(255 * (1 - fraction))
    return f"rgb(255, {green}, 0)", green

@cache.memoize(timeout=300)
def get_all_records_cached() -> pd.DataFrame:
    """
    Consulta a tabela fato_hora para os últimos 7 dias e retorna todos os registros com todas as colunas.
    Essa versão utiliza cache para melhorar a performance.
    """
    query = (
        f"EXEC dw_sdp_mt_fas..usp_fato_hora "
        f"'{DAY_START:%d/%m/%Y %H:%M:%S}', '{DAY_END:%d/%m/%Y %H:%M:%S}'"
    )
    df = query_to_df(query)
    if df is None or df.empty:
        return pd.DataFrame()
    if "dt_registro" in df.columns:
        df["dt_registro"] = pd.to_datetime(df["dt_registro"], errors="coerce")
    return df

def get_all_records() -> pd.DataFrame:
    """
    Wrapper para obter registros utilizando cache.
    """
    return get_all_records_cached()

def get_current_state_records() -> pd.DataFrame:
    """
    Para cada equipamento, retorna o registro mais recente (baseado em dt_registro) e,
    se houver várias linhas com o mesmo id_lancamento, utiliza o menor dt_registro
    daquele id_lancamento para indicar quando o estado iniciou.
    Retorna um DataFrame com todas as colunas originais e uma nova coluna "dt_registro_inicio".
    """
    df = get_all_records()
    if df.empty:
        return pd.DataFrame()
    df = df.dropna(subset=["nome_equipamento", "id_lancamento", "dt_registro"])
    dt_min = df.groupby(["nome_equipamento", "id_lancamento"], as_index=False)["dt_registro"].min()
    df_sorted = df.sort_values("dt_registro")
    latest = df_sorted.groupby("nome_equipamento", as_index=False).last()
    current_state = pd.merge(latest, dt_min, on=["nome_equipamento", "id_lancamento"], suffixes=("", "_inicio"))
    return current_state

def get_latest_records_by_equipment() -> pd.DataFrame:
    """
    Função de compatibilidade: retorna os registros com estado atual, incluindo dt_registro_inicio.
    """
    return get_current_state_records()

def create_tv_layout(df: pd.DataFrame, filter_values: list[str] = None) -> html.Div:
    """
    Cria um layout para visualização em TV:
      - Cabeçalho com duas colunas: "Estado" e "Equipamento".
      - Para cada combinação (nome_estado, nome_tipo_estado), cria uma linha (dbc.Row) com:
          * Coluna esquerda: informações do estado (nome, tipo e quantidade de equipamentos).
          * Coluna direita: cartões dos equipamentos, onde cada cartão contém:
              - Uma caixinha menor com a imagem do modelo (ou placeholder, se não houver imagem).
              - Uma faixa horizontal com fundo colorido (de acordo com o tempo decorrido) e informações centralizadas.
    """
    if df.empty:
        return html.Div("Sem dados para agrupar.", className="text-center my-4")
    
    # Exclui registros do equipamento TRIMAK
    df = df[df["nome_equipamento"].str.upper() != "TRIMAK"]
    
    if filter_values:
        filter_values_upper = [v.upper().strip() for v in filter_values]
        df = df[df["nome_tipo_estado"].str.upper().str.strip().isin(filter_values_upper)]
    if df.empty:
        return html.Div("Nenhum equipamento corresponde ao filtro selecionado.", className="text-center my-4")
    
    df = df.sort_values(["nome_estado", "nome_tipo_estado", "nome_equipamento"])
    
    # Cria um dicionário de mapeamento de imagens com chave normalizada (uppercase e strip)
    normalized_model_images = {key.strip().upper(): url for key, url in model_images.items()}
    
    header = dbc.Row(
        [
            dbc.Col(
                html.H4("Estado", className="text-white m-0", style={"padding": "10px"}),
                width=3,
                style={"backgroundColor": "#0D6EFD"}
            ),
            dbc.Col(
                html.H4("Equipamento", className="text-white m-0", style={"padding": "10px"}),
                width=9,
                style={"backgroundColor": "#0D6EFD"}
            )
        ],
        className="mb-2"
    )
    
    group_cols = ["nome_estado", "nome_tipo_estado"]
    grouped = df.groupby(group_cols)
    
    rows = []
    now = datetime.now()
    for (estado, tipo), group_data in grouped:
        count_equip = len(group_data)
        left_col = [
            html.H5(estado, className="mb-0 text-white", style={"fontSize": "18px"}),
            html.H6(tipo, className="mb-0 text-white", style={"fontSize": "16px"}) if pd.notnull(tipo) else None,
            html.P(f"{count_equip} equipamento(s)", className="text-white", style={"fontSize": "14px"})
        ]
        left_col = [c for c in left_col if c is not None]
        
        equip_cards = []
        for _, row in group_data.iterrows():
            equip_name = row["nome_equipamento"]
            model_name = row.get("nome_modelo", "")
            
            dt_val = row.get("dt_registro_inicio")
            if not isinstance(dt_val, pd.Timestamp):
                dt_val = pd.to_datetime(dt_val, errors="coerce")
            if pd.notnull(dt_val):
                duration = now - dt_val
                time_str = dt_val.strftime("%d/%m/%Y %H:%M:%S")
                band_color, green_val = get_color_for_duration(duration)
                text_color = "black" if green_val > 200 else "white"
            else:
                time_str = "N/A"
                band_color = "#CCCCCC"
                text_color = "white"
            
            img_url = None
            if pd.notnull(model_name):
                img_url = normalized_model_images.get(model_name.strip().upper(), None)
            
            image_component = (
                html.Img(src=img_url, style={
                    "width": "120px", "height": "120px", "objectFit": "cover", "borderRadius": "4px"
                })
                if img_url else
                html.Div(style={
                    "width": "120px", "height": "120px", "backgroundColor": "#EEEEEE", "borderRadius": "4px"
                })
            )
            
            info_band = html.Div(
                [
                    html.Div(equip_name, style={"fontSize": "16px", "fontWeight": "bold", "color": text_color}),
                    html.Div(time_str, style={"fontSize": "12px", "color": text_color})
                ],
                style={
                    "backgroundColor": band_color,
                    "width": "100%",
                    "padding": "5px",
                    "textAlign": "center",
                    "borderRadius": "0 0 4px 4px"
                }
            )
            
            card = dbc.Card(
                dbc.CardBody(
                    html.Div(
                        [image_component, info_band],
                        style={"display": "flex", "flexDirection": "column", "alignItems": "center"}
                    )
                ),
                style={
                    "width": "180px",
                    "margin": "5px",
                    "padding": "0px",
                    "boxShadow": "0px 2px 4px rgba(0,0,0,0.1)",
                    "borderRadius": "4px",
                    "overflow": "hidden",
                    "backgroundColor": "#FFFFFF"
                }
            )
            equip_cards.append(card)
        
        right_col = html.Div(equip_cards, style={"display": "flex", "flexWrap": "wrap", "gap": "10px"})
        
        row_layout = dbc.Row(
            [
                dbc.Col(
                    html.Div(left_col),
                    width=3,
                    style={"backgroundColor": "#0D6EFD", "padding": "10px", "color": "white"}
                ),
                dbc.Col(
                    right_col,
                    width=9,
                    style={"backgroundColor": "#FFFFFF", "padding": "10px"}
                )
            ],
            className="mb-2"
        )
        rows.append(row_layout)
    
    return html.Div([header] + rows)

# ===================== LAYOUT PRINCIPAL =====================
layout = dbc.Container(
    [
        dbc.Row([
            dbc.Col(
                html.H1("Relatório 6 – Dashboard de Equipamentos", 
                        className="text-center", 
                        style={"fontFamily": "Arial, sans-serif"}),
                xs=12, md=10
            ),
            dbc.Col(
                dbc.Button("Voltar ao Portal", href="/", color="secondary", className="w-100"),
                xs=12, md=2
            )
        ], className="my-4"),
        dbc.Row([
            dbc.Col(
                dbc.Button("Atualizar", id="update-button", color="success", className="mb-3", 
                           style={"width": "100%"}),
                width=2
            ),
            dbc.Col(
                html.Div(id="last-update", 
                         style={"fontSize": "14px", "textAlign": "center", "paddingTop": "15px"}),
                width=10
            )
        ], justify="center"),
        dcc.Interval(id="interval-component", interval=300000, n_intervals=0),
        dbc.Row(
            dbc.Col(
                dcc.Dropdown(
                    id="filter-dropdown",
                    multi=True,
                    placeholder="Selecione os tipos de estado (nome_tipo_estado) para filtrar...",
                    clearable=False,
                    style={"marginBottom": "20px"}
                ),
                width=12
            )
        ),
        dcc.Store(id="latest-data-store"),
        dcc.Loading(
            id="loading-tv-layout",
            type="default",
            children=html.Div(id="tv-layout")
        )
    ],
    fluid=True,
    style={"minHeight": "100vh", "width": "100vw"}
)

@callback(
    Output("latest-data-store", "data"),
    Output("last-update", "children"),
    Input("update-button", "n_clicks"),
    Input("interval-component", "n_intervals")
)
def update_data(n_clicks, n_intervals):
    latest = get_latest_records_by_equipment()
    if latest.empty:
        return None, "Sem dados"
    # Remove registros do equipamento TRIMAK
    latest = latest[latest["nome_equipamento"].str.upper() != "TRIMAK"]
    json_data = latest.to_json(orient="records", date_format="iso")
    last_update_text = "Última atualização: " + datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    return json_data, last_update_text

@callback(
    Output("filter-dropdown", "options"),
    Output("filter-dropdown", "value"),
    Input("latest-data-store", "data")
)
def update_filter_options(json_data):
    """
    Atualiza as opções do Dropdown e define os valores pré-selecionados.
    """
    if not json_data:
        return [], []

    df = pd.read_json(json_data, orient="records")
    # Normaliza para uppercase
    df["nome_tipo_estado"] = df["nome_tipo_estado"].str.upper()
    
    tipos = sorted(df["nome_tipo_estado"].dropna().unique())
    options = [{"label": t, "value": t} for t in tipos]
    
    default_preselection = [
        "MANUTENÇÃO CORRETIVA",
        "MANUTENÇÃO PREVENTIVA",
        "MANUTENÇÃO OPERACIONAL",
        "FORA DE FROTA"
    ]
    default_value = [t for t in default_preselection if t in tipos]
    
    return options, default_value

@callback(
    Output("tv-layout", "children"),
    Input("latest-data-store", "data"),
    Input("filter-dropdown", "value")
)
def render_tv_layout(json_data, filter_values):
    if not json_data:
        return html.Div("Clique em 'Atualizar' para carregar os dados.", className="text-center my-4")
    df = pd.read_json(json_data, orient="records")
    return create_tv_layout(df, filter_values)
