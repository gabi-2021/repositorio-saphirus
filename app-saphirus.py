import streamlit as st
import pandas as pd
import re
import requests
from pypdf import PdfReader
from twilio.rest import Client

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Repositor Saphirus", page_icon="✨", layout="centered")
st.title("✨ Repositor Saphirus 8.0")

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

# --- LÓGICA DE TEXTO Y CATEGORÍAS ---
def detectar_categoria(producto):
    p = producto.upper()
    # Categorías Específicas
    if "PREMIUM" in p and ("DIFUSOR" in p or "VARILLA" in p): return "💎 Difusores Premium"
    if "AMBAR" in p: return "🔸 Línea Ambar"
    if "TEXTIL" in p: return "👕 Textiles"
    if "AEROSOL" in p: return "💨 Aerosoles"
    if "DIFUSOR" in p or "VARILLA" in p: return "🎍 Difusores"
    if "SAHUMERIO" in p: return "🧘 Sahumerios"
    if "AUTO" in p or "RUTA" in p or "TOUCH" in p: return "🚗 Autos"
    if "VELA" in p: return "🕯️ Velas"
    if "HOME" in p: return "🏠 Home Spray"
    return "📦 Varios"

def limpiar_nombre_visual(nombre):
    """
    Elimina los prefijos repetitivos para dejar la lista limpia.
    Ej: 'DIFUSOR AROMATICO - INVICTO' -> 'INVICTO'
    """
    # Lista de frases a borrar (Regex insensible a mayúsculas)
    patrones = [
        r"^DIFUSOR AROMATICO\s*[-–]?\s*",
        r"^DIFUSOR PREMIUM\s*[-–]?\s*",
        r"^DIFUSOR\s*[-–]?\s*",
        r"^AROMATIZADOR TEXTIL 250 ML\s*[-–]?\s*",
        r"^AROMATIZADOR TEXTIL\s*[-–]?\s*",
        r"^AEROSOL\s*[-–]?\s*",
        r"^HOME SPRAY\s*[-–]?\s*",
        r"^SAHUMERIO\s*[-–]?\s*",
        r"^VELAS SAPHIRUS X \d+ UNIDADES\s*[-–]?\s*"
    ]
    
    nombre_limpio = nombre
    for pat in patrones:
        nombre_limpio = re.sub(pat, "", nombre_limpio, flags=re.IGNORECASE)
    
    return nombre_limpio.strip()

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

    # Estrategia CSV
    patron_csv = r'"\s*(\d{8})\s*"\s*,\s*"\s*([-0-9,]+)\s+([^"]+)"'
    matches = re.findall(patron_csv, texto_limpio)
    
    if matches:
        for m in matches:
            datos.append({"ID": m[0], "Cantidad": m[1], "Producto": m[2]})
    else:
        # Estrategia Texto Plano
        patron_libre = r'(\d{8})\s+([-0-9]+,\d{2})\s+(.*?)(?=\s\d{1,3}(?:\.\d{3})*,\d{2})'
        matches = re.findall(patron_libre, texto_limpio)
        for m in matches:
            datos.append({"ID": m[0], "Cantidad": m[1], "Producto": m[2].strip()})

    if not datos: return None

    df = pd.DataFrame(datos)
    
    # Limpieza Numérica
    df["Cantidad"] = df["Cantidad"].apply(lambda x: float(x.replace(",", ".")) if isinstance(x, str) else x)
    
    # Limpieza ID fantasma
    def quitar_id(x):
        return re.sub(r'^\d{8}\s*', '', x.strip())
    df["Producto"] = df["Producto"].apply(quitar_id)
    
    # Filtrar > 0
    df = df[df["Cantidad"] > 0]
    
    # 1. Asignar Categoría
    df["Categoria"] = df["Producto"].apply(detectar_categoria)
    
    # 2. Limpiar Nombre (Para que quede bonito EN la lista)
    df["Producto"] = df["Producto"].apply(limpiar_nombre_visual)
    
    # 3. Agrupar y Sumar
    df_final = df.groupby(["Categoria", "Producto"], as_index=False)["Cantidad"].sum()
    
    return df_final

# --- INTERFAZ ---
archivo = st.file_uploader("Subir PDF", type="pdf")

if archivo:
    df_res = procesar_pdf(archivo)
    
    if df_res is not None and not df_res.empty:
        # Generar Texto Limpio
        mensaje_txt = "📋 *LISTA DE REPOSICIÓN*\n"
        cats = sorted(df_res["Categoria"].unique()) # Ordenar alfabéticamente
        
        for c in cats:
            mensaje_txt += f"\n== {c.upper()} ==\n"
            sub = df_res[df_res["Categoria"]==c]
            # Ordenar productos alfabéticamente dentro de la categoría
            sub = sub.sort_values("Producto")
            
            for _, r in sub.iterrows():
                cant = int(r['Cantidad']) if r['Cantidad'].is_integer() else r['Cantidad']
                # FORMATO LIMPIO: SIN CORCHETES
                mensaje_txt += f"{cant} x {r['Producto']}\n"
        
        total = len(df_res)
        largo_texto = len(mensaje_txt)
        st.success(f"✅ {total} artículos limpios.")
        st.text_area("Vista previa:", mensaje_txt, height=400)
        
        if st.button("🚀 Enviar a WhatsApp", type="primary"):
            if not SID or not TOK:
                st.error("Faltan credenciales")
                st.stop()
                
            client = Client(SID, TOK)
            enviado = False
            
            with st.status("Procesando envío...", expanded=True) as status:
                if largo_texto < 1500:
                    try:
                        client.messages.create(body=mensaje_txt, from_=FROM, to=TO)
                        enviado = True
                    except Exception as e: st.error(f"Error: {e}")
                else:
                    status.write("Generando archivo...")
                    link = subir_archivo_robusto(mensaje_txt)
                    if link:
                        try:
                            client.messages.create(
                                body=f"📄 *Lista Simplificada*\nDescarga: {link}",
                                from_=FROM, to=TO
                            )
                            enviado = True
                        except Exception as e: st.error(f"Error: {e}")
                    else:
                        status.write("⚠️ Falló archivo, enviando por partes...")
                        trozos = [mensaje_txt[i:i+1500] for i in range(0, len(mensaje_txt), 1500)]
                        for t in trozos:
                            client.messages.create(body=t, from_=FROM, to=TO)
                        enviado = True

            if enviado:
                st.balloons()
                st.success("¡Enviado!")

    else:
        st.error("Error leyendo PDF.")
