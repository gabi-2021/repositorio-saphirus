import streamlit as st
import pandas as pd
import re
import requests
from pypdf import PdfReader
from twilio.rest import Client

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Repositor Saphirus", page_icon="📦", layout="centered")
st.title("📦 Repositor Saphirus 6.0")

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

# --- FUNCIONES ---
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

def subir_archivo_temporal(texto_contenido):
    """
    Sube el texto a file.io (más estable)
    """
    try:
        # Preparamos el archivo
        files = {'file': ('pedido_reposicion.txt', texto_contenido)}
        # expires=1d significa que el link dura 1 día
        response = requests.post('https://file.io/?expires=1d', files=files)
        
        if response.status_code == 200:
            # File.io devuelve un JSON con el link
            return response.json()["link"]
        else:
            st.error(f"Error del servidor de archivos: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

def procesar_pdf(archivo):
    reader = PdfReader(archivo)
    texto_completo = ""
    for page in reader.pages:
        texto_completo += page.extract_text() + "\n"
    
    texto_limpio = texto_completo.replace("\n", " ")
    datos = []

    # 1. Estrategia CSV
    patron_csv = r'"\s*(\d{8})\s*"\s*,\s*"\s*([-0-9,]+)\s+([^"]+)"'
    matches = re.findall(patron_csv, texto_limpio)
    
    if matches:
        for m in matches:
            datos.append({"ID": m[0], "Cantidad": m[1], "Producto": m[2]})
    else:
        # 2. Estrategia Texto Plano
        patron_libre = r'(\d{8})\s+([-0-9]+,\d{2})\s+(.*?)(?=\s\d{1,3}(?:\.\d{3})*,\d{2})'
        matches = re.findall(patron_libre, texto_limpio)
        for m in matches:
            datos.append({"ID": m[0], "Cantidad": m[1], "Producto": m[2].strip()})

    if not datos:
        return None

    df = pd.DataFrame(datos)
    
    # Limpiezas
    df["Cantidad"] = df["Cantidad"].apply(lambda x: float(x.replace(",", ".")) if isinstance(x, str) else x)
    
    def limpiar_desc(x):
        x = x.strip()
        x = re.sub(r'^\d{8}\s*', '', x)
        return x
    df["Producto"] = df["Producto"].apply(limpiar_desc)
    
    # Filtrar
    df = df[df["Cantidad"] > 0]
    df["Categoria"] = df["Producto"].apply(detectar_categoria)
    df_final = df.groupby(["Categoria", "Producto"], as_index=False)["Cantidad"].sum()
    
    return df_final

# --- INTERFAZ ---
archivo = st.file_uploader("Subir PDF", type="pdf")

if archivo:
    df_res = procesar_pdf(archivo)
    
    if df_res is not None and not df_res.empty:
        # Generar Texto
        mensaje_txt = "📋 *LISTA DE REPOSICIÓN*\n"
        cats = df_res["Categoria"].unique()
        for c in cats:
            mensaje_txt += f"\n== {c.upper()} ==\n"
            sub = df_res[df_res["Categoria"]==c]
            for _, r in sub.iterrows():
                cant = int(r['Cantidad']) if r['Cantidad'].is_integer() else r['Cantidad']
                mensaje_txt += f"[ ] {cant} x {r['Producto']}\n"
        
        total = len(df_res)
        st.success(f"✅ {total} artículos detectados.")
        st.text_area("Vista previa:", mensaje_txt, height=200)
        
        if st.button("🚀 Enviar a WhatsApp", type="primary"):
            if not SID or not TOK:
                st.error("Faltan credenciales")
                st.stop()
                
            client = Client(SID, TOK)
            largo = len(mensaje_txt)
            
            with st.spinner("Enviando..."):
                try:
                    # Si es corto, mandar texto
                    if largo < 1500:
                        client.messages.create(body=mensaje_txt, from_=FROM, to=TO)
                        st.balloons()
                        st.success("✅ Mensaje enviado.")
                    
                    # Si es largo, mandar archivo
                    else:
                        st.info("Generando archivo temporal...")
                        link = subir_archivo_temporal(mensaje_txt)
                        
                        if link:
                            client.messages.create(
                                body=f"📄 *Lista Completa ({total} items)*\nDescarga el archivo aquí:",
                                from_=FROM,
                                to=TO,
                                media_url=[link]
                            )
                            st.balloons()
                            st.success("✅ Archivo enviado a WhatsApp.")
                        else:
                            st.error("No se pudo generar el enlace. Intenta de nuevo.")
                            
                except Exception as e:
                    st.error(f"Error Twilio: {e}")

    else:
        st.error("No se pudieron leer datos.")
