import streamlit as st
import pandas as pd
import re
import requests
from pypdf import PdfReader
from twilio.rest import Client

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Repositor Saphirus", page_icon="✨", layout="centered")
st.title("✨ Repositor Saphirus 10.0")

# --- CREDENCIALES ---
with st.sidebar:
    st.header("🔐 Twilio")
    try:
        SID = st.secrets["TWILIO_SID"]
        TOK = st.secrets["TWILIO_TOKEN"]
        FROM = st.secrets["TWILIO_FROM"]
        TO = st.secrets["TWILIO_TO"]
        st.success("Credenciales OK 🔒")
    except:
        st.warning("Faltan secrets")
        SID = st.text_input("SID", type="password")
        TOK = st.text_input("Token", type="password")
        FROM = st.text_input("From")
        TO = st.text_input("To")

# --- 1. CATEGORIZACIÓN (ORDEN CRÍTICO) ---
def detectar_categoria(producto):
    p = producto.upper()
    
    # 1. AMBAR (Prioridad máxima para separar tipos)
    if "AMBAR" in p:
        if "AEROSOL" in p: return "🔸 Aerosoles Ambar"
        if "TEXTIL" in p or "150 ML" in p: return "🔸 Textiles Ambar"
        if "SAHUMERIO" in p: return "🔸 Sahumerios Ambar"
        return "🔸 Línea Ambar Varios"

    # 2. HOME SPRAY (Antes que Textil normal para no confundirse)
    if "HOME SPRAY" in p or "500 ML" in p or "500ML" in p: 
        return "🏠 Home Spray"

    # 3. PREMIUM
    if "PREMIUM" in p and ("DIFUSOR" in p or "VARILLA" in p): 
        return "💎 Difusores Premium"

    # 4. RESTO DE CATEGORÍAS
    if "TEXTIL" in p: return "👕 Textiles (250ml)"
    if "AEROSOL" in p: return "💨 Aerosoles"
    if "DIFUSOR" in p or "VARILLA" in p: return "🎍 Difusores"
    if "SAHUMERIO" in p: return "🧘 Sahumerios"
    if "AUTO" in p or "RUTA" in p or "TOUCH" in p or "CARITAS" in p: return "🚗 Autos"
    if "VELA" in p: return "🕯️ Velas"
    if "ACEITE" in p: return "💧 Aceites"
    
    return "📦 Varios"

# --- 2. LIMPIEZA DE NOMBRES ---
def limpiar_nombre_visual(nombre):
    n = nombre
    
    # Lista de Prefijos a borrar (Inicio del nombre)
    prefijos = [
        r"^AROMATIZADOR TEXTIL 150 ML AMBAR\s*[-–]?\s*", # FIX AMBAR 150ML
        r"^DIFUSOR AROMATICO\s*[-–]?\s*",
        r"^DIFUSOR PREMIUM\s*[-–]?\s*",
        r"^DIFUSOR\s*[-–]?\s*",
        r"^AROMATIZADOR TEXTIL 250 ML\s*[-–]?\s*",
        r"^AROMATIZADOR TEXTIL MINI 60 ML\s*[-–]?\s*",
        r"^AROMATIZADOR TEXTIL\s*[-–]?\s*",
        r"^AEROSOL\s*[-–]?\s*",
        r"^HOME SPRAY\s*[-–]?\s*",
        r"^SAHUMERIO AMBAR\s*[-–]?\s*",
        r"^SAHUMERIO\s*[-–]?\s*",
        r"^RUTA 66\s*[-–]?\s*",
        r"^CARITAS EMOGI X 2\s*[-–]?\s*"
        # Nota: Quité la regla de VELAS de aquí para que no borre el nombre entero
    ]
    for pat in prefijos:
        n = re.sub(pat, "", n, flags=re.IGNORECASE)

    # Lista de Sufijos a borrar (Final del nombre)
    sufijos = [
        r"\s*[-–]?\s*AMBAR.*$",             # Borra " - AMBAR" al final (ej: DANIEL AMBAR -> DANIEL)
        r"\s*[-–]?\s*SAPHIRUS.*$",          # Borra " - SAPHIRUS"
        r"\s*[-–]?\s*AROMATIZANTE TEXTIL\s*500\s*ML.*$", # FIX HOME SPRAY SUCIOS
        r"\s*[-–]?\s*AROMATIZANTE TEXTIL.*$",
        r"\s*[-–]?\s*X\s*\d+\s*SAPHIRUS.*$",
        r"\s*[-–]?\s*VARILLA SAPHIRUS.*$",
        r"\s*[-–]?\s*AROMATICO VARILLA.*$"
    ]
    for pat in sufijos:
        n = re.sub(pat, "", n, flags=re.IGNORECASE)

    # Limpieza cosmética final
    n = n.strip()
    n = re.sub(r"^[-–]\s*", "", n) 
    n = re.sub(r"\s*[-–]$", "", n) 
    
    # REGLA SALVAVIDAS: Si borramos demasiado, devolver el original
    if len(n) < 2:
        # Intenta al menos quitar la palabra SAPHIRUS si es lo único que molesta
        backup = re.sub(r"\s*SAPHIRUS.*", "", nombre, flags=re.IGNORECASE).strip()
        return backup
        
    return n

