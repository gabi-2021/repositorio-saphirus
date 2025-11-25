import streamlit as st
import pandas as pd
import re
import requests
from pypdf import PdfReader
from twilio.rest import Client
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Repositor Saphirus", page_icon="✨", layout="centered")
st.title("✨ Repositor Saphirus 20.0")

# --- CREDENCIALES ---
def cargar_credenciales():
    """Carga credenciales desde secrets o inputs del usuario"""
    with st.sidebar:
        st.header("🔐 Twilio")
        try:
            credentials = {
                'SID': st.secrets["TWILIO_SID"],
                'TOK': st.secrets["TWILIO_TOKEN"],
                'FROM': st.secrets["TWILIO_FROM"],
                'TO': st.secrets["TWILIO_TO"]
            }
            st.success("Credenciales OK 🔒")
            return credentials
        except Exception as e:
            st.warning("Faltan secrets - Ingresa credenciales manualmente")
            return {
                'SID': st.text_input("SID", type="password"),
                'TOK': st.text_input("Token", type="password"),
                'FROM': st.text_input("From"),
                'TO': st.text_input("To")
            }

credentials = cargar_credenciales()

# --- PATRONES DE CATEGORIZACIÓN ---
# EL ORDEN IMPORTA: Las reglas más específicas deben ir primero.
CATEGORIAS = {
    # Touch
    'touch_dispositivo': {'pattern': lambda p: "DISPOSITIVO" in p and "TOUCH" in p, 'emoji': "🖱️", 'nombre': "Dispositivos Touch"},
    'touch_repuesto': {'pattern': lambda p: ("REPUESTO" in p and "TOUCH" in p) or "GR/13" in p, 'emoji': "🔄", 'nombre': "Repuestos de Touch"},
    
    # Perfumería
    'perfume_mini': {'pattern': lambda p: "MINI MILANO" in p, 'emoji': "🧴", 'nombre': "Perfume Mini Milano"},
    'perfume_parfum': {'pattern': lambda p: "PARFUM" in p, 'emoji': "🧴", 'nombre': "Parfum / Perfumes"},
    
    # Shiny General (NUEVO - Prioridad alta para atrapar limpiavidrios de 500ml antes que Home Spray)
    'shiny_general': {
        'pattern': lambda p: "SHINY" in p and ("LIMPIAVIDRIOS" in p or "DESENGRASANTE" in p or "LUSTRAMUEBLE" in p), 
        'emoji': "✨", 
        'nombre': "Shiny General"
    },

    # Ambar
    'ambar_aerosol': {'pattern': lambda p: "AMBAR" in p and "AEROSOL" in p, 'emoji': "🔸", 'nombre': "Aerosoles Ambar"},
    'ambar_textil': {'pattern': lambda p: "AMBAR" in p and ("TEXTIL" in p or "150 ML" in p), 'emoji': "🔸", 'nombre': "Textiles Ambar"},
    'ambar_sahumerio': {'pattern': lambda p: "AMBAR" in p and "SAHUMERIO" in p, 'emoji': "🔸", 'nombre': "Sahumerios Ambar"},
    'ambar_varios': {'pattern': lambda p: "AMBAR" in p, 'emoji': "🔸", 'nombre': "Línea Ambar Varios"},
    
    # Home Spray
    'home_spray': {'pattern': lambda p: "HOME SPRAY" in p or "500 ML" in p or "500ML" in p, 'emoji': "🏠", 'nombre': "Home Spray"},
    
    # Aparatos
    'aparatos': {'pattern': lambda p: "APARATO" in p or "HORNILLO" in p, 'emoji': "⚙️", 'nombre': "Aparatos"},
    
    # Premium
    'premium': {'pattern': lambda p: "PREMIUM" in p, 'emoji': "💎", 'nombre': "Difusores Premium"},
    
    # Sahumerios
    'sahumerio_hierbas': {'pattern': lambda p: "SAHUMERIO" in p and "HIERBAS" in p, 'emoji': "🌿", 'nombre': "Sahumerios Hierbas"},
    'sahumerio_himalaya': {'pattern': lambda p: "SAHUMERIO" in p and "HIMALAYA" in p, 'emoji': "🏔️", 'nombre': "Sahumerios Himalaya"},
    'sahumerio_varios': {'pattern': lambda p: "SAHUMERIO" in p, 'emoji': "🧘", 'nombre': "Sahumerios Varios"},
    
    # Autos
    'auto_caritas': {'pattern': lambda p: "CARITAS" in p, 'emoji': "😎", 'nombre': "Autos - Caritas"},
    'auto_ruta': {'pattern': lambda p: "RUTA" in p or "RUTA 66" in p, 'emoji': "🛣️", 'nombre': "Autos - Ruta 66"},
    'auto_varios': {'pattern': lambda p: "AUTO" in p, 'emoji': "🚗", 'nombre': "Autos - Varios"},
    
    # Estándar (Nombres actualizados)
    'textil': {'pattern': lambda p: "TEXTIL" in p, 'emoji': "👕", 'nombre': "Textiles Saphirus"},
    'aerosol': {'pattern': lambda p: "AEROSOL" in p, 'emoji': "💨", 'nombre': "Aerosoles Saphirus"},
    'difusor': {'pattern': lambda p: "DIFUSOR" in p or "VARILLA" in p, 'emoji': "🎍", 'nombre': "Difusores"},
    'vela': {'pattern': lambda p: "VELA" in p, 'emoji': "🕯️", 'nombre': "Velas"},
    'aceite': {'pattern': lambda p: "ACEITE" in p, 'emoji': "💧", 'nombre': "Aceites"},
    'antihumedad': {'pattern': lambda p: "ANTIHUMEDAD" in p, 'emoji': "💧", 'nombre': "Antihumedad"},
    'limpiador': {'pattern': lambda p: "LIMPIADOR" in p, 'emoji': "🧼", 'nombre': "Limpiadores Multisuperficies"},
}

