import streamlit as st
import pandas as pd
import re
from pypdf import PdfReader
from twilio.rest import Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Repositor Saphirus", page_icon="📦", layout="centered")

st.title("📦 Repositor Saphirus")
st.markdown(
    "Sube el PDF de ventas y recibe tu lista de reposición ordenada en WhatsApp."
)

# --- BARRA LATERAL: CREDENCIALES ---
# En Streamlit Cloud, esto se configura en "Secrets", pero para probar local lo dejamos así.
with st.sidebar:
    st.header("🔐 Configuración Twilio")
    TWILIO_SID = st.text_input("Account SID", type="password")
    TWILIO_TOKEN = st.text_input("Auth Token", type="password")
    TWILIO_FROM = st.text_input("Desde (Twilio)", placeholder="whatsapp:+1415...")
    TWILIO_TO = st.text_input("Para (Tu Celular)", placeholder="whatsapp:+549...")


# --- FUNCIÓN 1: CATEGORIZAR ---
def detectar_categoria(producto):
    nombre = producto.upper()
    if "TEXTIL" in nombre:
        return "👕 Textiles"
    if "AEROSOL" in nombre:
        return "💨 Aerosoles"
    if "DIFUSOR" in nombre or "VARILLA" in nombre:
        return "🎍 Difusores"
    if "SAHUMERIO" in nombre:
        return "🧘 Sahumerios"
    if "AUTO" in nombre or "RUTA" in nombre or "CARITAS" in nombre:
        return "🚗 Autos"
    if "ACEITE" in nombre:
        return "Aceite"
    if "PERFUME" in nombre:
        return "Perfume"
    if "APARATO" in nombre:
        return "Aparato"
    return "📦 Varios"


# --- FUNCIÓN 2: PROCESAMIENTO ---
def procesar_pdf(archivo_pdf):
    # 1. Leer PDF y unificar texto
    reader = PdfReader(archivo_pdf)
    texto_completo = ""
    for page in reader.pages:
        texto_completo += page.extract_text() + "\n"

    # 2. Limpiar saltos de línea para facilitar Regex
    texto_limpio = texto_completo.replace("\n", " ")

    # 3. Regex (El Ojo Digital)
    # Busca: ID(8 digitos) -> Cantidad -> Descripción
    patron = r'"\d{8}","([-0-9,]+)\s+([^"]+)"'
    coincidencias = re.findall(patron, texto_limpio)

    if not coincidencias:
        return None

    # 4. Pandas (El Cerebro)
    df = pd.DataFrame(coincidencias, columns=["Cantidad", "Producto"])

    # Limpieza numérica: "2,00" -> 2.0
    df["Cantidad"] = df["Cantidad"].apply(lambda x: float(x.replace(",", ".")))

    # Filtrar devoluciones o ceros
    df = df[df["Cantidad"] > 0]

    # Crear columna Categoría
    df["Categoria"] = df["Producto"].apply(detectar_categoria)

    # Agrupar y Sumar (La Magia)
    df_final = df.groupby(["Categoria", "Producto"], as_index=False)["Cantidad"].sum()

    return df_final


# --- FUNCIÓN 3: ENVIAR WHATSAPP ---
def enviar_mensaje(texto):
    if not TWILIO_SID or not TWILIO_TOKEN:
        return False, "Faltan credenciales"
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        msg = client.messages.create(body=texto, from_=TWILIO_FROM, to=TWILIO_TO)
        return True, msg.sid
    except Exception as e:
        return False, str(e)


# --- INTERFAZ PRINCIPAL (EL FLUJO) ---
archivo = st.file_uploader("Cargar Reporte PDF", type="pdf")

if archivo:
    with st.spinner("Procesando datos inteligentes..."):
        df_resultado = procesar_pdf(archivo)

        if df_resultado is not None and not df_resultado.empty:
            st.success("✅ PDF Procesado con éxito")

            # Visualizar en pantalla
            st.dataframe(df_resultado, use_container_width=True)

            # Preparar texto para WhatsApp
            mensaje_final = "📋 *LISTA DE REPOSICIÓN*\n"
            categorias = df_resultado["Categoria"].unique()

            for cat in categorias:
                mensaje_final += f"\n*{cat}*\n"
                # Filtramos solo los productos de esta categoría
                items = df_resultado[df_resultado["Categoria"] == cat]
                for _, fila in items.iterrows():
                    cant = (
                        int(fila["Cantidad"])
                        if fila["Cantidad"].is_integer()
                        else fila["Cantidad"]
                    )
                    mensaje_final += f"▫️ {cant} x {fila['Producto']}\n"

            st.info(f"Se detectaron {len(df_resultado)} artículos únicos para reponer.")

            if st.button("🚀 Enviar a mi Celular"):
                ok, resp = enviar_mensaje(mensaje_final)
                if ok:
                    st.balloons()
                    st.success("¡Enviado! Revisa WhatsApp.")
                else:
                    st.error(f"Error: {resp}")
        else:
            st.error("No se encontraron productos. Revisa el formato del PDF.")