def subir_archivo_robusto(texto_contenido):
    try:
        files = {
            'reqtype': (None, 'fileupload'),
            'userhash': (None, ''),
            'fileToUpload': ('reposicion.txt', texto_contenido)
        }
        response = requests.post('https://catbox.moe/user/api.php', files=files)
        if response.status_code == 200:
            return response.text.strip()
        return None
    except:
        return None

def procesar_pdf(archivo):
    reader = PdfReader(archivo)
    texto_completo = ""
    for page in reader.pages:
        texto_completo += page.extract_text() + "\n"
    
    texto_limpio = texto_completo.replace("\n", " ")
    datos = []

    # CSV Strategy
    patron_csv = r'"\s*(\d{8})\s*"\s*,\s*"\s*([-0-9,]+)\s+([^"]+)"'
    matches = re.findall(patron_csv, texto_limpio)
    if matches:
        for m in matches: datos.append({"ID": m[0], "Cantidad": m[1], "Producto": m[2]})
    else:
        # Text Strategy
        patron_libre = r'(\d{8})\s+([-0-9]+,\d{2})\s+(.*?)(?=\s\d{1,3}(?:\.\d{3})*,\d{2})'
        matches = re.findall(patron_libre, texto_limpio)
        for m in matches: datos.append({"ID": m[0], "Cantidad": m[1], "Producto": m[2].strip()})

    if not datos: return None

    df = pd.DataFrame(datos)
    
    # Conversiones
    df["Cantidad"] = df["Cantidad"].apply(lambda x: float(x.replace(",", ".")) if isinstance(x, str) else x)
    def limpiar_id(x): return re.sub(r'^\d{8}\s*', '', x.strip())
    df["Producto"] = df["Producto"].apply(limpiar_id)
    
    df = df[df["Cantidad"] > 0]
    
    # 1. CATEGORIZAR (Antes de limpiar nombre)
    df["Categoria"] = df["Producto"].apply(detectar_categoria)
    
    # 2. LIMPIAR NOMBRE
    df["Producto"] = df["Producto"].apply(limpiar_nombre_visual)
    
    # 3. AGRUPAR
    df_final = df.groupby(["Categoria", "Producto"], as_index=False)["Cantidad"].sum()
    
    return df_final

# --- INTERFAZ ---
archivo = st.file_uploader("Subir PDF", type="pdf")

if archivo:
    df_res = procesar_pdf(archivo)
    
    if df_res is not None and not df_res.empty:
        mensaje_txt = "📋 *LISTA DE REPOSICIÓN*\n"
        cats = sorted(df_res["Categoria"].unique())
        
        for c in cats:
            mensaje_txt += f"\n== {c.upper()} ==\n"
            sub = df_res[df_res["Categoria"]==c]
            sub = sub.sort_values("Producto")
            
            for _, r in sub.iterrows():
                cant = int(r['Cantidad']) if r['Cantidad'].is_integer() else r['Cantidad']
                mensaje_txt += f"{cant} x {r['Producto']}\n"
        
        total = len(df_res)
        l = len(mensaje_txt)
        st.success(f"✅ {total} artículos organizados.")
        st.text_area("Vista previa:", mensaje_txt, height=500)
        
        if st.button("🚀 Enviar a WhatsApp", type="primary"):
            if not SID or not TOK:
                st.error("Faltan credenciales")
                st.stop()
            
            client = Client(SID, TOK)
            enviado = False
            
            with st.status("Enviando...", expanded=True) as status:
                if l < 1500:
                    try:
                        client.messages.create(body=mensaje_txt, from_=FROM, to=TO)
                        enviado = True
                    except Exception as e: st.error(f"Error: {e}")
                else:
                    status.write("Generando archivo...")
                    link = subir_archivo_robusto(mensaje_txt)
                    if link:
                        client.messages.create(body=f"📄 *Lista Completa*\nDescarga: {link}", from_=FROM, to=TO)
                        enviado = True
                    else:
                        status.write("⚠️ Falló archivo. Enviando por partes...")
                        trozos = [mensaje_txt[i:i+1500] for i in range(0, l, 1500)]
                        for t in trozos: client.messages.create(body=t, from_=FROM, to=TO)
                        enviado = True
            
            if enviado:
                st.balloons()
                st.success("¡Enviado!")
    else:
        st.error("Error leyendo PDF.")
