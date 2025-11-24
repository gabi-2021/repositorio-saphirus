import streamlit as st
import pandas as pd
import re
import requests
from pypdf import PdfReader
from twilio.rest import Client

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Repositor Saphirus", page_icon="✨", layout="centered")
st.title("✨ Repositor Saphirus 17.0")

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

# --- 1. DETECCIÓN DE CATEGORÍA (Expandida) ---
def detectar_categoria(producto):
    p = producto.upper()
    
    # 1. TOUCH (Prioridad máxima)
    if "DISPOSITIVO" in p and "TOUCH" in p: return "🖱️ Dispositivos Touch"
    if ("REPUESTO" in p and "TOUCH" in p) or "GR/13" in p: return "🔄 Repuestos de Touch"

    # 2. PERFUMERÍA (Nueva)
    if "MINI MILANO" in p: return "🧴 Perfume Mini Milano"
    if "PARFUM" in p: return "🧴 Parfum / Perfumes"

    # 3. AMBAR
    if "AMBAR" in p:
        if "AEROSOL" in p: return "🔸 Aerosoles Ambar"
        if "TEXTIL" in p or "150 ML" in p: return "🔸 Textiles Ambar"
        if "SAHUMERIO" in p: return "🔸 Sahumerios Ambar"
        return "🔸 Línea Ambar Varios"

    # 4. HOME SPRAY
    if "HOME SPRAY" in p or "500 ML" in p or "500ML" in p: return "🏠 Home Spray"

    # 5. APARATOS (Resto de aparatos no touch)
    if "APARATO" in p or "HORNILLO" in p: return "⚙️ Aparatos"

    # 6. PREMIUM
    if "PREMIUM" in p: return "💎 Difusores Premium"

    # 7. SAHUMERIOS (Divididos)
    if "SAHUMERIO" in p:
        if "HIERBAS" in p: return "🌿 Sahumerios Hierbas"
        if "HIMALAYA" in p: return "🏔️ Sahumerios Himalaya"
        return "🧘 Sahumerios Varios"
    
    # 8. AUTOS
    if "CARITAS" in p: return "😎 Autos - Caritas"
    if "RUTA" in p or "RUTA 66" in p: return "🛣️ Autos - Ruta 66"
    if "AUTO" in p: return "🚗 Autos - Varios"

    # 9. ESTÁNDAR
    if "TEXTIL" in p: return "👕 Textiles (250ml)"
    if "AEROSOL" in p: return "💨 Aerosoles"
    if "DIFUSOR" in p or "VARILLA" in p: return "🎍 Difusores"
    if "VELA" in p: return "🕯️ Velas"
    if "ACEITE" in p: return "💧 Aceites"
    if "ANTIHUMEDAD" in p: return "💧 Antihumedad"
    if "LIMPIADOR" in p: return "🧼 Limpiadores"
    
    return "📦 Varios"

# --- 2. ESPECIALISTAS DE LIMPIEZA ---

def limpiar_general(nombre):
    n = nombre
    n = re.sub(r"\s*[-–]?\s*SAPHIRUS.*$", "", n, flags=re.IGNORECASE)
    n = re.sub(r"\s*[-–]?\s*AMBAR.*$", "", n, flags=re.IGNORECASE)
    n = n.strip()
    n = re.sub(r"^[-–]\s*", "", n)
    n = re.sub(r"\s*[-–]$", "", n)
    if len(n) < 2: return nombre
    return n

def limpiar_antihumedad(nombre):
    n = nombre.upper()
    # 1. Borrar la redundancia "ANTI HUMEDAD"
    n = re.sub(r"ANTI\s+HUMEDAD", "", n)
    # 2. Borrar la marca SAPHIRUS
    n = re.sub(r"SAPHIRUS", "", n)
    # 3. Borrar códigos numéricos al final (ej: - 684569)
    n = re.sub(r"[-–]\s*\d+$", "", n)
    # 4. Limpiar espacios dobles que quedan
    n = re.sub(r"\s+", " ", n).strip()
    return n

def limpiar_perfumes(nombre):
    n = nombre.upper()
    n = re.sub(r"PERFUME MINI MILANO\s*[-–]?\s*", "", n)
    n = re.sub(r"SAPHIRUS PARFUM\s*", "", n)
    return limpiar_general(n)

def limpiar_aparatos(nombre):
    n = nombre.upper()
    n = re.sub(r"APARATO ANALOGICO DECO", "ANALOGICO", n)
    n = re.sub(r"HORNILLO CERAMICA", "HORNILLO", n)
    n = re.sub(r"\s*[-–]?\s*SAPHIRUS.*$", "", n) # Borrar marca final
    return n.strip()

def limpiar_sahumerio_ambar(nombre):
    n = nombre.upper()
    n = re.sub(r"^SAHUMERIO\s*[-–]?\s*AMBAR\s*[-–]?\s*", "", n)
    if len(n) < 3: return "SAHUMERIO AMBAR (Generico)"
    return limpiar_general(n)

def limpiar_sahumerio_tipo(nombre): # Para Hierbas y Himalaya
    n = nombre.upper()
    n = re.sub(r"^SAHUMERIO HIERBAS\s*[-–]?\s*", "", n)
    n = re.sub(r"^SAHUMERIO HIMALAYA\s*[-–]?\s*", "", n)
    n = re.sub(r"^SAHUMERIO\s*[-–]?\s*", "", n)
    return limpiar_general(n)