def detectar_categoria(producto):
    """Detecta la categoría del producto usando patrones configurables"""
    p = producto.upper()
    for key, config in CATEGORIAS.items():
        if config['pattern'](p):
            return f"{config['emoji']} {config['nombre']}"
    return "📦 Varios"

# --- REGLAS DE LIMPIEZA ---
REGLAS_LIMPIEZA = {
    'general': [
        (r"\s*[-–]?\s*SAPHIRUS.*$", ""),
        (r"\s*[-–]?\s*AMBAR.*$", ""),
        (r"^[-–]\s*", ""),
        (r"\s*[-–]$", ""),
    ],
    # Nueva regla Shiny General (Forzado de nombres)
    'shiny_general': [
        (r"^LIMPIAVIDRIOS.*", "LIMPIAVIDRIOS"), 
        (r"^DESENGRASANTE.*", "DESENGRASANTE"),
        (r"^LUSTRAMUEBLES?.*", "LUSTRAMUEBLE"), # Atrapa singular y plural
    ],
    'limpiadores': [
        (r"^LIMPIADOR\s+LIQUIDO\s+MULTISUPERFICIES\s*250\s*ML\s*[-–]?\s*SHINY\s*[-–]?\s*", ""),
        (r"\s*\d{4,6}$", ""),
    ],
    'premium': [
        (r"^DIFUSOR PREMIUM\s*[-–]?\s*", ""),
        (r"\s*[-–]?\s*AROMATICO.*$", ""), # Borra " - AROMATICO" del final
    ],
    'home_spray': [
        (r"^HOME SPRAY\s*[-–]?\s*", ""),
        # Regla agresiva para Clementina: busca guion, espacios opcionales, AROMATIZANTE TEXTIL y todo lo que siga
        (r"\s*[-–]\s*AROMATIZANTE TEXTIL.*$", ""), 
        (r"\s*AROMATIZANTE TEXTIL.*$", ""), # Fallback sin guion
        (r"\s*500\s*ML.*$", ""),
    ],
    'repuesto_touch': [
        # Regla flexible: Borra "9 GR...CM3" aunque tenga espacios raros como "9 GR /13CM3"
        (r"\d+\s*GR.*?CM3\s*[-–]?\s*", ""), 
        (r"^REPUESTO TOUCH\s*[-–]?\s*", ""),
    ],
    'aceites': [(r"^ACEITE\s+ESENCIAL\s*[-–]?\s*", "")],
    'antihumedad': [
        (r"ANTI\s+HUMEDAD", ""),
        (r"SAPHIRUS", ""),
        (r"[-–]\s*\d+$", ""),
    ],
    'perfumes': [
        (r"PERFUME MINI MILANO\s*[-–]?\s*", ""),
        (r"SAPHIRUS PARFUM\s*", ""),
    ],
    'aparatos': [
        # Reglas de Prioridad: Detectan la palabra clave y reemplazan TODO el nombre por ella
        (r".*LATERAL.*", "LATERAL"),
        (r".*FRONTAL.*", "FRONTAL"),
        (r".*DIGITAL.*", "DIGITAL"),
        
        # Colores de los Aparatos Deco (Analogicos)
        (r".*NEGRO.*", "NEGRO"),
        (r".*GRIS.*", "GRIS"),
        (r".*ROSA.*", "ROSA"),
        (r".*BEIGE.*", "BEIGE"),
        (r".*BLANCO.*", "BLANCO"),
        
        # Unificar Hornillos
        (r".*HORNILLO.*", "HORNILLO CHICO"),
        
        # Limpieza final por si queda algo genérico (fallback)
        (r"APARATO ANALOGICO DECO", "ANALOGICO"), 
    ],
    'sahumerio_ambar': [(r"^SAHUMERIO\s*[-–]?\s*AMBAR\s*[-–]?\s*", "")],
    'sahumerio_tipo': [
        (r"^SAHUMERIO HIERBAS\s*[-–]?\s*", ""),
        (r"^SAHUMERIO HIMALAYA\s*[-–]?\s*", ""),
        (r"^SAHUMERIO\s*[-–]?\s*", ""),
    ],
    'dispositivo_touch': [
        (r"^DISPOSITIVO TOUCH\s*(\+)?\s*", ""),
        (r"\s*\d{6,}$", ""),
    ],
    'textil': [
        (r"^AROMATIZADOR TEXTIL 150 ML AMBAR\s*[-–]?\s*", ""),
        (r"^AROMATIZADOR TEXTIL 250 ML\s*[-–]?\s*", ""),
        (r"^AROMATIZADOR TEXTIL MINI 60 ML\s*[-–]?\s*", ""),
        (r"^AROMATIZADOR TEXTIL\s*[-–]?\s*", ""),
    ],
    'autos': [
        (r"CARITAS EMOGI X 2", ""),
        (r"RUTA 66", ""),
        (r"AROMATIZANTE AUTO", ""),
        (r"\s*X\s*2.*$", ""),
    ],
    'velas': [(r"VELAS SAPHIRUS", "VELAS")],
    'aerosol': [(r"^AEROSOL\s*[-–]?\s*", "")],
    'difusor': [
        (r"^DIFUSOR AROMATICO\s*[-–]?\s*", ""),
        (r"^DIFUSOR\s*[-–]?\s*", ""),
        (r"\s*[-–]?\s*VARILLA.*$", ""),
    ],
}

