import streamlit as st
import pandas as pd
import re
from pypdf import PdfReader
from twilio.rest import Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Repositor Saphirus", page_icon="📦", layout="centered")

st.title("📦 Repositor Saphirus 3.0")
st.markdown("Versión mejorada para detectar productos con formato invertido.")

# --- BARRA LATERAL: CREDENCIALES ---
with st.sidebar:
    st.header("🔐 Twilio")
    try:
        SID = st.secrets["TWILIO_SID"]
        TOK = st.secrets["TWILIO_TOKEN"]
        FROM = st.secrets["TWILIO_FROM"]
        TO = st.secrets["TWILIO_TO"]
        st.success("Credenciales OK 🔒")
    except:
        st.warning("Usa secrets o rellena abajo")
        SID = st.text_input("SID", type="password")
        TOK = st.text_input("Token", type="password")
        FROM = st.text_input("From", value="whatsapp:...")
        TO = st.text_input("To", value="whatsapp:...")

# --- LÓGICA DE CATEGORÍAS ---
def detectar_categoria(producto):
    p = producto.upper()
    if "TEXTIL" in p: return "👕 Textiles"
    if "AEROSOL" in p: return "💨 Aerosoles"
    if "DIFUSOR" in p or "VARILLA" in p: return "🎍 Difusores"
    if "SAHUMERIO" in p: return "🧘 Sahumerios"
    if "AUTO" in p or "RUTA" in p or "TOUCH" in p: return "🚗 Autos/Touch"
    if "VELA" in p: return "🕯️ Velas"
    if "HOME" in p: return "🏠 Home Spray"
    if "ACEITE" in p: return "💧 Aceites"
    return "📦 Varios"

# --- PROCESAMIENTO INTELIGENTE ---
def procesar_pdf(archivo):
    reader = PdfReader(archivo)
    texto_completo = ""
    for page in reader.pages:
        texto_completo += page.extract_text() + "\n"
    
    # Limpieza: quitamos saltos de línea para analizar bloques
    texto_limpio = texto_completo.replace("\n", " ")
    
    # --- NUEVO PATRÓN ---
    # Buscamos cualquier bloque que empiece con un ID de Saphirus (362...)
    # Y capturamos TODO lo que hay en la segunda columna (donde está mezclada cantidad y nombre)
    # Grupo 1: ID
    # Grupo 2: Contenido (Cant + Desc)
    patron = r'"\s*(\d[\d\s]*)\s*"\s*,\s*"\s*([^"]+)"'
    bloques = re.findall(patron, texto_limpio)
    
    datos = []
    
    for id_art, contenido in bloques:
        # Limpiamos el contenido de espacios extra
        contenido = contenido.strip()
        
        # Buscamos la cantidad con Regex dentro del contenido
        # Formato esperado: números, coma, dos números (ej: 2,00 o -1,00)
        match_cantidad = re.search(r'(-?\d+,\d{2})', contenido)
        
        if match_cantidad:
            cant_str = match_cantidad.group(1)
            # Convertir a numero
            try:
                cantidad = float(cant_str.replace(",", "."))
            except:
                cantidad = 0.0
            
            # La descripción es todo lo que NO es la cantidad
            descripcion = contenido.replace(cant_str, "").strip()
            # Limpiar basura que pueda quedar al inicio o final
            descripcion = re.sub(r'^[\s\.-]+', '', descripcion) # Quita guiones o puntos al inicio
            
            # Solo agregamos si parece un producto real (tiene letras)
            if len(descripcion) > 3:
                datos.append({
                    "Cantidad": cantidad,
                    "Producto": descripcion,
                    "ID": id_art
                })
                
    if not datos:
        return None, texto_limpio # Devolvemos texto para debug
        
    df = pd.DataFrame(datos)
    df = df[df["Cantidad"] > 0] # Filtrar devoluciones
    df["Categoria"] = df["Producto"].apply(detectar_categoria)
    
    # Agrupar
    df_final = df.groupby(["Categoria", "Producto"], as_index=False)["Cantidad"].sum()
    return df_final, texto_limpio

# --- INTERFAZ ---
st.info("Sube tu PDF para generar la lista.")
archivo = st.file_uploader("Archivo PDF", type="pdf")

if archivo:
    resultado, debug_text = procesar_pdf(archivo)
    
    if isinstance(resultado, pd.DataFrame) and not resultado.empty:
        # CASO DE ÉXITO
        st.success(f"✅ ¡Éxito! Se encontraron {len(resultado)} productos.")
        
        # Pestañas para ver tabla o mensaje
        tab1, tab2 = st.tabs(["📋 Vista Previa", "📱 Mensaje WhatsApp"])
        
        with tab1:
            st.dataframe(resultado, use_container_width=True)
            
        with tab2:
            mensaje = "📋 *PEDIDO REPOSICIÓN*\n"
            cats = resultado["Categoria"].unique()
            for c in cats:
                mensaje += f"\n*{c}*\n"
                sub = resultado[resultado["Categoria"] == c]
                for _, r in sub.iterrows():
                    cant = int(r['Cantidad']) if r['Cantidad'].is_integer() else r['Cantidad']
                    mensaje += f"▫️ {cant} x {r['Producto']}\n"
            
            st.text_area("Vista previa del mensaje:", mensaje, height=300)
            
            if st.button("Enviar ahora"):
                if not SID or not TOK:
                    st.error("Faltan credenciales de Twilio")
                else:
                    try:
                        cli = Client(SID, TOK)
                        # Enviar en trozos si es muy largo
                        if len(mensaje) > 1500:
                            mensaje = mensaje[:1500] + "\n...(recortado)"
                        cli.messages.create(body=mensaje, from_=FROM, to=TO)
                        st.balloons()
                        st.success("¡Enviado!")
                    except Exception as e:
                        st.error(f"Error: {e}")

    else:
        # CASO DE ERROR
        st.error("⚠️ No se detectaron productos.")
        with st.expander("🕵️ Ver Diagnóstico (Para arreglarlo)"):
            st.write("El sistema leyó esto del PDF (primeros 1000 caracteres):")
            st.code(debug_text[:1000])
            st.write("Si ves texto aquí pero no productos, el formato cambió radicalmente.")
