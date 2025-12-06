import streamlit as st
import pandas as pd
import re
from pypdf import PdfReader
from twilio.rest import Client
import logging
import uuid

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Repositor Saphirus", page_icon="✨", layout="centered")
st.title("✨ Repositor Saphirus 27.0")

# --- ESTILOS CSS OPTIMIZADOS PARA MÓVIL ---
st.markdown("""
<style>
    /* --- Estilos Generales de Botones --- */
    .stButton button {
        width: 100%;
        border-radius: 5px;
        border: 1px solid #e0e0e0; /* Borde sutil */
        padding: 4px 0px !important; /* Botones más delgados */
        font-size: 16px !important; /* Emoji legible pero no gigante */
        line-height: 1 !important;
        height: auto !important;
        min-height: unset !important;
        margin-top: 0px !important; /* Eliminar márgenes extra */
    }

    /* --- Alineación de Columnas --- */
    /* Centrar verticalmente el contenido de todas las columnas */
    div[data-testid="column"] {
        display: flex;
        align-items: center;
        padding: 0 2px !important; /* Reducir espacio entre columnas */
    }

    /* La primera columna (texto del producto) alineada a la izquierda */
    div[data-testid="column"]:first-child {
        justify-content: flex-start;
    }
    
    /* Las columnas de botones centradas horizontalmente */
    div[data-testid="column"]:not(:first-child) {
        justify-content: center;
    }

    /* --- OPTIMIZACIÓN PARA MÓVILES (CRÍTICO) --- */
    @media (max-width: 640px) {
        /* Fuerza a las columnas a mantenerse en una sola fila */
        div[data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap !important;
        }
        
        /* Ajustar el texto del producto para que ocupe menos espacio vertical */
        div[data-testid="column"]:first-child p {
            margin: 0 !important;
            font-size: 14px !important;
            line-height: 1.2 !important;
        }
        
        /* Reducir aún más el padding de los botones en móvil */
        .stButton button {
            padding: 2px 0px !important;
            font-size: 14px !important;
        }
    }

    /* --- Otros Estilos --- */
    .element-container {
        transition: all 0.3s ease;
    }
    /* Reducir el espacio del divisor */
    hr {
        margin: 0.5em 0 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- GESTIÓN DE ESTADO ---
if 'audit_data' not in st.session_state:
    st.session_state.audit_data = [] 
if 'audit_started' not in st.session_state:
    st.session_state.audit_started = False

# --- CREDENCIALES ---
def cargar_credenciales():
    with st.sidebar:
        st.header("🔐 Twilio")
        try:
            credentials = {
                'SID': st.secrets["TWILIO_SID"],
                'TOK': st.secrets["TWILIO_TOKEN"],
                'FROM': st.secrets["TWILIO_FROM"],
                'TO': st.secrets["TWILIO_TO"]
            }
            return credentials
        except Exception:
            return {
                'SID': st.text_input("SID", type="password"),
                'TOK': st.text_input("Token", type="password"),
                'FROM': st.text_input("From"),
                'TO': st.text_input("To")
            }

credentials = cargar_credenciales()

# --- PATRONES DE CATEGORIZACIÓN ---
CATEGORIAS = {
    'touch_dispositivo': {'pattern': lambda p: "DISPOSITIVO" in p and "TOUCH" in p, 'emoji': "🖱️", 'nombre': "Dispositivos Touch"},
    'touch_repuesto': {'pattern': lambda p: ("REPUESTO" in p and "TOUCH" in p) or "GR/13" in p, 'emoji': "🔄", 'nombre': "Repuestos de Touch"},
    'perfume_mini': {'pattern': lambda p: "MINI MILANO" in p, 'emoji': "🧴", 'nombre': "Perfume Mini Milano"},
    'perfume_parfum': {'pattern': lambda p: "PARFUM" in p, 'emoji': "🧴", 'nombre': "Parfum / Perfumes"},
    'shiny_general': {'pattern': lambda p: "SHINY" in p and ("LIMPIAVIDRIOS" in p or "DESENGRASANTE" in p or "LUSTRAMUEBLE" in p), 'emoji': "✨", 'nombre': "Shiny General"},
    'ambar_aerosol': {'pattern': lambda p: "AMBAR" in p and "AEROSOL" in p, 'emoji': "🔸", 'nombre': "Aerosoles Ambar"},
    'ambar_textil': {'pattern': lambda p: "AMBAR" in p and ("TEXTIL" in p or "150 ML" in p), 'emoji': "🔸", 'nombre': "Textiles Ambar"},
    'ambar_sahumerio': {'pattern': lambda p: "AMBAR" in p and "SAHUMERIO" in p, 'emoji': "🔸", 'nombre': "Sahumerios Ambar"},
    'ambar_varios': {'pattern': lambda p: "AMBAR" in p, 'emoji': "🔸", 'nombre': "Línea Ambar Varios"},
    'home_spray': {'pattern': lambda p: "HOME SPRAY" in p or "500 ML" in p or "500ML" in p, 'emoji': "🏠", 'nombre': "Home Spray"},
    'aparatos': {'pattern': lambda p: "APARATO" in p or "HORNILLO" in p, 'emoji': "⚙️", 'nombre': "Aparatos"},
    'premium': {'pattern': lambda p: "PREMIUM" in p, 'emoji': "💎", 'nombre': "Difusores Premium"},
    'sahumerio_hierbas': {'pattern': lambda p: "SAHUMERIO" in p and "HIERBAS" in p, 'emoji': "🌿", 'nombre': "Sahumerios Hierbas"},
    'sahumerio_himalaya': {'pattern': lambda p: "SAHUMERIO" in p and "HIMALAYA" in p, 'emoji': "🏔️", 'nombre': "Sahumerios Himalaya"},
    'sahumerio_varios': {'pattern': lambda p: "SAHUMERIO" in p, 'emoji': "🧘", 'nombre': "Sahumerios Varios"},
    'auto_caritas': {'pattern': lambda p: "CARITAS" in p, 'emoji': "😎", 'nombre': "Autos - Caritas"},
    'auto_ruta': {'pattern': lambda p: "RUTA" in p or "RUTA 66" in p, 'emoji': "🛣️", 'nombre': "Autos - Ruta 66"},
    'auto_varios': {'pattern': lambda p: "AUTO" in p, 'emoji': "🚗", 'nombre': "Autos - Varios"},
    'textil_mini': {'pattern': lambda p: "TEXTIL" in p and "MINI" in p, 'emoji': "🤏", 'nombre': "Textiles Mini"},
    'textil': {'pattern': lambda p: "TEXTIL" in p, 'emoji': "👕", 'nombre': "Textiles Saphirus"},
    'aerosol': {'pattern': lambda p: "AEROSOL" in p, 'emoji': "💨", 'nombre': "Aerosoles Saphirus"},
    'difusor': {'pattern': lambda p: "DIFUSOR" in p or "VARILLA" in p, 'emoji': "🎍", 'nombre': "Difusores"},
    'vela': {'pattern': lambda p: "VELA" in p, 'emoji': "🕯️", 'nombre': "Velas"},
    'aceite': {'pattern': lambda p: "ACEITE" in p, 'emoji': "💧", 'nombre': "Aceites"},
    'antihumedad': {'pattern': lambda p: "ANTIHUMEDAD" in p, 'emoji': "💧", 'nombre': "Antihumedad"},
    'limpiador': {'pattern': lambda p: "LIMPIADOR" in p, 'emoji': "🧼", 'nombre': "Limpiadores Multisuperficies"},
}

def detectar_categoria(producto):
    p = producto.upper()
    for key, config in CATEGORIAS.items():
        if config['pattern'](p):
            return f"{config['emoji']} {config['nombre']}"
    return "📦 Varios"

# --- REGLAS DE LIMPIEZA ---
REGLAS_LIMPIEZA = {
    'general': [(r"\s*[-–]?\s*SAPHIRUS.*$", ""), (r"\s*[-–]?\s*AMBAR.*$", ""), (r"^[-–]\s*", ""), (r"\s*[-–]$", "")],
    'shiny_general': [(r"^LIMPIAVIDRIOS.*", "LIMPIAVIDRIOS"), (r"^DESENGRASANTE.*", "DESENGRASANTE"), (r"^LUSTRAMUEBLES?.*", "LUSTRAMUEBLE")],
    'limpiadores': [(r"^LIMPIADOR\s+LIQUIDO\s+MULTISUPERFICIES\s*250\s*ML\s*[-–]?\s*SHINY\s*[-–]?\s*", ""), (r"\s*\d{4,6}$", "")],
    'premium': [(r"^DIFUSOR PREMIUM\s*[-–]?\s*", ""), (r"\s*[-–]?\s*AROMATICO.*$", "")],
    'home_spray': [(r"^HOME SPRAY\s*[-–]?\s*", ""), (r"\s*[-–]?\s*AROMATIZANTE\s+TEXTIL.*$", ""), (r"\s*500\s*ML.*$", "")],
    'repuesto_touch': [(r"(\d+\s*)?GR.*?CM3\s*[-–]?\s*", ""), (r"^REPUESTO TOUCH\s*[-–]?\s*", "")],
    'aceites': [(r"^ACEITE\s+ESENCIAL\s*[-–]?\s*", "")],
    'antihumedad': [(r"ANTI\s+HUMEDAD", ""), (r"SAPHIRUS", ""), (r"[-–]\s*\d+$", "")],
    'perfumes': [(r"PERFUME MINI MILANO\s*[-–]?\s*", ""), (r"SAPHIRUS PARFUM\s*", "")],
    'aparatos': [(r".*LATERAL.*", "LATERAL"), (r".*FRONTAL.*", "FRONTAL"), (r".*DIGITAL.*", "DIGITAL"), (r".*NEGRO.*", "NEGRO"), (r".*GRIS.*", "GRIS"), (r".*ROSA.*", "ROSA"), (r".*BEIGE.*", "BEIGE"), (r".*BLANCO.*", "BLANCO"), (r".*HORNILLO.*", "HORNILLO CHICO"), (r"APARATO ANALOGICO DECO", "ANALOGICO")],
    'sahumerio_ambar': [(r"^SAHUMERIO\s*[-–]?\s*AMBAR\s*[-–]?\s*", "")],
    'sahumerio_tipo': [(r"^SAHUMERIO HIERBAS\s*[-–]?\s*", ""), (r"^SAHUMERIO HIMALAYA\s*[-–]?\s*", ""), (r"^SAHUMERIO\s*[-–]?\s*", "")],
    'dispositivo_touch': [(r"^DISPOSITIVO TOUCH\s*(\+)?\s*", ""), (r"\s*\d{6,}$", "")],
    'textil_mini': [(r"^AROMATIZADOR TEXTIL MINI 60 ML\s*[-–]?\s*", "")],
    'textil': [(r"^AROMATIZADOR TEXTIL 150 ML AMBAR\s*[-–]?\s*", ""), (r"^AROMATIZADOR TEXTIL 250 ML\s*[-–]?\s*", ""), (r"^AROMATIZADOR TEXTIL MINI 60 ML\s*[-–]?\s*", ""), (r"^AROMATIZADOR TEXTIL\s*[-–]?\s*", "")],
    'autos': [(r"CARITAS EMOGI X 2", ""), (r"RUTA 66", ""), (r"AROMATIZANTE AUTO", ""), (r"\s*X\s*2.*$", "")],
    'velas': [(r"VELAS SAPHIRUS", "VELAS")],
    'aerosol': [(r"^AEROSOL\s*[-–]?\s*", "")],
    'difusor': [(r"^DIFUSOR AROMATICO\s*[-–]?\s*", ""), (r"^DIFUSOR\s*[-–]?\s*", ""), (r"\s*[-–]?\s*VARILLA.*$", "")],
}

def aplicar_reglas(texto, reglas):
    resultado = texto.upper()
    for patron, reemplazo in reglas:
        resultado = re.sub(patron, reemplazo, resultado, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", resultado).strip()

def limpiar_producto_por_categoria(row):
    cat = row["Categoria"]
    nom = row["Producto"]
    mapeo = {
        "Shiny General": 'shiny_general', "Limpiadores": 'limpiadores', "Difusores Premium": 'premium', "Aceites": 'aceites', 
        "Sahumerios Ambar": 'sahumerio_ambar', "Repuestos de Touch": 'repuesto_touch', "Dispositivos Touch": 'dispositivo_touch', 
        "Antihumedad": 'antihumedad', "Perfume": 'perfumes', "Parfum": 'perfumes', "Aparatos": 'aparatos', 
        "Sahumerios": 'sahumerio_tipo', "Home Spray": 'home_spray', "Textiles Mini": 'textil_mini', "Textiles": 'textil',
        "Autos": 'autos', "Aerosoles": 'aerosol', "Difusores": 'difusor', "Velas": 'velas',
    }
    for key, regla in mapeo.items():
        if key in cat:
            if regla == 'shiny_general': return aplicar_reglas(nom, REGLAS_LIMPIEZA['shiny_general'])
            if regla == 'aparatos':
                 res = aplicar_reglas(nom, REGLAS_LIMPIEZA['aparatos'])
                 if res == nom: res = res.replace("APARATO ANALOGICO DECO", "ANALOGICO")
                 return res
            resultado = aplicar_reglas(nom, REGLAS_LIMPIEZA.get(regla, []))
            resultado = aplicar_reglas(resultado, REGLAS_LIMPIEZA['general'])
            if "Touch" in cat and "REPUESTO NEGRO" in resultado: resultado = resultado.replace("REPUESTO NEGRO", "NEGRO + REPUESTO")
            return resultado if len(resultado) >= 2 else nom
    return aplicar_reglas(nom, REGLAS_LIMPIEZA['general'])

# --- PROCESAMIENTO PDF ---
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

def procesar_pdf(archivo):
    try:
        texto = extraer_texto_pdf(archivo)
        if not texto: return None
        datos = parsear_datos(texto)
        if not datos: return None
        df = pd.DataFrame(datos)
        return limpiar_dataframe(df)
    except Exception as e:
        logger.error(f"Error en procesar_pdf: {e}")
        return None

# --- FUNCIONES AUDITORIA ---
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
                    "categoria": categoria_actual,
                    "producto": prod,
                    "cantidad": cant,
                    "status": None 
                })
            except: continue
    return items

def actualizar_estado(item_id, nuevo_estado):
    for item in st.session_state.audit_data:
        if item['id'] == item_id:
            item['status'] = nuevo_estado
            break

def actualizar_categoria_completa(categoria, nuevo_estado):
    for item in st.session_state.audit_data:
        if item['categoria'] == categoria and item['status'] is None:
            item['status'] = nuevo_estado

def generar_listas_finales(data):
    pedido_web = {} 
    reponido = {}
    pendiente = {}
    for item in data:
        cat = item['categoria']
        linea = f"{item['cantidad']} x {item['producto']}"
        if item['status'] == 'pedido':
            if cat not in pedido_web: pedido_web[cat] = []
            pedido_web[cat].append(linea)
        elif item['status'] == 'repuesto':
            if cat not in reponido: reponido[cat] = []
            reponido[cat].append(linea)
        elif item['status'] == 'pendiente':
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
        st.error("Faltan credenciales")
        return False
    try:
        Client(creds['SID'], creds['TOK']).messages.create(body=mensaje, from_=creds['FROM'], to=creds['TO'])
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

# --- UI PRINCIPAL ---
tab1, tab2, tab3 = st.tabs(["📄 Procesar PDF", "➕ Sumar Listas", "✅ Auditoría en Vivo"])

# TAB 1: PDF
with tab1:
    archivo = st.file_uploader("Subir PDF", type="pdf")
    if archivo:
        df_res = procesar_pdf(archivo)
        if df_res is not None and not df_res.empty:
            msg = generar_mensaje_df(df_res)
            st.code(msg, language='text')
            if len(msg) > 1500: st.warning("⚠️ Mensaje muy largo para WhatsApp directo.")
            else:
                if st.button("Enviar PDF a WhatsApp"):
                    if enviar_whatsapp(msg, credentials): st.success("Enviado")
        else: st.error("No se pudieron extraer datos.")

# TAB 2: SUMA
with tab2:
    st.info("Pega dos listas para sumarlas.")
    c1, c2 = st.columns(2)
    l1 = c1.text_area("Lista 1")
    l2 = c2.text_area("Lista 2")
    if st.button("Unificar"):
        def parse_simple(txt):
            d = {}
            cat = "General"
            for line in txt.split('\n'):
                line = line.strip()
                if "==" in line: cat = line.replace("==", "").strip()
                elif " x " in line:
                    p = line.split(" x ", 1)
                    try:
                        c = float(p[0])
                        prod = p[1]
                        if cat not in d: d[cat] = {}
                        d[cat][prod] = d[cat].get(prod, 0) + c
                    except: pass
            return d
        d1 = parse_simple(l1)
        d2 = parse_simple(l2)
        total = d1.copy()
        for c, prods in d2.items():
            if c not in total: total[c] = {}
            for p, qty in prods.items():
                total[c][p] = total[c].get(p, 0) + qty
        txt_fin = "📋 *LISTA SUMADA*\n"
        for c in sorted(total.keys()):
            txt_fin += f"\n== {c} ==\n"
            for p in sorted(total[c].keys()):
                q = total[c][p]
                q_fmt = int(q) if q.is_integer() else q
                txt_fin += f"{q_fmt} x {p}\n"
        st.code(txt_fin, language='text')

# TAB 3: AUDITORÍA
with tab3:
    st.header("🕵️ Auditoría de Reposición")
    
    if not st.session_state.audit_started:
        input_audit = st.text_area("Pega la lista generada aquí:", height=200, placeholder="== CATEGORIA ==\n1 x PRODUCTO")
        if st.button("🚀 Comenzar Auditoría", type="primary"):
            if input_audit:
                st.session_state.audit_data = preparar_datos_auditoria(input_audit)
                st.session_state.audit_started = True
                st.rerun()
            else: st.warning("Pega una lista primero")
    else:
        if st.button("🔄 Reiniciar Auditoría", type="secondary"):
            st.session_state.audit_started = False
            st.session_state.audit_data = []
            st.rerun()
            
        completed_count = len([x for x in st.session_state.audit_data if x['status']])
        total_items = len(st.session_state.audit_data)
        if total_items > 0: st.progress(completed_count / total_items)
        
        st.markdown("---")
        
        all_cats = sorted(list(set([x['categoria'] for x in st.session_state.audit_data])))
        
        cats_pendientes = []
        for c in all_cats:
            if any(x['categoria'] == c and x['status'] is None for x in st.session_state.audit_data):
                cats_pendientes.append(c)

        if not cats_pendientes and total_items > 0:
             st.success("🎉 ¡Auditoría Completada! Revisa los resultados abajo.")

        for cat in cats_pendientes:
            # Desplegables cerrados por defecto
            with st.expander(f"📂 {cat}", expanded=False):
                # Barra de acciones masivas con estilo más compacto
                st.markdown(f"<div style='background-color:#f9f9f9; padding: 5px 0; border-radius:5px; margin-bottom:5px;'>", unsafe_allow_html=True)
                cb_info, cb1, cb2, cb3 = st.columns([3, 1, 1, 1])
                with cb_info:
                    st.markdown(f"<small style='color:#666;'>Acciones masivas para <b>{cat}</b>:</small>", unsafe_allow_html=True)
                with cb1:
                    if st.button("📦📉", key=f"all_ped_{cat}", help="Marcar TODOS como Sin Stock"):
                        actualizar_categoria_completa(cat, 'pedido')
                        st.rerun()
                with cb2:
                    if st.button("✅", key=f"all_rep_{cat}", help="Marcar TODOS como Repuestos"):
                        actualizar_categoria_completa(cat, 'repuesto')
                        st.rerun()
                with cb3:
                    if st.button("❌", key=f"all_pen_{cat}", help="Marcar TODOS como Pendientes"):
                        actualizar_categoria_completa(cat, 'pendiente')
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
                
                items_visibles = [x for x in st.session_state.audit_data if x['categoria'] == cat and x['status'] is None]
                
                for item in items_visibles:
                    # Proporción de columnas ajustada para dar más espacio al texto
                    c1, c2, c3, c4 = st.columns([5, 1, 1, 1])
                    with c1:
                        # Usamos markdown para un control más preciso del estilo del texto
                        st.markdown(f"<span style='font-weight:500; font-size:15px;'>{item['cantidad']} x {item['producto']}</span>", unsafe_allow_html=True)
                    with c2:
                        if st.button("📦", key=f"p_{item['id']}", help="Sin Stock"):
                            actualizar_estado(item['id'], 'pedido')
                            st.rerun()
                    with c3:
                        if st.button("✅", key=f"r_{item['id']}", help="Repuesto"):
                            actualizar_estado(item['id'], 'repuesto')
                            st.rerun()
                    with c4:
                        if st.button("❌", key=f"n_{item['id']}", help="No necesario"):
                            actualizar_estado(item['id'], 'pendiente')
                            st.rerun()
                    st.divider()

        st.header("📊 Listas Finales")
        lp, lr, lpen = generar_listas_finales(st.session_state.audit_data)
        c_res1, c_res2, c_res3 = st.columns(3)
        with c_res1: 
            st.subheader("📉 Pedido")
            st.code(formatear_lista_texto(lp, "Pedido Web"), language='text')
        with c_res2: 
            st.subheader("✅ Repuesto")
            st.code(formatear_lista_texto(lr, "Repuesto Hoy"), language='text')
        with c_res3: 
            st.subheader("❌ Pendiente")
            st.code(formatear_lista_texto(lpen, "Pendientes"), language='text')

st.markdown("---")
st.caption("Repositor Saphirus 27.0")
