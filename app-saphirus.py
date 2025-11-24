import streamlit as st
import pandas as pd
import re
import requests
from pypdf import PdfReader
from twilio.rest import Client

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Repositor Saphirus", page_icon="✨", layout="centered")
st.title("✨ Repositor Saphirus 12.0")

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

# --- 1. CATEGORIZACIÓN (MÁS ESPECÍFICA) ---
def detectar_categoria(producto):
    p = producto.upper()
    
    # AMBAR
    if "AMBAR" in p:
        if "AEROSOL" in p: return "🔸 Aerosoles Ambar"
        if "TEXTIL" in p or "150 ML" in p: return "🔸 Textiles Ambar"
        if "SAHUMERIO" in p: return "🔸 Sahumerios Ambar"
        return "🔸 Línea Ambar Varios"

    # PERFUMERÍA / MINI
    if "MINI MILANO" in p: return "🧴 Perfume Mini Milano"
    if "PARFUM" in p or "PERFUME" in p: return "🧴 Parfum / Perfumes"

    # APARATOS
    if "APARATO" in p or "HORNILLO" in p or "DISPOSITIVO" in p:
        # Excepción: Los Touch a veces se consideran aparatos, pero si quieres separarlos:
        if "TOUCH" in p: return "🚗 Autos - Touch/Varios" 
        return "⚙️ Aparatos y Hornillos"

    # HOME SPRAY
    if "HOME SPRAY" in p or "500 ML" in p or "500ML" in p: 
        return "🏠 Home Spray"

    # PREMIUM
    if "PREMIUM" in p and ("DIFUSOR" in p or "VARILLA" in p): 
        return "💎 Difusores Premium"

    # SAHUMERIOS (DIVIDIDOS)
    if "SAHUMERIO" in p:
        if "HIERBAS" in p: return "🌿 Sahumerios Hierbas"
        if "HIMALAYA" in p: return "🏔️ Sahumerios Himalaya"
        return "🧘 Sahumerios Varios"

    # AUTOS
    if "CARITAS" in p: return "😎 Autos - Caritas"
    if "RUTA" in p or "RUTA 66" in p: return "🛣️ Autos - Ruta 66"
    if "AUTO" in p or "TOUCH" in p: return "🚗 Autos - Touch/Varios"

    # RESTO
    if "TEXTIL" in p: return "👕 Textiles (250ml)"
    if "AEROSOL" in p: return "💨 Aerosoles"
    if "DIFUSOR" in p or "VARILLA" in p: return "🎍 Difusores"
    if "VELA" in p: return "🕯️ Velas"
    if "ACEITE" in p: return "💧 Aceites"
    if "ANTIHUMEDAD" in p: return "💧 Antihumedad"
    
    return "📦 Varios"