def aplicar_reglas(texto, reglas):
    """Aplica una lista de reglas de regex al texto"""
    resultado = texto.upper()
    for patron, reemplazo in reglas:
        resultado = re.sub(patron, reemplazo, resultado, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", resultado).strip()

def limpiar_producto_por_categoria(row):
    """Limpia el nombre del producto según su categoría"""
    cat = row["Categoria"]
    nom = row["Producto"]
    
    # Mapeo de categorías a reglas
    mapeo = {
        "Shiny General": 'shiny_general',
        "Limpiadores": 'limpiadores',
        "Difusores Premium": 'premium',
        "Aceites": 'aceites',
        "Sahumerios Ambar": 'sahumerio_ambar',
        "Repuestos de Touch": 'repuesto_touch',
        "Dispositivos Touch": 'dispositivo_touch',
        "Antihumedad": 'antihumedad',
        "Perfume": 'perfumes',
        "Parfum": 'perfumes',
        "Aparatos": 'aparatos',
        "Sahumerios": 'sahumerio_tipo',
        "Home Spray": 'home_spray',
        "Textiles": 'textil',
        "Autos": 'autos',
        "Aerosoles": 'aerosol',
        "Difusores": 'difusor',
        "Velas": 'velas',
    }
    
    # Buscar regla específica
    for key, regla in mapeo.items():
        if key in cat:
            # Casos especiales Shiny (Reemplazo total)
            if regla == 'shiny_general':
                return aplicar_reglas(nom, REGLAS_LIMPIEZA['shiny_general'])

            resultado = aplicar_reglas(nom, REGLAS_LIMPIEZA.get(regla, []))
            resultado = aplicar_reglas(resultado, REGLAS_LIMPIEZA['general'])
            
            # Casos especiales Touch
            if "Touch" in cat and "REPUESTO NEGRO" in resultado:
                resultado = resultado.replace("REPUESTO NEGRO", "NEGRO + REPUESTO")
            
            return resultado if len(resultado) >= 2 else nom
    
    return aplicar_reglas(nom, REGLAS_LIMPIEZA['general'])

# --- PROCESAMIENTO DE PDF ---
def extraer_texto_pdf(archivo):
    try:
        reader = PdfReader(archivo)
        texto_completo = ""
        for i, page in enumerate(reader.pages):
            try:
                texto_completo += page.extract_text() + "\n"
            except Exception:
                continue
        return texto_completo.replace("\n", " ")
    except Exception as e:
        logger.error(f"Error leyendo PDF: {e}")
        return None

def parsear_datos(texto_limpio):
    datos = []
    patron_csv = r'"\s*(\d{8})\s*"\s*,\s*"\s*([-0-9,]+)\s+([^"]+)"'
    matches = re.findall(patron_csv, texto_limpio)
    if matches:
        for m in matches:
            datos.append({"ID": m[0], "Cantidad": m[1], "Producto": m[2]})
    else:
        patron_libre = r'(\d{8})\s+([-0-9]+,\d{2})\s+(.*?)(?=\s\d{1,3}(?:\.\d{3})*,\d{2})'
        matches = re.findall(patron_libre, texto_limpio)
        for m in matches:
            datos.append({"ID": m[0], "Cantidad": m[1], "Producto": m[2].strip()})
    return datos

def limpiar_dataframe(df):
    df["Cantidad"] = df["Cantidad"].apply(
        lambda x: float(x.replace(",", ".")) if isinstance(x, str) else x
    )
    df["Producto"] = df["Producto"].apply(lambda x: re.sub(r'^\d{8}\s*', '', x.strip()))
    df = df[df["Cantidad"] > 0]
    df["Categoria"] = df["Producto"].apply(detectar_categoria)
    df["Producto"] = df.apply(limpiar_producto_por_categoria, axis=1)
    df_final = df.groupby(["Categoria", "Producto"], as_index=False)["Cantidad"].sum()
    return df_final

def procesar_pdf(archivo):
    try:
        texto_limpio = extraer_texto_pdf(archivo)
        if not texto_limpio: return None
        datos = parsear_datos(texto_limpio)
        if not datos: return None
        df = pd.DataFrame(datos)
        return limpiar_dataframe(df)
    except Exception as e:
        logger.error(f"Error procesando PDF: {e}")
        return None

# --- ENVÍO DE MENSAJES ---
def subir_archivo_robusto(texto_contenido):
    try:
        files = {'reqtype': (None, 'fileupload'), 'userhash': (None, ''), 'fileToUpload': ('reposicion.txt', texto_contenido)}
        response = requests.post('https://catbox.moe/user/api.php', files=files, timeout=30)
        if response.status_code == 200: return response.text.strip()
        return None
    except Exception: return None

def generar_mensaje(df):
    mensaje_txt = "📋 *LISTA DE REPOSICIÓN*\n"
    cats = sorted(df["Categoria"].unique())
    for c in cats:
        mensaje_txt += f"\n== {c.upper()} ==\n"
        sub = df[df["Categoria"] == c].sort_values("Producto")
        for _, r in sub.iterrows():
            cant = int(r['Cantidad']) if r['Cantidad'].is_integer() else r['Cantidad']
            mensaje_txt += f"{cant} x {r['Producto']}\n"
    return mensaje_txt

def enviar_whatsapp(mensaje_txt, credentials):
    if not all([credentials['SID'], credentials['TOK'], credentials['FROM'], credentials['TO']]):
        st.error("❌ Faltan credenciales de Twilio")
        return False
    try:
        client = Client(credentials['SID'], credentials['TOK'])
        mensaje_len = len(mensaje_txt)
        with st.status("📤 Enviando...", expanded=True) as status:
            if mensaje_len < 1500:
                status.write("Enviando mensaje directo...")
                client.messages.create(body=mensaje_txt, from_=credentials['FROM'], to=credentials['TO'])
                return True
            else:
                status.write("📎 Mensaje largo, generando archivo...")
                link = subir_archivo_robusto(mensaje_txt)
                if link:
                    status.write("✅ Archivo generado, enviando link...")
                    client.messages.create(body=f"📄 *Lista Completa*\nDescarga: {link}", from_=credentials['FROM'], to=credentials['TO'])
                    return True
                else:
                    status.write("⚠️ Falló archivo. Enviando por partes...")
                    trozos = [mensaje_txt[i:i+1500] for i in range(0, mensaje_len, 1500)]
                    for idx, trozo in enumerate(trozos, 1):
                        client.messages.create(body=trozo, from_=credentials['FROM'], to=credentials['TO'])
                    return True
    except Exception as e:
        st.error(f"❌ Error al enviar: {str(e)}")
        return False

# --- INTERFAZ PRINCIPAL ---
archivo = st.file_uploader("📄 Subir PDF de Reposición", type="pdf")

if archivo:
    with st.spinner("🔄 Procesando PDF..."):
        df_res = procesar_pdf(archivo)
    
    if df_res is not None and not df_res.empty:
        mensaje_txt = generar_mensaje(df_res)
        total = len(df_res)
        col1, col2 = st.columns(2)
        with col1: st.metric("📦 Total de artículos", total)
        with col2: st.metric("📏 Caracteres", len(mensaje_txt))
        st.success(f"✅ Archivo procesado correctamente")
        with st.expander("👁️ Vista previa del mensaje", expanded=True):
            st.text_area("", mensaje_txt, height=400, label_visibility="collapsed")
        if st.button("🚀 Enviar a WhatsApp", type="primary", use_container_width=True):
            if enviar_whatsapp(mensaje_txt, credentials):
                st.balloons()
                st.success("✅ ¡Mensaje enviado exitosamente!")
    else:
        st.error("❌ No se pudieron extraer datos del PDF. Verifica el formato del archivo.")
else:
    st.info("👆 Sube un archivo PDF para comenzar")

st.markdown("---")
st.caption("Repositor Saphirus 20.0 | Edición Shiny & Premium")

