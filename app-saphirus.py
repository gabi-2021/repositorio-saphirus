import streamlit as st
import pandas as pd
import re
from pypdf import PdfReader
from twilio.rest import Client
import logging
import uuid

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Repositor V49", page_icon="⚡", layout="wide")
st.title("⚡ Repositor V49 (Modo Seguro)")

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 5rem !important;
    }
    /* Botones compactos */
    div[data-testid="column"] button {
        height: auto !important;
        padding: 0.25rem 0.5rem !important;
        font-size: 0.8rem !important;
        min-height: 0px !important;
    }
    /* Estilo botón Finalizar/Ocultar */
    div[data-testid="column"] button[kind="secondary"] {
        border-color: #c3e6cb;
        color: #155724;
        background-color: #d4edda;
    }
    /* Estilo botón Reset Ocultas */
    .stButton button:contains("Mostrar") {
        border-color: #bee5eb;
        color: #0c5460;
    }
</style>
""", unsafe_allow_html=True)

# --- GESTIÓN DE ESTADO ---
if 'audit_data' not in st.session_state:
    st.session_state.audit_data = [] 
if 'audit_started' not in st.session_state:
    st.session_state.audit_started = False
# NUEVO: Lista de categorías ocultas (Archivadas)
if 'cats_ocultas' not in st.session_state:
    st.session_state.cats_ocultas = set()
if 'stock_report_log' not in st.session_state:
    st.session_state.stock_report_log = []
# --- CREDENCIALES ---
def cargar_credenciales():
    try:
        return {
            'SID': st.secrets["TWILIO_SID"],
            'TOK': st.secrets["TWILIO_TOKEN"],
            'FROM': st.secrets["TWILIO_FROM"],
            'TO': st.secrets["TWILIO_TO"]
        }
    except:
        return {'SID': '', 'TOK': '', 'FROM': '', 'TO': ''}

credentials = cargar_credenciales()

# --- REGEX PRE-COMPILADOS ---
PATRONES = {
    'general': [re.compile(p, re.IGNORECASE) for p in [r"\s*[-–]?\s*SAPHIRUS.*$", r"\s*[-–]?\s*AMBAR.*$", r"^[-–]\s*", r"\s*[-–]$"]],
    'textil_disney': [re.compile(p, re.IGNORECASE) for p in [r"^AROMATIZADOR\s+TEXTIL(\s+DISNEY)?\s*[-–]?\s*DISNEY\s*[-–]?\s*(MARVEL\s*[-–]?\s*)?", r"^AROMATIZADOR\s+TEXTIL\s*[-–]?\s*(MARVEL\s*[-–]?\s*)?"]],
    'difusor_disney': [re.compile(p, re.IGNORECASE) for p in [r"^DIFUSOR\s+AROMATICO(\s+DISNEY)?\s*[-–]?\s*DISNEY\s*[-–]?\s*(MARVEL\s*[-–]?\s*)?", r"^DIFUSOR\s+AROMATICO\s*[-–]?\s*(MARVEL\s*[-–]?\s*)?"]],
    'tarjeta': [re.compile(r"^TARJETA\s+AROMATICA(\s+SAPHIRUS)?\s*", re.IGNORECASE)],
    'sahumerio_saphirus': [re.compile(r"^SAHUMERIO SAPHIRUS\s*[-–]?\s*", re.IGNORECASE)],
    'shiny_general': [(re.compile(r"^LIMPIAVIDRIOS.*", re.IGNORECASE), "LIMPIAVIDRIOS"), (re.compile(r"^DESENGRASANTE.*", re.IGNORECASE), "DESENGRASANTE"), (re.compile(r"^LUSTRAMUEBLES?.*", re.IGNORECASE), "LUSTRAMUEBLE")],
    'limpiadores': [re.compile(p, re.IGNORECASE) for p in [r"^LIMPIADOR\s+LIQUIDO\s+MULTISUPERFICIES\s*250\s*ML\s*[-–]?\s*SHINY\s*[-–]?\s*", r"\s*\d{4,6}$"]],
    'premium': [re.compile(p, re.IGNORECASE) for p in [r"^DIFUSOR PREMIUM\s*[-–]?\s*", r"\s*[-–]?\s*AROMATICO.*$"]],
    'home_spray': [re.compile(p, re.IGNORECASE) for p in [r"^HOME SPRAY\s*[-–]?\s*", r"\s*[-–]?\s*AROMATIZANTE\s+TEXTIL.*$", r"\s*500\s*ML.*$"]],
    'repuesto_touch': [re.compile(p, re.IGNORECASE) for p in [r"(\d+\s*)?GR.*?CM3\s*[-–]?\s*", r"^REPUESTO TOUCH\s*[-–]?\s*"]],
    'aceites': [re.compile(r"^ACEITE\s+ESENCIAL\s*[-–]?\s*", re.IGNORECASE)],
    'antihumedad': [re.compile(p, re.IGNORECASE) for p in [r"ANTI\s+HUMEDAD", r"SAPHIRUS", r"[-–]\s*\d+$"]],
    'perfumes': [re.compile(p, re.IGNORECASE) for p in [r"PERFUME MINI MILANO\s*[-–]?\s*", r"SAPHIRUS PARFUM\s*"]],
    'aparatos': [(re.compile(r".*LATERAL.*", re.IGNORECASE), "LATERAL"), (re.compile(r".*FRONTAL.*", re.IGNORECASE), "FRONTAL"), (re.compile(r".*DIGITAL.*", re.IGNORECASE), "DIGITAL"), (re.compile(r".*NEGRO.*", re.IGNORECASE), "NEGRO"), (re.compile(r".*GRIS.*", re.IGNORECASE), "GRIS"), (re.compile(r".*ROSA.*", re.IGNORECASE), "ROSA"), (re.compile(r".*BEIGE.*", re.IGNORECASE), "BEIGE"), (re.compile(r".*BLANCO.*", re.IGNORECASE), "BLANCO"), (re.compile(r".*HORNILLO.*", re.IGNORECASE), "HORNILLO CHICO"), (re.compile(r"APARATO ANALOGICO DECO", re.IGNORECASE), "ANALOGICO")],
    'sahumerio_ambar': [re.compile(r"^SAHUMERIO\s*[-–]?\s*AMBAR\s*[-–]?\s*", re.IGNORECASE)],
    'sahumerio_tipo': [re.compile(p, re.IGNORECASE) for p in [r"^SAHUMERIO HIERBAS\s*[-–]?\s*", r"^SAHUMERIO HIMALAYA\s*[-–]?\s*", r"^SAHUMERIO\s*[-–]?\s*"]],
    'dispositivo_touch': [re.compile(p, re.IGNORECASE) for p in [r"^DISPOSITIVO TOUCH\s*(\+)?\s*", r"\s*\d{6,}$"]],
    'textil_mini': [re.compile(r"^AROMATIZADOR TEXTIL MINI 60 ML\s*[-–]?\s*", re.IGNORECASE)],
    'textil': [re.compile(p, re.IGNORECASE) for p in [r"^AROMATIZADOR TEXTIL 150 ML AMBAR\s*[-–]?\s*", r"^AROMATIZADOR TEXTIL 250 ML\s*[-–]?\s*", r"^AROMATIZADOR TEXTIL MINI 60 ML\s*[-–]?\s*", r"^AROMATIZADOR TEXTIL\s*[-–]?\s*"]],
    'autos': [re.compile(p, re.IGNORECASE) for p in [r"CARITAS EMOGI X 2", r"RUTA 66", r"AROMATIZANTE AUTO", r"\s*X\s*2.*$"]],
    'velas': [(re.compile(r"VELAS SAPHIRUS", re.IGNORECASE), "VELAS")],
    'aerosol': [re.compile(r"^AEROSOL\s*[-–]?\s*", re.IGNORECASE)],
    'difusor': [re.compile(p, re.IGNORECASE) for p in [r"^DIFUSOR AROMATICO\s*[-–]?\s*", r"^DIFUSOR\s*[-–]?\s*", r"\s*[-–]?\s*VARILLA.*$"]],
}

# --- CATEGORIAS ---
CATEGORIAS = {
    'textil_disney': {'pattern': lambda p: "TEXTIL" in p and "DISNEY" in p, 'emoji': "", 'nombre': "TEXTILES DISNEY", 'prioridad': 0.1},
    'difusor_disney': {'pattern': lambda p: "DIFUSOR" in p and "DISNEY" in p, 'emoji': "", 'nombre': "DIFUSORES DISNEY", 'prioridad': 0.2},
    'tarjeta': {'pattern': lambda p: "TARJETA" in p and "AROMATICA" in p, 'emoji': "💳", 'nombre': "Tarjetas Aromáticas", 'prioridad': 0.5},
    'sahumerio_saphirus': {'pattern': lambda p: "SAHUMERIO" in p and "SAPHIRUS" in p and not any(x in p for x in ["AMBAR", "HIMALAYA", "HIERBAS"]), 'emoji': "🧘‍♂️", 'nombre': "Sahumerios Saphirus", 'prioridad': 14.5},
    'touch_dispositivo': {'pattern': lambda p: "DISPOSITIVO" in p and "TOUCH" in p, 'emoji': "🖱️", 'nombre': "Dispositivos Touch", 'prioridad': 1},
    'touch_repuesto': {'pattern': lambda p: ("REPUESTO" in p and "TOUCH" in p) or "GR/13" in p, 'emoji': "🔄", 'nombre': "Repuestos de Touch", 'prioridad': 2},
    'perfume_mini': {'pattern': lambda p: "MINI MILANO" in p, 'emoji': "🧴", 'nombre': "Perfume Mini Milano", 'prioridad': 3},
    'perfume_parfum': {'pattern': lambda p: "PARFUM" in p, 'emoji': "🧴", 'nombre': "Parfum / Perfumes", 'prioridad': 4},
    'shiny_general': {'pattern': lambda p: "SHINY" in p and ("LIMPIAVIDRIOS" in p or "DESENGRASANTE" in p or "LUSTRAMUEBLE" in p), 'emoji': "✨", 'nombre': "Shiny General", 'prioridad': 5},
    'ambar_aerosol': {'pattern': lambda p: "AMBAR" in p and "AEROSOL" in p, 'emoji': "🔸", 'nombre': "Aerosoles Ambar", 'prioridad': 6},
    'ambar_textil': {'pattern': lambda p: "AMBAR" in p and ("TEXTIL" in p or "150 ML" in p), 'emoji': "🔸", 'nombre': "Textiles Ambar", 'prioridad': 7},
    'ambar_sahumerio': {'pattern': lambda p: "AMBAR" in p and "SAHUMERIO" in p, 'emoji': "🔸", 'nombre': "Sahumerios Ambar", 'prioridad': 8},
    'ambar_varios': {'pattern': lambda p: "AMBAR" in p, 'emoji': "🔸", 'nombre': "Línea Ambar Varios", 'prioridad': 9},
    'home_spray': {'pattern': lambda p: "HOME SPRAY" in p or "500 ML" in p or "500ML" in p, 'emoji': "🏠", 'nombre': "Home Spray", 'prioridad': 10},
    'aparatos': {'pattern': lambda p: "APARATO" in p or "HORNILLO" in p, 'emoji': "⚙️", 'nombre': "Aparatos", 'prioridad': 11},
    'premium': {'pattern': lambda p: "PREMIUM" in p, 'emoji': "💎", 'nombre': "Difusores Premium", 'prioridad': 12},
    'sahumerio_hierbas': {'pattern': lambda p: "SAHUMERIO" in p and "HIERBAS" in p, 'emoji': "🌿", 'nombre': "Sahumerios Hierbas", 'prioridad': 13},
    'sahumerio_himalaya': {'pattern': lambda p: "SAHUMERIO" in p and "HIMALAYA" in p, 'emoji': "🏔️", 'nombre': "Sahumerios Himalaya", 'prioridad': 14},
    'sahumerio_varios': {'pattern': lambda p: "SAHUMERIO" in p, 'emoji': "🧘", 'nombre': "Sahumerios Varios", 'prioridad': 15},
    'auto_caritas': {'pattern': lambda p: "CARITAS" in p, 'emoji': "😎", 'nombre': "Autos - Caritas", 'prioridad': 16},
    'auto_ruta': {'pattern': lambda p: "RUTA" in p or "RUTA 66" in p, 'emoji': "🛣️", 'nombre': "Autos - Ruta 66", 'prioridad': 17},
    'auto_varios': {'pattern': lambda p: "AUTO" in p, 'emoji': "🚗", 'nombre': "Autos - Varios", 'prioridad': 18},
    'textil_mini': {'pattern': lambda p: "TEXTIL" in p and "MINI" in p, 'emoji': "🤏", 'nombre': "Textiles Mini", 'prioridad': 19},
    'textil': {'pattern': lambda p: "TEXTIL" in p, 'emoji': "👕", 'nombre': "Textiles Saphirus", 'prioridad': 20},
    'aerosol': {'pattern': lambda p: "AEROSOL" in p, 'emoji': "💨", 'nombre': "Aerosoles Saphirus", 'prioridad': 21},
    'difusor': {'pattern': lambda p: "DIFUSOR" in p or "VARILLA" in p, 'emoji': "🎍", 'nombre': "Difusores", 'prioridad': 22},
    'vela': {'pattern': lambda p: "VELA" in p, 'emoji': "🕯️", 'nombre': "Velas", 'prioridad': 23},
    'aceite': {'pattern': lambda p: "ACEITE" in p, 'emoji': "💧", 'nombre': "Aceites", 'prioridad': 24},
    'antihumedad': {'pattern': lambda p: "ANTIHUMEDAD" in p, 'emoji': "💧", 'nombre': "Antihumedad", 'prioridad': 25},
    'limpiador': {'pattern': lambda p: "LIMPIADOR" in p, 'emoji': "🧼", 'nombre': "Limpiadores Multisuperficies", 'prioridad': 26},
}

def detectar_categoria(producto):
    p = producto.upper()
    for key, config in sorted(CATEGORIAS.items(), key=lambda x: x[1]['prioridad']):
        if config['pattern'](p):
            prefix = f"{config['emoji']} " if config['emoji'] else ""
            return f"{prefix}{config['nombre']}"
    return "📦 Varios"

def aplicar_reglas_compiladas(texto, reglas):
    resultado = texto.upper()
    for regla in reglas:
        if isinstance(regla, tuple):
            patron, reemplazo = regla
            resultado = patron.sub(reemplazo, resultado)
        else:
            resultado = regla.sub("", resultado)
    return re.sub(r"\s+", " ", resultado).strip()

def limpiar_producto_por_categoria(row):
    cat = row["Categoria"]
    nom = row["Producto"]
    
    mapeo = {
        "TEXTILES DISNEY": 'textil_disney', "DIFUSORES DISNEY": 'difusor_disney', 
        "Tarjetas Aromáticas": 'tarjeta', "Sahumerios Saphirus": 'sahumerio_saphirus', 
        "Shiny General": 'shiny_general', "Limpiadores": 'limpiadores', "Difusores Premium": 'premium', 
        "Aceites": 'aceites', "Sahumerios Ambar": 'sahumerio_ambar', "Repuestos de Touch": 'repuesto_touch', 
        "Dispositivos Touch": 'dispositivo_touch', "Antihumedad": 'antihumedad', "Perfume": 'perfumes', 
        "Parfum": 'perfumes', "Aparatos": 'aparatos', "Sahumerios": 'sahumerio_tipo', "Home Spray": 'home_spray', 
        "Textiles Mini": 'textil_mini', "Textiles": 'textil', "Autos": 'autos', "Aerosoles": 'aerosol', 
        "Difusores": 'difusor', "Velas": 'velas',
    }
    
    for key, regla_key in mapeo.items():
        if key in cat:
            if regla_key == 'aparatos':
                 res = aplicar_reglas_compiladas(nom, PATRONES['aparatos'])
                 return res
            resultado = aplicar_reglas_compiladas(nom, PATRONES.get(regla_key, []))
            resultado = aplicar_reglas_compiladas(resultado, PATRONES['general'])
            if "Touch" in cat and "REPUESTO NEGRO" in resultado: 
                resultado = resultado.replace("REPUESTO NEGRO", "NEGRO + REPUESTO")
            return resultado if len(resultado) >= 2 else nom
    return aplicar_reglas_compiladas(nom, PATRONES['general'])

def extraer_texto_pdf(archivo):
    try:
        reader = PdfReader(archivo)
        texto = "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        return texto.replace("\n", " ")
    except Exception: return None

def parsear_datos(texto):
    datos = []
    matches = re.findall(r'"\s*(\d{8})\s*"\s*,\s*"\s*([-0-9,]+)\s+([^"]+)"', texto)
    if not matches:
        matches = re.findall(r'(\d{8})\s+([-0-9]+,\d{2})\s+(.*?)(?=\s\d{1,3}(?:\.\d{3})*,\d{2})', texto)
    for m in matches:
        datos.append({"ID": m[0], "Cantidad": m[1], "Producto": m[2].strip()})
    return datos

def limpiar_dataframe(df):
    df["Cantidad"] = df["Cantidad"].apply(lambda x: float(x.replace(",", ".")) if isinstance(x, str) else x)
    df["Producto"] = df["Producto"].apply(lambda x: re.sub(r'^\d{8}\s*', '', x.strip()))
    df = df[df["Cantidad"] > 0]
    df["Categoria"] = df["Producto"].apply(detectar_categoria)
    df["Producto"] = df.apply(limpiar_producto_por_categoria, axis=1)
    return df.groupby(["Categoria", "Producto"], as_index=False)["Cantidad"].sum()

@st.cache_data
def procesar_pdf(archivo):
    try:
        texto = extraer_texto_pdf(archivo)
        if not texto: return None
        datos = parsear_datos(texto)
        if not datos: return None
        df = pd.DataFrame(datos)
        return limpiar_dataframe(df)
    except Exception as e:
        return None

def preparar_datos_auditoria(texto_lista):
    items = []
    categoria_actual = "General"
    lineas = texto_lista.split('\n')
    for linea in lineas:
        linea = linea.strip()
        if not linea: continue
        if linea.startswith("==") and linea.endswith("=="):
            categoria_actual = linea.replace("==", "").strip()
        elif " x " in linea:
            try:
                partes = linea.split(" x ", 1)
                cant_str = partes[0].strip()
                prod = partes[1].strip()
                cant = float(cant_str) if '.' in cant_str else int(cant_str)
                items.append({
                    "id": str(uuid.uuid4()),
                    "Categoría": categoria_actual,
                    "Producto": prod,
                    "Cantidad": cant,
                    "Estado": "pdte." # Abreviatura por defecto
                })
            except: continue
    return items

def generar_listas_finales(data):
    pedido_web = {} 
    reponido = {}
    pendiente = {}
    
    # Nuevo mapeo con abreviaturas
    mapa_estados = {"ped.": "pedido", "rep.": "repuesto", "pdte.": "pendiente"}
    
    for item in data:
        cat = item['Categoría']
        linea = f"{item['Cantidad']} x {item['Producto']}"
        status_normalizado = mapa_estados.get(item['Estado'], "pendiente")
        
        if status_normalizado == 'pedido':
            if cat not in pedido_web: pedido_web[cat] = []
            pedido_web[cat].append(linea)
        elif status_normalizado == 'repuesto':
            if cat not in reponido: reponido[cat] = []
            reponido[cat].append(linea)
        elif status_normalizado == 'pendiente':
            if cat not in pendiente: pendiente[cat] = []
            pendiente[cat].append(linea)
    return pedido_web, reponido, pendiente

def formatear_lista_texto(diccionario, titulo):
    if not diccionario: return ""
    txt = f"📋 *{titulo.upper()}*\n"
    for cat in sorted(diccionario.keys()):
        txt += f"\n== {cat} ==\n"
        for prod in diccionario[cat]:
            txt += f"{prod}\n"
    return txt

def generar_mensaje_df(df):
    txt = "📋 *LISTA DE REPOSICIÓN*\n"
    for c in sorted(df["Categoria"].unique()):
        txt += f"\n== {c.upper()} ==\n"
        for _, r in df[df["Categoria"] == c].sort_values("Producto").iterrows():
            cant = int(r['Cantidad']) if r['Cantidad'].is_integer() else r['Cantidad']
            txt += f"{cant} x {r['Producto']}\n"
    return txt

def enviar_whatsapp(mensaje, creds):
    if not all([creds['SID'], creds['TOK'], creds['FROM'], creds['TO']]):
        st.error("Faltan credenciales o internet.")
        return False
    try:
        Client(creds['SID'], creds['TOK']).messages.create(body=mensaje, from_=creds['FROM'], to=creds['TO'])
        return True
    except Exception as e:
        st.error(f"Error envío: {e}")
        return False

# --- LÓGICA DE EDICIÓN AVANZADA (Borrar, Añadir) ---
def actualizar_datos_categoria(df_nuevo, categoria):
    # 1. Convertir DF editado a diccionarios
    nuevos_items = df_nuevo.to_dict('records')
    
    # 2. Separar datos: Conservar todo lo que NO es de esta categoría
    otros_items = [x for x in st.session_state.audit_data if x['Categoría'] != categoria]
    
    # 3. Procesar los nuevos datos de ESTA categoría
    items_procesados = []
    for item in nuevos_items:
        # Si agregaron fila nueva, generar ID
        if not item.get('id') or pd.isna(item.get('id')):
            item['id'] = str(uuid.uuid4())
        
        # Asegurar consistencia
        item['Categoría'] = categoria
        if not item.get('Producto'): item['Producto'] = "Nuevo Item"
        if not item.get('Cantidad'): item['Cantidad'] = 1.0
        if not item.get('Estado'): item['Estado'] = "pdte."
            
        items_procesados.append(item)
    
    # 4. Reconstruir estado global
    st.session_state.audit_data = otros_items + items_procesados

# NUEVO: Ocultar categoría sin borrar datos
def ocultar_categoria(cat_target):
    st.session_state.cats_ocultas.add(cat_target)
    st.rerun()

def restaurar_todas_categorias():
    st.session_state.cats_ocultas.clear()
    st.rerun()

def actualizar_categoria_masiva(cat_target, nuevo_estado):
    for item in st.session_state.audit_data:
        if item['Categoría'] == cat_target:
            item['Estado'] = nuevo_estado
    st.rerun()

# --- UI PRINCIPAL ---
# --- BUSCA ESTA LÍNEA Y REEMPLÁZALA POR ESTA NUEVA ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📄 Procesar", "➕ Sumar", "✅ Auditoría", "📊 Totales", "🆚 Comparar", "📦 Control Stock"])

# TAB 1
with tab1:
    archivo = st.file_uploader("Subir PDF", type="pdf")
    if archivo:
        df_res = procesar_pdf(archivo)
        if df_res is not None and not df_res.empty:
            msg = generar_mensaje_df(df_res)
            st.code(msg, language='text')
            if credentials['SID'] and st.button("Enviar WhatsApp"):
                 if enviar_whatsapp(msg, credentials): st.success("Enviado")
        else: st.error("Error al leer PDF.")

# TAB 2 SUMAR
with tab2:
    st.header("➕/➖ Operaciones con Listas")
    l1 = st.text_area("Lista 1 (Base)", height=150, key="sum_l1")
    l2 = st.text_area("Lista 2 (A sumar/restar)", height=150, key="sum_l2")
    
    col_b1, col_b2 = st.columns(2)
    btn_sumar = col_b1.button("➕ Sumar Listas", use_container_width=True)
    btn_restar = col_b2.button("➖ Restar Listas", use_container_width=True)
    
    if btn_sumar or btn_restar:
        es_suma = btn_sumar
        
        def parse_complex(txt):
            d = {}
            cat = "General"
            titulo = ""
            titulo_original = ""
            lineas = txt.split('\n')
            
            # Intentar extraer el título de la primera línea no vacía
            for linea in lineas:
                if linea.strip():
                    # Si no es categoría ni producto, asumimos que es título
                    if not linea.strip().startswith("==") and " x " not in linea.lower():
                        titulo = re.sub(r'[^\w\s]', '', linea).strip().upper()
                        titulo_original = linea.strip()
                    break
            
            if not titulo:
                titulo = "SIN TITULO"
                    
            for linea in lineas:
                linea = linea.strip()
                if "==" in linea: 
                    cat = linea.replace("==", "").strip()
                elif " x " in linea.lower() or " X " in linea.upper():
                    # Separar por la x sin importar mayúsculas
                    if " x " in linea:
                        p = linea.split(" x ", 1)
                    else:
                        p = linea.split(" X ", 1)
                        
                    if len(p) == 2:
                        try:
                            c = float(p[0])
                            prod = p[1].strip()
                            if cat not in d: d[cat] = {}
                            d[cat][prod] = d[cat].get(prod, 0) + c
                        except: pass
            return d, titulo, titulo_original

        d1, tit1, original_tit1 = parse_complex(l1)
        d2, tit2, original_tit2 = parse_complex(l2)
        
        # Lógica para definir el título final
        if tit1 and tit1 == tit2 and tit1 != "SIN TITULO":
            # Si coinciden (ej. ambas son "PEDIDO WEB"), conserva el título con emojis y formato
            titulo_final = original_tit1
        else:
            # Si son distintas o no tienen título claro, usamos uno genérico
            titulo_final = "📋 *LISTA SUMADA*" if es_suma else "📋 *LISTA RESTADA*"
            
        total = {}
        # Primero copiar L1 completa
        for c, prods in d1.items():
            total[c] = prods.copy()
            
        # Luego operar con L2
        for c, prods in d2.items():
            if c not in total: 
                total[c] = {}
            for p, qty in prods.items():
                if es_suma:
                    total[c][p] = total[c].get(p, 0) + qty
                else:
                    total[c][p] = total[c].get(p, 0) - qty
        
        # Generar texto final
        txt_fin = f"{titulo_final}\n"
        for c in sorted(total.keys()):
            # IMPORTANTE: Filtrar para que solo queden productos con cantidad mayor a 0
            items_validos = {p: q for p, q in total[c].items() if q > 0}
            
            # Solo agregar la categoría si le quedaron productos
            if items_validos:
                txt_fin += f"\n== {c} ==\n"
                for p in sorted(items_validos.keys()):
                    q = items_validos[p]
                    q_fmt = int(q) if q.is_integer() else q
                    txt_fin += f"{q_fmt} x {p}\n"
                    
        st.code(txt_fin)
# TAB 3: AUDITORÍA
with tab3:
    st.header("🕵️ Auditoría")
    
    if not st.session_state.audit_started:
        input_audit = st.text_area("Pega la lista aquí:", height=150)
        if st.button("🚀 Iniciar", type="primary"):
            if input_audit:
                st.session_state.audit_data = preparar_datos_auditoria(input_audit)
                st.session_state.audit_started = True
                st.rerun()
    else:
        col_act, col_reset = st.columns([3, 1])
        with col_reset:
            if st.button("🔄 Reiniciar Todo"):
                st.session_state.audit_started = False
                st.session_state.audit_data = []
                st.session_state.cats_ocultas.clear()
                st.rerun()
        
        if st.session_state.audit_data:
            df_full = pd.DataFrame(st.session_state.audit_data)
            categorias = sorted(df_full['Categoría'].unique())
            
            cats_visibles = 0
            for cat in categorias:
                if cat in st.session_state.cats_ocultas:
                    continue
                
                cats_visibles += 1
                df_cat = df_full[df_full['Categoría'] == cat].copy()
                df_cat.reset_index(drop=True, inplace=True)
                
                # Inyectamos una columna temporal para los tildes
                df_cat.insert(0, "Seleccionar", False)
                
                safe_key = f"ed_{re.sub(r'[^a-zA-Z0-9]', '', cat)}"
                
                with st.expander(f"📂 {cat} ({len(df_cat)})", expanded=False):
                    # BARRA DE HERRAMIENTAS
                    mc1, mc2, mc3, mc4 = st.columns([1, 1, 1, 1])
                    if mc1.button("Todo Ped.", key=f"bp_{safe_key}"):
                        actualizar_categoria_masiva(cat, "ped.")
                    if mc2.button("Todo Rep.", key=f"br_{safe_key}"):
                        actualizar_categoria_masiva(cat, "rep.")
                    if mc3.button("Reset", key=f"brst_{safe_key}"):
                        actualizar_categoria_masiva(cat, "pdte.")
                    
                    if mc4.button("🔒 Listo", key=f"hide_{safe_key}", help="Ocultar esta categoría"):
                        ocultar_categoria(cat)
                    
                    # TABLA EDITABLE CON CHECKBOX
                    edited_df_cat = st.data_editor(
                        df_cat,
                        column_config={
                            "Seleccionar": st.column_config.CheckboxColumn("✔", width="small"),
                            "_index": None,
                            "Estado": st.column_config.SelectboxColumn("Est", options=["pdte.", "ped.", "rep."], required=True, width="small"),
                            "Cantidad": st.column_config.NumberColumn("Cant", min_value=0, width="small"),
                            "Producto": st.column_config.TextColumn("Producto"),
                            "Categoría": None,
                            "id": None
                        },
                        hide_index=True,
                        use_container_width=True,
                        num_rows="dynamic", 
                        key=safe_key
                    )
                    
                    # LÓGICA DE EDICIÓN MULTIPLE (Evita el teclado en el celular)
                    filas_seleccionadas = edited_df_cat[edited_df_cat["Seleccionar"] == True]
                    if not filas_seleccionadas.empty:
                        st.caption("Acción para ítems seleccionados:")
                        bc1, bc2, bc3 = st.columns([1, 1, 2])
                        ids_seleccionados = filas_seleccionadas["id"].tolist()
                        
                        if bc1.button("📦 Ped.", key=f"mped_{safe_key}", type="primary"):
                            for item in st.session_state.audit_data:
                                if item["id"] in ids_seleccionados: item["Estado"] = "ped."
                            st.rerun()
                        if bc2.button("✅ Rep.", key=f"mrep_{safe_key}", type="primary"):
                            for item in st.session_state.audit_data:
                                if item["id"] in ids_seleccionados: item["Estado"] = "rep."
                            st.rerun()

                    # Limpiamos la columna 'Seleccionar' antes de guardar los datos reales
                    df_para_guardar = edited_df_cat.drop(columns=["Seleccionar"])
                    df_original = df_cat.drop(columns=["Seleccionar"])
                    
                    if not df_original.equals(df_para_guardar):
                        actualizar_datos_categoria(df_para_guardar, cat)
                        st.rerun()
            
            # GESTIÓN SELECTIVA DE CATEGORÍAS OCULTAS
            if len(st.session_state.cats_ocultas) > 0:
                st.divider()
                st.info(f"Tienes {len(st.session_state.cats_ocultas)} categorías ocultas.")
                
                col_sel, col_btn = st.columns([3, 1])
                with col_sel:
                    cats_a_restaurar = st.multiselect("Elige cuáles mostrar de nuevo:", list(st.session_state.cats_ocultas))
                with col_btn:
                    st.write("") # Espaciador para alinear
                    st.write("")
                    if st.button("👁️ Restaurar") and cats_a_restaurar:
                        for c in cats_a_restaurar:
                            st.session_state.cats_ocultas.remove(c)
                        st.rerun()
            
            if cats_visibles == 0 and len(categorias) > 0:
                st.success("🎉 ¡Todas las categorías han sido revisadas!")

        st.divider()
        lp, lr, lpen = generar_listas_finales(st.session_state.audit_data)
        ft1, ft2, ft3 = st.tabs(["📉 Pedido", "✅ Repuesto", "❌ Pendientes"])
        with ft1: st.code(formatear_lista_texto(lp, "Pedido Web"))
        with ft2: st.code(formatear_lista_texto(lr, "Repuesto Hoy"))
        with ft3: st.code(formatear_lista_texto(lpen, "Pendientes"))
# TAB 4
with tab4:
    st.header("Totales")
    list_input_totales = st.text_area("Lista para sumar:", height=150, key="tot_input")
    if st.button("Calcular"):
        totales = {} 
        cat = "General"
        for line in list_input_totales.split('\n'):
            line = line.strip()
            if "==" in line: cat = line.replace("==", "").strip()
            elif " x " in line:
                try:
                    p = line.split(" x ", 1); qty = float(p[0])
                    totales[cat] = totales.get(cat, 0) + qty
                except: pass
        txt = ""
        for c, q in totales.items():
            q_fmt = int(q) if q.is_integer() else q
            txt += f"{c}: {q_fmt}\n"
        st.code(txt)

# TAB 5
with tab5:
    st.header("Comparador")
    ca = st.text_area("Lista A", height=150, key="ca")
    cb = st.text_area("Lista B", height=150, key="cb")
    if st.button("Comparar"):
        def parse_c(t):
            d = {}
            for l in t.split('\n'):
                if " x " in l: p = l.split(" x ", 1); d[p[1].strip().upper()] = float(p[0])
            return d
        da = parse_c(ca); db = parse_c(cb)
        falta = {k: v for k, v in da.items() if k not in db}
        sobra = {k: v for k, v in db.items() if k not in da}
        dif = {k: (v, db[k]) for k, v in da.items() if k in db and v != db[k]}
        t1, t2, t3 = st.tabs([f"Faltan ({len(falta)})", f"Sobran ({len(sobra)})", f"Dif ({len(dif)})"])
        with t1:
             for k,v in falta.items(): st.write(f"- {v} x {k}")
        with t2:
             for k,v in sobra.items(): st.write(f"- {v} x {k}")
        with t3:
             for k,v in dif.items(): st.write(f"**{k}**: {v[0]} -> {v[1]}")
# --- TAB 6: CONTROL DE STOCK ---
with tab6:
    st.header("Generador de Reporte de Stock")
    
    col_input, col_output = st.columns([1, 1.5])
    
    with col_input:
        st.subheader("Ingreso de Datos")
        with st.form("form_stock"):
            # Fila 1: Identificación
            c1, c2 = st.columns([1, 2])
            id_art = c1.text_input("ID ARTICULO", placeholder="Ej: 75500082")
            nom_art = c2.text_input("NOMBRE", placeholder="Ej: ESFERAS MAGICAS...")
            
            # Fila 2: Cantidades (Lo más importante)
            c3, c4 = st.columns(2)
            st_depo = c3.number_input("STOCK REAL", step=1, value=0)
            st_sis = c4.number_input("STOCK SISTEMA", step=1, value=0)
            
            # Fila 3: Checks (Opcionales / Automáticos)
            st.divider()
            check_venta = st.checkbox("MARCADO PARA LA VENTA", value=True)
            check_corregido = st.checkbox("CORREGIDO", value=True)
            check_foto = st.checkbox("FOTO", value=True)
            # Botón de envío
            submitted = st.form_submit_button("➕ Agregar al Reporte", type="primary")
            
            if submitted:
                # Lógica automática para 'No Coincide'
                diferencia = st_depo != st_sis
                
                nuevo_item = {
                    "id": id_art,
                    "nombre": nom_art,
                    "depo": int(st_depo),
                    "sistema": int(st_sis),
                    "no_coincide": diferencia,
                    "corregido": check_corregido,
                    "venta": check_venta,
                    "foto": check_foto,
                    "hora": pd.Timestamp.now().strftime("%H:%M")
                }
                st.session_state.stock_report_log.append(nuevo_item)
                st.toast(f"Artículo '{nom_art}' agregado.")

        # Botón para limpiar si te equivocas
        if st.button("🗑️ Borrar último ingreso"):
            if st.session_state.stock_report_log:
                st.session_state.stock_report_log.pop()
                st.rerun()

    with col_output:
        st.subheader("📋 Vista Previa del Reporte")
        
        # Generación del Texto Final
        fecha_hoy = pd.Timestamp.now().strftime("%d-%m-%y")
        texto_final = f"CONTROL DE STOCK {fecha_hoy}\n"
        
        if not st.session_state.stock_report_log:
            st.info("Agrega artículos en el formulario de la izquierda para generar el texto.")
        else:
            # Iterar sobre la lista guardada
            for i, item in enumerate(st.session_state.stock_report_log, 1):
                texto_final += f"\n{i}) \n"
                texto_final += f"Id:\n{item['id']}\n"
                texto_final += f"Nombre del Articulo:\n{item['nombre']}\n"
                texto_final += f"STOCK REAL : {item['depo']}\n"
                texto_final += f"STOCK SISTEMA : {item['sistema']}\n"
                
                if item['no_coincide']:
                    texto_final += "❌ NO COINCIDE \n"
                else:
                    texto_final += "✅ SI COINCIDE \n"
                if item['corregido']:
                    texto_final += "✅ CORREGIDO\n"
                else:
                    texto_final += "❌ NO CORREGIDO \n"
                if item['venta']:
                    texto_final += "✅MARCADO PARA LA VENTA\n"
                else:
                    texto_final += "❌NO SE MARCO PARA LA VENTA \n"
                if item["foto"]:
                    texto_final += "✅CON FOTO \n"
                else:
                    texto_final +="❌SIN FOTO \n"
            # Mostrar el texto para copiar
            st.text_area("Copia este texto:", value=texto_final, height=600)
            
            # Botón para limpiar todo al terminar el día
            if st.button("🔄 Reiniciar Reporte Diario"):
                st.session_state.stock_report_log = []
                st.rerun()
st.caption("Modo Offline Seguro - v49")