# --- 2. LIMPIEZA DE NOMBRES ---
def limpiar_nombre_visual(nombre):
    n = nombre
    
    # --- REGLA ANTIHUMEDAD (Nueva) ---
    # Transforma "ANTIHUMEDAD ANTI HUMEDAD SAPHIRUS 145 GR-684569" en "ANTIHUMEDAD 145 GR"
    if "ANTIHUMEDAD" in n.upper():
        # 1. Borrar la repetición y la marca
        n = re.sub(r"ANTIHUMEDAD\s+ANTI\s+HUMEDAD\s*(SAPHIRUS)?", "ANTIHUMEDAD", n, flags=re.IGNORECASE)
        n = re.sub(r"ANTIHUMEDAD\s+SAPHIRUS", "ANTIHUMEDAD", n, flags=re.IGNORECASE)
        # 2. Borrar códigos al final (ej: - 684569)
        n = re.sub(r"\s*-\s*\d+$", "", n)
        return n.strip()

    # --- REGLA PARFUM/MINI ---
    n = re.sub(r"SAPHIRUS PARFUM", "", n, flags=re.IGNORECASE)
    n = re.sub(r"PERFUME MINI MILANO\s*[-–]?\s*", "", n, flags=re.IGNORECASE)
    
    # --- REGLA APARATOS ---
    n = re.sub(r"APARATO ANALOGICO DECO", "ANALOGICO", n, flags=re.IGNORECASE)
    n = re.sub(r"HORNILLO CERAMICA", "HORNILLO", n, flags=re.IGNORECASE)

    # --- REGLA SAHUMERIOS ---
    n = re.sub(r"SAHUMERIO HIERBAS\s*[-–]?\s*", "", n, flags=re.IGNORECASE)
    n = re.sub(r"SAHUMERIO HIMALAYA\s*[-–]?\s*", "", n, flags=re.IGNORECASE)
    n = re.sub(r"SAHUMERIO\s*[-–]?\s*", "", n, flags=re.IGNORECASE)

    # --- OTRAS REGLAS ---
    n = re.sub(r"CARITAS EMOGI X 2", "", n, flags=re.IGNORECASE)
    n = re.sub(r"RUTA 66", "", n, flags=re.IGNORECASE)
    n = re.sub(r"AROMATIZANTE AUTO", "", n, flags=re.IGNORECASE)
    
    prefijos = [
        r"^DIFUSOR AROMATICO\s*[-–]?\s*",
        r"^DIFUSOR PREMIUM\s*[-–]?\s*",
        r"^AROMATIZADOR TEXTIL 250 ML\s*[-–]?\s*",
        r"^AROMATIZADOR TEXTIL MINI 60 ML\s*[-–]?\s*",
        r"^AROMATIZADOR TEXTIL 150 ML AMBAR\s*[-–]?\s*",
        r"^AROMATIZADOR TEXTIL\s*[-–]?\s*",
        r"^AEROSOL\s*[-–]?\s*",
        r"^HOME SPRAY\s*[-–]?\s*",
        r"^VELAS SAPHIRUS\s*",
        r"^DISPOSITIVO TOUCH\s*"
    ]
    for pat in prefijos:
        n = re.sub(pat, "", n, flags=re.IGNORECASE)

    sufijos = [
        r"\s*[-–]?\s*SAPHIRUS.*$",
        r"\s*[-–]?\s*AMBAR.*$",
        r"\s*[-–]?\s*AROMATIZANTE TEXTIL.*$",
        r"\s*[-–]?\s*VARILLA SAPHIRUS.*$",
        r"\s*[-–]?\s*AROMATICO VARILLA.*$",
        r"\s*[-–]?\s*X\s*2.*$",
        r"\s*X\s*2$"
    ]
    for pat in sufijos:
        n = re.sub(pat, "", n, flags=re.IGNORECASE)

    n = n.strip()
    n = re.sub(r"^[-–]\s*", "", n) 
    n = re.sub(r"\s*[-–]$", "", n) 
    
    if len(n) < 3:
        backup = re.sub(r"SAPHIRUS", "", nombre, flags=re.IGNORECASE).strip()
        backup = re.sub(r"^[-–]", "", backup).strip()
        return backup if len(backup) > 2 else nombre
        
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

    patron_csv = r'"\s*(\d{8})\s*"\s*,\s*"\s*([-0-9,]+)\s+([^"]+)"'
    matches = re.findall(patron_csv, texto_limpio)
    if matches:
        for m in matches: datos.append({"ID": m[0], "Cantidad": m[1], "Producto": m[2]})
    else:
        patron_libre = r'(\d{8})\s+([-0-9]+,\d{2})\s+(.*?)(?=\s\d{1,3}(?:\.\d{3})*,\d{2})'
        matches = re.findall(patron_libre, texto_limpio)
        for m in matches: datos.append({"ID": m[0], "Cantidad": m[1], "Producto": m[2].strip()})

    if not datos: return None

    df = pd.DataFrame(datos)
    
    df["Cantidad"] = df["Cantidad"].apply(lambda x: float(x.replace(",", ".")) if isinstance(x, str) else x)
    def limpiar_id(x): return re.sub(r'^\d{8}\s*', '', x.strip())
    df["Producto"] = df["Producto"].apply(limpiar_id)
    
    df = df[df["Cantidad"] > 0]
    
    df["Categoria"] = df["Producto"].apply(detectar_categoria)
    df["Producto"] = df["Producto"].apply(limpiar_nombre_visual)
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
