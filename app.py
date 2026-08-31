import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
from google import genai
from PIL import Image
import json

# ---------------------------------------------------------
# Configuración de la Página
# ---------------------------------------------------------
st.set_page_config(
    page_title="Control de Parleys",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# Sistema de Autenticación de Usuarios
# ---------------------------------------------------------
# Si deseas cambiar o agregar usuarios, puedes hacerlo aquí
USUARIOS = {
    "admin": "1234",
    "parley": "parley2026"
}

def login():
    st.title("🔐 Inicio de Sesión - Control de Parleys")
    
    with st.form("form_login"):
        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Ingresar")
        
        if submit:
            if usuario in USUARIOS and USUARIOS[usuario] == password:
                st.session_state["autenticado"] = True
                st.session_state["usuario_actual"] = usuario
                st.success(f"¡Bienvenido, {usuario}!")
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    login()
    st.stop()

# ---------------------------------------------------------
# Barra Lateral (Sidebar)
# ---------------------------------------------------------
st.sidebar.title(f"👤 {st.session_state.get('usuario_actual', 'Usuario')}")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state["autenticado"] = False
    st.rerun()

st.sidebar.divider()

# ---------------------------------------------------------
# Conexión a Google Sheets
# ---------------------------------------------------------
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")

def cargar_datos():
    try:
        df = conn.read(ttl="0s")
        if df.empty:
            return pd.DataFrame(columns=[
                "Fecha", "Deporte/Liga", "Selección", "Monto", "Cuota", 
                "Ganancia Potencial", "Moneda", "Estado", "Retorno"
            ])
        return df
    except Exception:
        return pd.DataFrame(columns=[
            "Fecha", "Deporte/Liga", "Selección", "Monto", "Cuota", 
            "Ganancia Potencial", "Moneda", "Estado", "Retorno"
        ])

df_apuestas = cargar_datos()

# ---------------------------------------------------------
# Función para procesar tickets con IA (Gemini 1.5 Flash)
# ---------------------------------------------------------
def analizar_ticket_con_ia(imagen_pil):
    """Extrae los datos de la captura del parley utilizando Gemini."""
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key:
        st.error("Falta configurar la GEMINI_API_KEY en los Secrets de Streamlit.")
        return None

    try:
        client = genai.Client(api_key=api_key)
        prompt = """
        Analiza esta imagen de un ticket o captura de apuesta deportiva/parley.
        Extrae la información requerida y responde EXCLUSIVAMENTE con un objeto JSON válido con la siguiente estructura:
        {
            "deporte_liga": "Ej: MLB / Champions League / NBA / Fútbol",
            "seleccion": "Ej: Real Madrid ML + Yankees Gana (resumen de los logros/juegos)",
            "monto": 10.0,
            "cuota": 2.50,
            "moneda": "USD",
            "estado": "Pendiente"
        }
        Reglas:
        - "monto" y "cuota" deben ser números (floats/decimales).
        - "moneda" debe ser "USD" si es en dólares ($) o "VES" si es en bolívares (Bs / Bs.D). Si no estás seguro, usa "USD".
        - "estado" debe ser una de estas opciones exactamente: "Pendiente", "Ganada", "Perdida".
        - Responde únicamente el texto JSON limpio, sin bloques de código ni explicaciones adicionales.
        """
        
        # Uso del modelo gemini-1.5-flash
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[imagen_pil, prompt]
        )
        
        txt = response.text.strip()
        if txt.startswith("```json"):
            txt = txt.replace("```json", "").replace("```", "").strip()
        elif txt.startswith("```"):
            txt = txt.replace("```", "").strip()
            
        return json.loads(txt)
    except Exception as e:
        st.error(f"Error al procesar la imagen con IA: {e}")
        return None

# ---------------------------------------------------------
# Interfaz Principal
# ---------------------------------------------------------
st.title("⚽ Dashboard & Control de Parleys")

# Inicializar estado para autocompletar campos con IA
if "datos_ia" not in st.session_state:
    st.session_state.datos_ia = {}

