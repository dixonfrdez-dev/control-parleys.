import sys
import os
from datetime import datetime
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from PIL import Image
import json

# --- INTELIGENCIA ARTIFICIAL (GEMINI) PARA LEER TICKETS ---
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Sistema de Control de Parleys",
    page_icon="⚽",
    layout="wide"
)

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def get_gspread_client():
    creds_dict = st.secrets["connections"]["gsheets"]
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(credentials)
    url = creds_dict["spreadsheet"]
    sh = client.open_by_url(url)
    return sh

try:
    sh = get_gspread_client()
    try:
        sheet_users = sh.worksheet("Usuarios")
    except Exception:
        sheet_users = sh.add_worksheet(title="Usuarios", rows="100", cols="5")
        sheet_users.append_row(["usuario", "clave"])

    try:
        sheet_parleys = sh.worksheet("Parleys")
    except Exception:
        sheet_parleys = sh.add_worksheet(title="Parleys", rows="1000", cols="10")
        sheet_parleys.append_row(["Usuario", "Fecha", "Deporte/Liga", "Seleccion", "Monto", "Cuota", "Estado", "Captura_URL"])
except Exception as e:
    st.error(f"Error de conexión con Google Sheets: {e}")
    st.stop()

# --- FUNCIONES DE LECTURA DE CAPTURAS CON IA ---
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
        Extrae la información requerida y responde EXCLUSIVAMENTE con un objeto JSON valido con la siguiente estructura:
        {
            "deporte_liga": "Ej: MLB / Champions League / NBA / Fútbol",
            "seleccion": "Ej: Real Madrid ML + Yankees Gana (resumen de los logros/juegos)",
            "monto": 10.0,
            "cuota": 2.50,
            "estado": "Pendiente"
        }
        Reglas:
        - "monto" y "cuota" deben ser números (floats).
        - "estado" debe ser una de estas opciones exactamente: "Pendiente", "Ganada", "Perdida".
        - Responde únicamente el formato JSON sin explicaciones adicionales.
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[imagen_pil, prompt]
        )
        
        # Limpieza básica del JSON
        txt = response.text.strip()
        if txt.startswith("```json"):
            txt = txt.replace("```json", "").replace("```", "").strip()
        elif txt.startswith("```"):
            txt = txt.replace("```", "").strip()
            
        return json.loads(txt)
    except Exception as e:
        st.error(f"Error al procesar la imagen con IA: {e}")
        return None

# --- FUNCIONES DE BASE DE DATOS ---
def obtener_usuarios():
    records = sheet_users.get_all_records()
    return pd.DataFrame(records)

def registrar_usuario(user, pwd):
    sheet_users.append_row([user.strip(), pwd.strip()])

def obtener_parleys():
    records = sheet_parleys.get_all_records()
    return pd.DataFrame(records)

def agregar_parley(usuario, fecha, deporte, seleccion, monto, cuota, estado, captura_url="N/A"):
    sheet_parleys.append_row([usuario, str(fecha), deporte, seleccion, float(monto), float(cuota), estado, captura_url])

def actualizar_estado_apuesta(row_index, nuevo_estado):
    sheet_parleys.update_cell(row_index, 7, nuevo_estado)

def eliminar_apuesta(row_index):
    sheet_parleys.delete_rows(row_index)

# --- GESTIÓN DE SESIÓN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = ""

# --- PANTALLA DE LOGIN / REGISTRO ---
if not st.session_state.autenticado:
    st.title("⚽ Control de Parleys y Apuestas")
    tab_login, tab_registro = st.tabs(["🔐 Iniciar Sesión", "📝 Registrarse"])

    with tab_login:
        with st.form("form_login"):
            u_input = st.text_input("Usuario").strip()
            p_input = st.text_input("Contraseña", type="password").strip()
            btn_login = st.form_submit_button("Ingresar")

            if btn_login:
                df_u = obtener_usuarios()
                if not df_u.empty and "usuario" in df_u.columns and "clave" in df_u.columns:
                    user_match = df_u[(df_u["usuario"].astype(str) == u_input) & (df_u["clave"].astype(str) == p_input)]
                    if not user_match.empty:
                        st.session_state.autenticado = True
                        st.session_state.usuario_actual = u_input
                        st.success("¡Bienvenido!")
                        st.rerun()
                    else:
                        st.error("Usuario o contraseña incorrectos.")
                else:
                    st.error("No hay usuarios registrados aún.")

    with tab_registro:
        with st.form("form_reg"):
            nu_input = st.text_input("Nuevo Usuario").strip()
            np_input = st.text_input("Nueva Contraseña", type="password").strip()
            btn_reg = st.form_submit_button("Crear cuenta")

            if btn_reg:
                if nu_input and np_input:
                    df_u = obtener_usuarios()
                    if not df_u.empty and "usuario" in df_u.columns and nu_input in df_u["usuario"].astype(str).values:
                        st.error("El usuario ya existe. Elige otro nombre.")
                    else:
                        registrar_usuario(nu_input, np_input)
                        st.success("¡Cuenta creada con éxito! Ahora inicia sesión.")
                else:
                    st.warning("Por favor completa todos los campos.")
    st.stop()

