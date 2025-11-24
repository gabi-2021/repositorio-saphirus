import streamlit as st
import pandas as pd
import re
import requests
from pypdf import PdfReader
from twilio.rest import Client

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Repositor Saphirus", page_icon="✨", layout="centered")
st.title("✨ Repositor Saphirus 9.0")

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

# --- 1. CATEGORIZACIÓN AVANZADA ---
def detectar_categoria(producto):
    p = producto.upper()
    
    # --- LÓGICA AMBAR (Separada) ---
    if "AMBAR" in p:
        if "AEROSOL" in p: return "🔸 Aerosoles Ambar"
        if "TEXTIL" in p: return "🔸 Textiles Ambar"
        if "SAHUMERIO" in p: return "🔸 Sahumerios Ambar"
        return "🔸 Línea Ambar Varios"

    # --- LÓGICA HOME SPRAY (Prioridad sobre Textil) ---
    # Detecta 500 ML o Home Spray explícito
    if "HOME SPRAY" in p or "500 ML" in p or "500ML" in p: 
        return "🏠 Home Spray"

    # --- LÓGICA PREMIUM ---
    if "PREMIUM" in p and ("DIFUSOR" in p or "VARILLA" in p): 
        return "💎 Difusores Premium"

    # --- CATEGORÍAS ESTÁNDAR ---
    if "TEXTIL" in p: return "👕 Textiles (250ml)"
    if "AEROSOL" in p: return "💨 Aerosoles"
    if "DIFUSOR" in p or "VARILLA" in p: return "🎍 Difusores"
    if "SAHUMERIO" in p: return "🧘 Sahumerios"
    if "AUTO" in p or "RUTA" in p or "TOUCH" in p or "CARITAS" in p: return "🚗 Autos"
    if "VELA" in p: return "🕯️ Velas"
    if "ACEITE" in p: return "💧 Aceites"
    
    return "📦 Varios"

# --- 2. LIMPIEZA DE NOMBRES (LAVADORA DE TEXTO) ---
def limpiar_nombre_visual(nombre):
    """
    Elimina prefijos y sufijos molestos para dejar solo la fragancia.
    """
    n = nombre
    
    # 1. Eliminar Prefijos (Lo que está al principio)
    prefijos = [
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
        r"^CARITAS EMOGI X 2\s*[-–]?\s*",
        # Cuidado con VELAS: Solo borramos si sigue texto, para no borrar el nombre si es genérico
        r"^VELAS SAPHIRUS X \d+ UNIDADES\s*[-–]\s*" 
    ]
    for pat in prefijos:
        n = re.sub(pat, "", n, flags=re.IGNORECASE)

    # 2. Eliminar Sufijos (Lo que está al final, como "- SAPHIRUS")
    sufijos = [
        r"\s*[-–]?\s*SAPHIRUS.*$",          # Borra " - SAPHIRUS" y todo lo que siga
        r"\s*[-–]?\s*AMBAR.*$",             # Borra " - AMBAR" al final (ya está en la categoría)
        r"\s*[-–]?\s*AROMATIZANTE TEXTIL\s*500\s*ML.*$", # Borra descripción técnica de Home Spray
        r"\s*[-–]?\s*AROMATIZANTE TEXTIL.*$",
        r"\s*[-–]?\s*X\s*\d+\s*SAPHIRUS.*$", # Ej: X 2 SAPHIRUS
        r"\s*[-–]?\s*VARILLA SAPHIRUS.*$",
        r"\s*[-–]?\s*AROMATICO VARILLA.*$"
    ]
    for pat in sufijos:
        n = re.sub(pat, "", n, flags=re.IGNORECASE)

    # 3. Limpieza final de guiones sueltos o espacios
    n = n.strip()
    n = re.sub(r"^[-–]\s*", "", n) # Guión al inicio
    n = re.sub(r"\s*[-–]$", "", n) # Guión al final
    
    # 4. REGLA DE EMERGENCIA: Si borramos todo, devolver el original
    # (Esto arregla el problema de las Velas que se quedaban vacías)
    if len(n) < 2:
        return nombre.strip()
        
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

    # CSV
    patron_csv = r'"\s*(\d{8})\s*"\s*,\s*"\s*([-0-9,]+)\s+([^"]+)"'
    matches = re.findall(patron_csv, texto_limpio)
    if matches:
        for m in matches: datos.append({"ID": m[0], "Cantidad": m[1], "Producto": m[2]})
    else:
        # Texto Plano
        patron_libre = r'(\d{8})\s+([-0-9]+,\d{2})\s+(.*?)(?=\s\d{1,3}(?:\.\d{3})*,\d{2})'
        matches = re.findall(patron_libre, texto_limpio)
        for m in matches: datos.append({"ID": m[0], "Cantidad": m[1], "Producto": m[2].strip()})

    if not datos: return None

    df = pd.DataFrame(datos)
    
    # Conversiones
    df["Cantidad"] = df["Cantidad"].apply(lambda x: float(x.replace(",", ".")) if isinstance(x, str) else x)
    def limpiar_id(x): return re.sub(r'^\d{8}\s*', '', x.strip())
    df["Producto"] = df["Producto"].apply(limpiar_id)
    
    # Filtrar
    df = df[df["Cantidad"] > 0]
    
    # 1. CATEGORIZAR (Antes de limpiar nombre para no perder info como "500 ML")
    df["Categoria"] = df["Producto"].apply(detectar_categoria)
    
    # 2. LIMPIAR NOMBRE VISUAL
    df["Producto"] = df["Producto"].apply(limpiar_nombre_visual)
    
    # 3. AGRUPAR
    df_final = df.groupby(["Categoria", "Producto"], as_index=False)["Cantidad"].sum()
    
    return df_final

# --- INTERFAZ ---
archivo = st.file_uploader("Subir PDF", type="pdf")

if archivo:
    df_res = procesar_pdf(archivo)
    
    if df_res is not None and not df_res.empty:
        # Generar Texto
        mensaje_txt = "📋 *LISTA DE REPOSICIÓN*\n"
        cats = sorted(df_res["Categoria"].unique())
        
        for c in cats:
            mensaje_txt += f"\n== {c.upper()} ==\n"
            sub = df_res[df_res["Categoria"]==c]
            sub = sub.sort_values("Producto")
            
            for _, r in sub.iterrows():
                cant = int(r['Cantidad']) if r['Cantidad'].is_integer() else r['Cantidad']
                # FORMATO SIMPLE: 1 x NOMBRE
                mensaje_txt += f"{cant} x {r['Producto']}\n"
        
        total = len(df_res)
        l = len(mensaje_txt)
        st.success(f"✅ {total} artículos.")
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