# Métricas Principales
if not df_apuestas.empty and "Monto" in df_apuestas.columns:
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    
    total_apuestas = len(df_apuestas)
    total_invertido = pd.to_numeric(df_apuestas["Monto"], errors="coerce").sum()
    
    ganadas = df_apuestas[df_apuestas["Estado"] == "Ganada"]
    perdidas = df_apuestas[df_apuestas["Estado"] == "Perdida"]
    pendientes = df_apuestas[df_apuestas["Estado"] == "Pendiente"]
    
    total_retorno = pd.to_numeric(df_apuestas["Retorno"], errors="coerce").sum()
    balance_neto = total_retorno - total_invertido
    
    col_m1.metric("Total Jugadas", total_apuestas)
    col_m2.metric("Total Invertido", f"${total_invertido:.2f}")
    col_m3.metric("Balance Neto", f"${balance_neto:.2f}", delta=f"{balance_neto:.2f}")
    col_m4.metric("Pendientes", len(pendientes))
    
st.divider()

# ---------------------------------------------------------
# Sección: Registrar Nueva Apuesta
# ---------------------------------------------------------
st.header("📝 Nueva Apuesta / Parley")

with st.expander("👁️ Escanear captura con IA para autocompletar campos"):
    archivo_subido = st.file_uploader("Sube la foto/captura de tu ticket", type=["jpg", "jpeg", "png"])
    if archivo_subido is not None:
        if st.button("🔍 Escanear y Extraer Datos"):
            with st.spinner("Analizando ticket con Gemini..."):
                imagen = Image.open(archivo_subido)
                datos = analizar_ticket_con_ia(imagen)
                if datos:
                    st.session_state.datos_ia = datos
                    st.success("¡Datos extraídos con éxito! Revisa los campos abajo.")

# Formulario de registro
with st.form("form_apuesta", clear_on_submit=True):
    col_f1, col_f2 = st.columns(2)
    
    with col_f1:
        fecha = st.date_input("Fecha de la Jugada", datetime.now())
        deporte = st.text_input(
            "Deporte / Liga", 
            value=st.session_state.datos_ia.get("deporte_liga", ""),
            placeholder="Ej. MLB, Champions League, NBA"
        )
    
    with col_f2:
        moneda = st.selectbox(
            "Moneda", 
            ["USD", "VES"], 
            index=0 if st.session_state.datos_ia.get("moneda") != "VES" else 1
        )
        estado = st.selectbox(
            "Estado Inicial", 
            ["Pendiente", "Ganada", "Perdida"],
            index=["Pendiente", "Ganada", "Perdida"].index(st.session_state.datos_ia.get("estado", "Pendiente")) if st.session_state.datos_ia.get("estado") in ["Pendiente", "Ganada", "Perdida"] else 0
        )

    seleccion = st.text_area(
        "Selección / Logros", 
        value=st.session_state.datos_ia.get("seleccion", ""),
        placeholder="Ej. Real Madrid Gana + Yankees ML"
    )

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        monto = st.number_input(
            "Monto Apostado", 
            min_value=0.0, 
            step=1.0, 
            value=float(st.session_state.datos_ia.get("monto", 0.0))
        )
    with col_m2:
        cuota = st.number_input(
            "Cuota / Logro Total", 
            min_value=1.0, 
            step=0.05, 
            value=float(st.session_state.datos_ia.get("cuota", 1.0))
        )

    ganancia_potencial = round(monto * cuota, 2)
    st.info(f"💡 **Ganancia Potencial estimada:** {ganancia_potencial} {moneda}")

    boton_guardar = st.form_submit_button("💾 Guardar Apuesta")

    if boton_guardar:
        if monto <= 0:
            st.warning("El monto apostado debe ser mayor a 0.")
        elif not seleccion.strip():
            st.warning("Escribe la selección o los logros de la jugada.")
        else:
            retorno = 0.0
            if estado == "Ganada":
                retorno = ganancia_potencial
            elif estado == "Perdida":
                retorno = 0.0

            nueva_fila = pd.DataFrame([{
                "Fecha": fecha.strftime("%Y-%m-%d"),
                "Deporte/Liga": deporte,
                "Selección": seleccion,
                "Monto": monto,
                "Cuota": cuota,
                "Ganancia Potencial": ganancia_potencial,
                "Moneda": moneda,
                "Estado": estado,
                "Retorno": retorno
            }])

            df_actualizado = pd.concat([df_apuestas, nueva_fila], ignore_index=True)
            conn.update(data=df_actualizado)
            st.session_state.datos_ia = {}
            st.success("¡Apuesta registrada exitosamente!")
            st.rerun()

# ---------------------------------------------------------
# Sección: Historial de Apuestas
# ---------------------------------------------------------
st.divider()
st.header("📊 Historial de Apuestas Registradas")

if not df_apuestas.empty:
    st.dataframe(df_apuestas, use_container_width=True)
else:
    st.info("No hay apuestas registradas aún en la hoja de cálculo.")