def limpiar_repuesto_touch(nombre):
    n = nombre.upper()
    n = re.sub(r"REPUESTO TOUCH\s*(9\s*)?GR/13\s*CM3\s*[-–]?\s*", "", n)
    n = re.sub(r"^REPUESTO TOUCH\s*[-–]?\s*", "", n)
    return limpiar_general(n)

def limpiar_dispositivo_touch(nombre):
    n = nombre.upper()
    if "REPUESTO NEGRO" in n: n = n.replace("REPUESTO NEGRO", "NEGRO + REPUESTO")
    n = re.sub(r"^DISPOSITIVO TOUCH\s*(\+)?\s*", "", n)
    n = re.sub(r"\s*\d{6,}$", "", n)
    return limpiar_general(n)

def limpiar_home_spray(nombre):
    n = nombre.upper()
    n = re.sub(r"^HOME SPRAY\s*[-–]?\s*", "", n)
    n = re.sub(r"\s*[-–]?\s*AROMATIZANTE TEXTIL.*$", "", n)
    n = re.sub(r"\s*500\s*ML.*$", "", n)
    return limpiar_general(n)

def limpiar_textil(nombre):
    n = nombre.upper()
    n = re.sub(r"^AROMATIZADOR TEXTIL 150 ML AMBAR\s*[-–]?\s*", "", n)
    prefijos = [r"^AROMATIZADOR TEXTIL 250 ML\s*[-–]?\s*", r"^AROMATIZADOR TEXTIL MINI 60 ML\s*[-–]?\s*", r"^AROMATIZADOR TEXTIL\s*[-–]?\s*"]
    for p in prefijos: n = re.sub(p, "", n)
    return limpiar_general(n)

def limpiar_autos(nombre):
    n = nombre.upper()
    n = re.sub(r"CARITAS EMOGI X 2", "", n)
    n = re.sub(r"RUTA 66", "", n)
    n = re.sub(r"AROMATIZANTE AUTO", "", n)
    n = re.sub(r"\s*X\s*2.*$", "", n)
    return limpiar_general(n)

def limpiar_velas(nombre):
    n = nombre.upper()
    n = re.sub(r"VELAS SAPHIRUS", "VELAS", n)
    n = re.sub(r"\s*[-–]?\s*SAPHIRUS.*$", "", n)
    return n.strip()

def limpiar_aerosol(nombre):
    n = nombre.upper()
    n = re.sub(r"^AEROSOL\s*[-–]?\s*", "", n)
    return limpiar_general(n)

def limpiar_difusor(nombre):
    n = nombre.upper()
    n = re.sub(r"^DIFUSOR AROMATICO\s*[-–]?\s*", "", n)
    n = re.sub(r"^DIFUSOR PREMIUM\s*[-–]?\s*", "", n)
    n = re.sub(r"^DIFUSOR\s*[-–]?\s*", "", n)
    n = re.sub(r"\s*[-–]?\s*VARILLA.*$", "", n)
    return limpiar_general(n)

# --- 3. DISPATCHER ---
def limpiar_producto_por_categoria(row):
    cat = row["Categoria"]
    nom = row["Producto"]
    
    if "Sahumerios Ambar" in cat: return limpiar_sahumerio_ambar(nom)
    if "Repuestos de Touch" in cat: return limpiar_repuesto_touch(nom)
    if "Dispositivos Touch" in cat: return limpiar_dispositivo_touch(nom)
    if "Antihumedad" in cat: return limpiar_antihumedad(nom) # NUEVO
    if "Perfume" in cat or "Parfum" in cat: return limpiar_perfumes(nom) # NUEVO
    if "Aparatos" in cat: return limpiar_aparatos(nom) # NUEVO
    
    if "Sahumerios" in cat: return limpiar_sahumerio_tipo(nom)
    if "Home Spray" in cat: return limpiar_home_spray(nom)
    if "Textiles" in cat: return limpiar_textil(nom)
    if "Autos" in cat: return limpiar_autos(nom)
    if "Aerosoles" in cat: return limpiar_aerosol(nom)
    if "Difusores" in cat: return limpiar_difusor(nom)
    if "Velas" in cat: return limpiar_velas(nom)
    
    return limpiar_general(nom)

# --- 4. PROCESAMIENTO ---
def subir_archivo_robusto(texto_contenido):
    try:
        files = {'reqtype': (None, 'fileupload'), 'userhash': (None, ''), 'fileToUpload': ('reposicion.txt', texto_contenido)}
        response = requests.post('https://catbox.moe/user/api.php', files=files)
        if response.status_code == 200: return response.text.strip()
        return None
    except: return None

def procesar_pdf(archivo):
    reader = PdfReader(archivo)
    texto_completo = ""
    for page in reader.pages: texto_completo += page.extract_text() + "\n"
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
    df["Producto"] = df.apply(limpiar_producto_por_categoria, axis=1)
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
            sub = df_res[df_res["Categoria"]==c].sort_values("Producto")
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
    else: st.error("Error leyendo PDF.")
