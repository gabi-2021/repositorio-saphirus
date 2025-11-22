import streamlit as st
import pandas as pd
import re
from pypdf import PdfReader
from twilio.rest import Client

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Repositor Saphirus", page_icon="📦", layout="centered")
st.title("📦 Repositor Saphirus 4.0")

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

def detectar_categoria(producto):
    p = producto.upper()
    if "TEXTIL" in p: return "👕 Textiles"
    if "AEROSOL" in p: return "💨 Aerosoles"
    if "DIFUSOR" in p or "VARILLA" in p: return "🎍 Difusores"
    if "SAHUMERIO" in p: return "🧘 Sahumerios"
    if "AUTO" in p or "RUTA" in p or "TOUCH" in p: return "🚗 Autos"
    if "VELA" in p: return "🕯️ Velas"
    if "HOME" in p: return "🏠 Home Spray"
    return "📦 Varios"

def procesar_pdf(archivo):
    reader = PdfReader(archivo)
    texto_completo = ""
    for page in reader.pages:
        texto_completo += page.extract_text() + "\n"
    
    # Limpieza básica: quitar saltos de línea
    texto_limpio = texto_completo.replace("\n", " ")
    
    datos = []

    # --- ESTRATEGIA 1: Formato CSV con Comillas (El original) ---
    # Busca: "36200035","2,00...
    patron_csv = r'"\s*(\d{8})\s*"\s*,\s*"\s*([-0-9,]+)\s+([^"]+)"'
    matches = re.findall(patron_csv, texto_limpio)
    
    if matches:
        st.info("Modo: CSV Estricto detectado")
        for m in matches:
            datos.append({"ID": m[0], "Cantidad": m[1], "Producto": m[2]})
            
    else:
        # --- ESTRATEGIA 2: Modo Rescate (Sin comillas) ---
        # Basado en tu diagnóstico: ID  CANT  DESCRIPCION  PRECIO
        # Explicación Regex:
        # (\d{8})           -> Captura 8 digitos (ID)
        # \s+               -> Espacios
        # ([-0-9]+,\d{2})   -> Captura Cantidad (ej: 2,00 o -1,00)
        # \s+               -> Espacios
        # (.*?)             -> Captura Descripción (mínimo posible)
        # (?=\s\d{1,3}\.)   -> PARE cuando vea el Precio (ej: 5.050,00)
        
        st.warning("Modo: Texto Plano (Sin comillas) activado")
        patron_libre = r'(\d{8})\s+([-0-9]+,\d{2})\s+(.*?)(?=\s\d{1,3}(?:\.\d{3})*,\d{2})'
        matches = re.findall(patron_libre, texto_limpio)
        
        for m in matches:
            datos.append({"ID": m[0], "Cantidad": m[1], "Producto": m[2].strip()})

    if not datos:
        return None, texto_limpio

    # Procesar datos
    df = pd.DataFrame(datos)
    
    # Limpiar números
    def clean_num(x):
        try: return float(x.replace(",", "."))
        except: return 0.0
        
    df["Cantidad"] = df["Cantidad"].apply(clean_num)
    
    # Limpiar descripción (a veces se cuela el ID repetido o guiones)
    def clean_desc(x):
        x = x.strip()
        # Quitar ID si se coló al principio
        x = re.sub(r'^\d{8}\s*', '', x)
        # Quitar guiones al inicio
        x = re.sub(r'^[-–]\s*', '', x)
        return x

    df["Producto"] = df["Producto"].apply(clean_desc)
    
    # Filtrar positivos y categorizar
    df = df[df["Cantidad"] > 0]
    df["Categoria"] = df["Producto"].apply(detectar_categoria)
    
    # Agrupar
    df_final = df.groupby(["Categoria", "Producto"], as_index=False)["Cantidad"].sum()
    
    return df_final, texto_limpio

# --- INTERFAZ ---
archivo = st.file_uploader("Subir PDF", type="pdf")

if archivo:
    df_res, debug = procesar_pdf(archivo)
    
    if df_res is not None and not df_res.empty:
        st.success(f"✅ {len(df_res)} Productos encontrados")
        
        # Crear mensaje
        mensaje = "📋 *REPOSICIÓN*\n"
        cats = df_res["Categoria"].unique()
        for c in cats:
            mensaje += f"\n*{c}*\n"
            sub = df_res[df_res["Categoria"]==c]
            for _, r in sub.iterrows():
                cant = int(r['Cantidad']) if r['Cantidad'].is_integer() else r['Cantidad']
                mensaje += f"▫️ {cant} x {r['Producto']}\n"

        st.text_area("Mensaje:", mensaje, height=200)
        
        if st.button("Enviar WhatsApp"):
            if SID and TOK:
                try:
                    cli = Client(SID, TOK)
                    # Cortar si es largo
                    msgs = [mensaje[i:i+1500] for i in range(0, len(mensaje), 1500)]
                    for m in msgs:
                        cli.messages.create(body=m, from_=FROM, to=TO)
                    st.balloons()
                    st.success("Enviado!")
                except Exception as e:
                    st.error(f"Error Twilio: {e}")
            else:
                st.error("Faltan credenciales")
    else:
        st.error("No se pudo leer. Verifica Diagnóstico.")
        with st.expander("Ver Diagnóstico"):
            st.write(debug[:1000])
