import streamlit as st
import pandas as pd
import re
import requests
from pypdf import PdfReader
from twilio.rest import Client

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Repositor Saphirus", page_icon="📦", layout="centered")
st.title("📦 Repositor Saphirus 5.0")
st.caption("Versión con envío de archivo .txt automático")

# --- CREDENCIALES TWILIO ---
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
        FROM = st.text_input("From (whatsapp:+...)")
        TO = st.text_input("To (whatsapp:+...)")

# --- FUNCIONES AUXILIARES ---
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
    Sube el texto a transfer.sh y devuelve el link de descarga.
    Esto permite enviar archivos por WhatsApp sin tener servidor propio.
    """
    try:
        # Creamos el archivo en memoria para enviarlo
        files = {'file': ('pedido_reposicion.txt', texto_contenido)}
        response = requests.put('https://transfer.sh/pedido_reposicion.txt', files=files)
        if response.status_code == 200:
            return response.text.strip() # Retorna la URL
        else:
            return None
    except:
        return None

# --- LÓGICA DE PROCESAMIENTO ---
def procesar_pdf(archivo):
    reader = PdfReader(archivo)
    texto_completo = ""
    for page in reader.pages:
        texto_completo += page.extract_text() + "\n"
    
    texto_limpio = texto_completo.replace("\n", " ")
    datos = []

    # 1. Estrategia CSV (con comillas)
    patron_csv = r'"\s*(\d{8})\s*"\s*,\s*"\s*([-0-9,]+)\s+([^"]+)"'
    matches = re.findall(patron_csv, texto_limpio)
    
    if matches:
        for m in matches:
            datos.append({"ID": m[0], "Cantidad": m[1], "Producto": m[2]})
    else:
        # 2. Estrategia Texto Plano (Rescate para tu PDF específico)
        # Busca ID -> Espacios -> Cantidad -> Descripción -> Hasta encontrar Precio
        patron_libre = r'(\d{8})\s+([-0-9]+,\d{2})\s+(.*?)(?=\s\d{1,3}(?:\.\d{3})*,\d{2})'
        matches = re.findall(patron_libre, texto_limpio)
        for m in matches:
            datos.append({"ID": m[0], "Cantidad": m[1], "Producto": m[2].strip()})

    if not datos:
        return None, texto_limpio

    df = pd.DataFrame(datos)
    
    # Limpiezas
    df["Cantidad"] = df["Cantidad"].apply(lambda x: float(x.replace(",", ".")) if isinstance(x, str) else x)
    
    def limpiar_desc(x):
        x = x.strip()
        x = re.sub(r'^\d{8}\s*', '', x) # Quitar ID repetido al inicio
        return x
    df["Producto"] = df["Producto"].apply(limpiar_desc)
    
    # Filtrar y Agrupar
    df = df[df["Cantidad"] > 0]
    df["Categoria"] = df["Producto"].apply(detectar_categoria)
    df_final = df.groupby(["Categoria", "Producto"], as_index=False)["Cantidad"].sum()
    
    return df_final, texto_limpio

# --- INTERFAZ PRINCIPAL ---
archivo = st.file_uploader("Subir PDF", type="pdf")

if archivo:
    df_res, debug = procesar_pdf(archivo)
    
    if df_res is not None and not df_res.empty:
        # Generar el Texto del Mensaje
        mensaje_txt = "📋 *LISTA DE REPOSICIÓN*\n"
        cats = df_res["Categoria"].unique()
        for c in cats:
            mensaje_txt += f"\n== {c.upper()} ==\n" # Formato texto plano
            sub = df_res[df_res["Categoria"]==c]
            for _, r in sub.iterrows():
                cant = int(r['Cantidad']) if r['Cantidad'].is_integer() else r['Cantidad']
                mensaje_txt += f"[ ] {cant} x {r['Producto']}\n"
        
        total_items = len(df_res)
        st.success(f"✅ {total_items} artículos detectados.")
        
        # Mostrar vista previa
        st.text_area("Vista previa:", mensaje_txt, height=200)
        
        # Botón de Envío Inteligente
        if st.button("🚀 Enviar a WhatsApp", type="primary"):
            if not SID or not TOK:
                st.error("Faltan credenciales de Twilio")
                st.stop()
                
            client = Client(SID, TOK)
            largo = len(mensaje_txt)
            
            with st.spinner(f"Analizando tamaño ({largo} caracteres)..."):
                try:
                    # CASO 1: Mensaje Corto (Texto directo)
                    if largo < 1550:
                        client.messages.create(
                            body=mensaje_txt,
                            from_=FROM,
                            to=TO
                        )
                        st.balloons()
                        st.success("✅ Lista enviada como mensaje de texto.")
                    
                    # CASO 2: Mensaje Largo (Archivo .txt)
                    else:
                        st.info("⚠️ La lista es muy larga para un solo mensaje. Generando archivo...")
                        
                        # 1. Subir archivo a transfer.sh
                        link_archivo = subir_archivo_temporal(mensaje_txt)
                        
                        if link_archivo:
                            # 2. Enviar link como archivo multimedia en WhatsApp
                            client.messages.create(
                                body=f"📄 *Lista de Reposición Completa*\nContiene {total_items} artículos.\nAbre el archivo adjunto.",
                                media_url=[link_archivo],
                                from_=FROM,
                                to=TO
                            )
                            st.balloons()
                            st.success("✅ Archivo .txt enviado a WhatsApp.")
                        else:
                            st.error("Error generando el enlace del archivo. Intenta de nuevo.")
                            
                except Exception as e:
                    st.error(f"Error en Twilio: {str(e)}")

    else:
        st.error("No se pudo leer el PDF.")
        with st.expander("Ver detalles técnicos"):
            st.write(debug[:1000])