# --- MENÚ LATERAL ---
st.sidebar.write(f"👤 **Usuario:** `{st.session_state.usuario_actual}`")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.autenticado = False
    st.session_state.usuario_actual = ""
    st.rerun()

opcion_menu = st.sidebar.radio(
    "Menú de Navegación",
    ["📊 Dashboard y Gráficos", "➕ Registrar Apuesta", "⚙️ Gestionar Historial"]
)

# Cargar apuestas globales
df_raw = obtener_parleys()
if not df_raw.empty and "Usuario" in df_raw.columns:
    df_user = df_raw[df_raw["Usuario"].astype(str) == st.session_state.usuario_actual].copy()
else:
    df_user = pd.DataFrame(columns=["Usuario", "Fecha", "Deporte/Liga", "Seleccion", "Monto", "Cuota", "Estado", "Captura_URL"])

# --- 1. DASHBOARD Y GRÁFICOS ---
if opcion_menu == "📊 Dashboard y Gráficos":
    st.title("📊 Panel Estadístico y Balance")
    
    if not df_user.empty:
        total_jugadas = len(df_user)
        df_ganadas = df_user[df_user["Estado"] == "Ganada"]
        df_perdidas = df_user[df_user["Estado"] == "Perdida"]

        total_apostado = df_user["Monto"].astype(float).sum()
        
        def calc_lucro(row):
            e = str(row["Estado"]).strip().capitalize()
            m = float(row.get("Monto", 0))
            c = float(row.get("Cuota", 1))
            if e == "Ganada":
                return (m * c) - m
            elif e == "Perdida":
                return -m
            return 0

        df_user["Lucro"] = df_user.apply(calc_lucro, axis=1)
        balance_total = df_user["Lucro"].sum()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Jugadas", total_jugadas)
        col2.metric("Total Apostado", f"${total_apostado:.2f}")
        col3.metric("Ganancias / Pérdidas", f"${balance_total:.2f}", delta=f"{balance_total:.2f}")
        
        win_rate = (len(df_ganadas) / total_jugadas * 100) if total_jugadas > 0 else 0
        col4.metric("% Efectividad", f"{win_rate:.1f}%")

        st.divider()

        col_g1, col_g2 = st.columns(2)

        with col_g1:
            df_chart = df_user.copy()
            df_chart["Acumulado"] = df_chart["Lucro"].cumsum()
            fig_line = px.line(
                df_chart,
                y="Acumulado",
                markers=True,
                title="📈 Evolución del Balance ($)",
                labels={"Acumulado": "Balance Net ($)", "index": "N° de Apuesta"},
                template="plotly_dark"
            )
            fig_line.update_traces(line_color="#00CC96", line_width=3)
            st.plotly_chart(fig_line, use_container_width=True)

        with col_g2:
            df_estado = df_user["Estado"].value_counts().reset_index()
            df_estado.columns = ["Estado", "Cantidad"]
            fig_pie = px.pie(
                df_estado,
                names="Estado",
                values="Cantidad",
                title="🍩 Distribución de Resultados",
                color="Estado",
                color_discrete_map={"Ganada": "#00CC96", "Perdida": "#EF553B", "Pendiente": "#FECB52"},
                hole=0.4,
                template="plotly_dark"
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("📋 Historial Reciente")
        st.dataframe(df_user.drop(columns=["Usuario"]), use_container_width=True)

    else:
        st.info("No tienes apuestas registradas. Ve a '➕ Registrar Apuesta' para comenzar.")

# --- 2. REGISTRAR APUESTA (CON AUTO-COMPLETADO POR IA) ---
elif opcion_menu == "➕ Registrar Apuesta":
    st.title("➕ Nueva Apuesta / Parley")

    # Inicializar estado del formulario
    if "auto_deporte" not in st.session_state:
        st.session_state.auto_deporte = ""
    if "auto_seleccion" not in st.session_state:
        st.session_state.auto_seleccion = ""
    if "auto_monto" not in st.session_state:
        st.session_state.auto_monto = 10.0
    if "auto_cuota" not in st.session_state:
        st.session_state.auto_cuota = 2.00
    if "auto_estado" not in st.session_state:
        st.session_state.auto_estado = "Pendiente"

    # Sección para subir captura y auto-completar
    with st.expander("🤖 Escanear captura con IA para autocompletar campos", expanded=True):
        captura_file = st.file_uploader("Sube la foto/captura de tu ticket", type=["png", "jpg", "jpeg"])
        if captura_file is not None:
            if st.button("🔍 Escanear y Extraer Datos"):
                with st.spinner("Analizando la imagen con IA..."):
                    img = Image.open(captura_file)
                    datos = analizar_ticket_con_ia(img)
                    if datos:
                        st.session_state.auto_deporte = datos.get("deporte_liga", "")
                        st.session_state.auto_seleccion = datos.get("seleccion", "")
                        st.session_state.auto_monto = float(datos.get("monto", 10.0))
                        st.session_state.auto_cuota = float(datos.get("cuota", 2.00))
                        st.session_state.auto_estado = datos.get("estado", "Pendiente")
                        st.success("¡Campos extraídos y completados automáticamente!")
                        st.rerun()

    # Formulario de registro de apuesta
    with st.form("form_nueva_apuesta"):
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            fecha = st.date_input("Fecha de la Jugada", datetime.now())
            deporte = st.text_input("Deporte / Liga", value=st.session_state.auto_deporte, placeholder="Ej. MLB, Champions League, NBA")
            seleccion = st.text_area("Selección / Logros", value=st.session_state.auto_seleccion, placeholder="Ej. Real Madrid Gana + Yankees ML")
        
        with col_f2:
            monto = st.number_input("Monto Apostado ($)", min_value=0.1, step=1.0, value=st.session_state.auto_monto)
            cuota = st.number_input("Cuota / Logro Total", min_value=1.01, step=0.05, value=st.session_state.auto_cuota)
            
            # Mapeo de estado para la selección por defecto
            opciones_estado = ["Pendiente", "Ganada", "Perdida"]
            idx_est = opciones_estado.index(st.session_state.auto_estado) if st.session_state.auto_estado in opciones_estado else 0
            estado = st.selectbox("Estado Inicial", opciones_estado, index=idx_est)

        btn_guardar = st.form_submit_button("💾 Guardar Apuesta")

        if btn_guardar:
            if deporte and seleccion:
                captura_nombre = f"Imagen: {captura_file.name}" if captura_file is not None else "N/A"
                
                agregar_parley(
                    st.session_state.usuario_actual,
                    fecha,
                    deporte,
                    seleccion,
                    monto,
                    cuota,
                    estado,
                    captura_nombre
                )
                st.success("¡Apuesta registrada exitosamente en Google Sheets!")
                
                # Limpiar autocompletado
                st.session_state.auto_deporte = ""
                st.session_state.auto_seleccion = ""
                st.session_state.auto_monto = 10.0
                st.session_state.auto_cuota = 2.00
                st.session_state.auto_estado = "Pendiente"
                st.rerun()
            else:
                st.warning("Por favor completa el deporte y los logros de la jugada.")

# --- 3. GESTIONAR HISTORIAL ---
elif opcion_menu == "⚙️ Gestionar Historial":
    st.title("⚙️ Editar o Eliminar Apuestas")

    if not df_user.empty:
        df_raw_reset = df_raw.reset_index()
        df_user_indexed = df_raw_reset[df_raw_reset["Usuario"].astype(str) == st.session_state.usuario_actual]

        opciones = {}
        for idx, row in df_user_indexed.iterrows():
            sheet_row_num = int(row["index"]) + 2
            label = f"Fila #{sheet_row_num} | {row.get('Fecha')} - {row.get('Deporte/Liga')} ({row.get('Monto')}$) [{row.get('Estado')}]"
            opciones[label] = sheet_row_num

        apuesta_sel = st.selectbox("Selecciona la apuesta a modificar:", options=list(opciones.keys()))
        row_target = opciones[apuesta_sel]

        col_act1, col_act2 = st.columns(2)

        with col_act1:
            st.subheader("✏️ Actualizar Estado")
            nuevo_est = st.radio("Nuevo Estado:", ["Ganada", "Perdida", "Pendiente"])
            if st.button("Guardar Nuevo Estado"):
                actualizar_estado_apuesta(row_target, nuevo_est)
                st.success("Estado actualizado.")
                st.rerun()

        with col_act2:
            st.subheader("🗑️ Eliminar Apuesta")
            st.write("Esta acción borrará el registro de tu hoja de cálculo.")
            if st.button("🔴 Eliminar Definitivamente"):
                eliminar_apuesta(row_target)
                st.success("Apuesta eliminada.")
                st.rerun()
    else:
        st.info("No tienes apuestas en el historial para modificar.")
