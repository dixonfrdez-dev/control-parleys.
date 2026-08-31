import sys
import os
from datetime import datetime, date
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from PIL import Image
import json

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

def inicializar_hojas():
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
        sheet_parleys.append_row(["Usuario", "Fecha", "Deporte/Liga", "Seleccion", "Monto", "Cuota", "Estado", "Captura_URL", "Moneda"])
    
    return sheet_users, sheet_parleys

try:
    sheet_users, sheet_parleys = inicializar_hojas()
except Exception as e:
    st.error(f"Error de conexión con Google Sheets: {e}")
    st.stop()

# --- FUNCIONES DE BASE DE DATOS ---
def obtener_usuarios():
    records = sheet_users.get_all_records()
    return pd.DataFrame(records)

def registrar_usuario(user, pwd):
    sheet_users.append_row([str(user).strip(), str(pwd).strip()])

def obtener_parleys():
    records = sheet_parleys.get_all_records()
    df = pd.DataFrame(records)
    
    columnas_requeridas = ["Usuario", "Fecha", "Deporte/Liga", "Seleccion", "Monto", "Cuota", "Estado", "Captura_URL", "Moneda"]
    
    if df.empty:
        return pd.DataFrame(columns=columnas_requeridas)
        
    for col in columnas_requeridas:
        if col not in df.columns:
            if col == "Moneda":
                df["Moneda"] = "USD"
            elif col == "Monto":
                df["Monto"] = 0.0
            elif col == "Cuota":
                df["Cuota"] = 1.00
            else:
                df[col] = ""

    df["Monto"] = pd.to_numeric(df["Monto"], errors='coerce').fillna(0.0)
    df["Cuota"] = pd.to_numeric(df["Cuota"], errors='coerce').fillna(1.00)
    
    return df

def agregar_parley(usuario, fecha, deporte, seleccion, monto, cuota, estado, captura_url="N/A", moneda="USD"):
    sheet_parleys.append_row([
        str(usuario),
        str(fecha),
        str(deporte),
        str(seleccion),
        float(monto),
        float(cuota),
        str(estado),
        str(captura_url),
        str(moneda)
    ])

def actualizar_estado_apuesta(row_index, nuevo_estado):
    sheet_parleys.update_cell(row_index, 7, str(nuevo_estado))

def eliminar_apuesta(row_index):
    sheet_parleys.delete_rows(row_index)

# --- ANALIZADOR DE IA CON GEMINI ---
def analizar_ticket_con_ia(imagen_pil):
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key:
        st.error("Falta configurar GEMINI_API_KEY en Secrets.")
        return None

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = """
        Analiza esta imagen de un ticket o captura de parley de apuestas deportivas.
        Extrae la información requerida y devuelve SOLAMENTE un objeto JSON válido:
        {
            "fecha": "YYYY-MM-DD",
            "deporte_liga": "Ej. MLB / Béisbol",
            "seleccion": "Ej. Brewers vs Rangers Under 8.5 + NY Yankees ML + BAL Orioles ML + PHI Phillies -1.5",
            "monto": 500.0,
            "cuota": 8.90,
            "moneda": "VES",
            "estado": "Ganada"
        }
        Reglas:
        - Si la cuota en el ticket es formato americano (ejemplo: +790), conviértela a decimal exacto (790/100 + 1 = 8.90).
        - "moneda": Usa "VES" si los montos dicen VES o Bs. Usa "USD" si son en dólares ($).
        - "estado": Si el ticket dice GANADO, pon "Ganada". Si dice PERDIDO, pon "Perdida". Si está activo, pon "Pendiente".
        - Devuelve únicamente el texto JSON limpio sin formato markdown.
        """
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=[imagen_pil, prompt]
        )
        txt = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(txt)
    except Exception as e:
        st.error(f"Error al procesar imagen con IA: {e}")
        return None

# --- GESTIÓN DE SESIÓN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = ""

# --- LOGIN / REGISTRO ---
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
                        st.error("El usuario ya existe.")
                    else:
                        registrar_usuario(nu_input, np_input)
                        st.success("¡Cuenta creada! Inicia sesión.")
                else:
                    st.warning("Completa todos los campos.")
    st.stop()

# --- BARRA LATERAL ---
st.sidebar.write(f"👤 **Usuario:** `{st.session_state.usuario_actual}`")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.autenticado = False
    st.session_state.usuario_actual = ""
    st.rerun()

opcion_menu = st.sidebar.radio(
    "Menú de Navegación",
    ["📊 Dashboard y Gráficos", "➕ Registrar Apuesta", "⚙️ Gestionar Historial"]
)

# Cargar apuestas
df_raw = obtener_parleys()
if not df_raw.empty and "Usuario" in df_raw.columns:
    df_user = df_raw[df_raw["Usuario"].astype(str) == st.session_state.usuario_actual].copy()
    if "Moneda" not in df_user.columns:
        df_user["Moneda"] = "USD"
    df_user["Moneda"] = df_user["Moneda"].replace("", "USD").fillna("USD")
else:
    df_user = pd.DataFrame(columns=["Usuario", "Fecha", "Deporte/Liga", "Seleccion", "Monto", "Cuota", "Estado", "Captura_URL", "Moneda"])

# --- 1. DASHBOARD ---
if opcion_menu == "📊 Dashboard y Gráficos":
    st.title("📊 Panel Estadístico y Balance")

    moneda_filtro = st.radio("Selecciona Moneda:", ["USD ($)", "VES (Bs)"], horizontal=True)
    moneda_code = "USD" if "USD" in moneda_filtro else "VES"
    simbolo = "$" if moneda_code == "USD" else "Bs"

    df_filtered = df_user[df_user["Moneda"] == moneda_code].copy() if not df_user.empty else pd.DataFrame()

    if not df_filtered.empty:
        total_jugadas = len(df_filtered)
        df_ganadas = df_filtered[df_filtered["Estado"] == "Ganada"]

        total_apostado = df_filtered["Monto"].astype(float).sum()

        def calc_lucro(row):
            e = str(row["Estado"]).strip().capitalize()
            m = float(row.get("Monto", 0))
            c = float(row.get("Cuota", 1))
            if e == "Ganada":
                return (m * c) - m
            elif e == "Perdida":
                return -m
            return 0

        df_filtered["Lucro"] = df_filtered.apply(calc_lucro, axis=1)
        balance_total = df_filtered["Lucro"].sum()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Jugadas", total_jugadas)
        col2.metric(f"Apostado ({moneda_code})", f"{simbolo} {total_apostado:,.2f}")
        col3.metric(f"Balance Net ({moneda_code})", f"{simbolo} {balance_total:,.2f}", delta=f"{balance_total:,.2f}")
        win_rate = (len(df_ganadas) / total_jugadas * 100) if total_jugadas > 0 else 0
        col4.metric("% Efectividad", f"{win_rate:.1f}%")

        st.divider()
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            df_chart = df_filtered.copy()
            df_chart["Acumulado"] = df_chart["Lucro"].cumsum()
            fig_line = px.line(df_chart, y="Acumulado", markers=True, title=f"📈 Evolución del Balance ({simbolo})", template="plotly_dark")
            fig_line.update_traces(line_color="#00CC96", line_width=3)
            st.plotly_chart(fig_line, use_container_width=True)

        with col_g2:
            df_estado = df_filtered["Estado"].value_counts().reset_index()
            df_estado.columns = ["Estado", "Cantidad"]
            fig_pie = px.pie(df_estado, names="Estado", values="Cantidad", title="🍩 Resultados", hole=0.4, template="plotly_dark")
            st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader(f"📋 Historial de Jugadas ({moneda_code})")
        st.dataframe(df_filtered.drop(columns=["Usuario"]), use_container_width=True)
    else:
        st.info(f"No hay apuestas registradas en {moneda_code}.")

# --- 2. REGISTRAR APUESTA ---
elif opcion_menu == "➕ Registrar Apuesta":
    st.title("➕ Nueva Apuesta / Parley")

    if "input_fecha" not in st.session_state:
        st.session_state.input_fecha = datetime.today().date()
    if "input_deporte" not in st.session_state:
        st.session_state.input_deporte = ""
    if "input_seleccion" not in st.session_state:
        st.session_state.input_seleccion = ""
    if "input_monto" not in st.session_state:
        st.session_state.input_monto = 10.0
    if "input_cuota" not in st.session_state:
        st.session_state.input_cuota = 2.00
    if "input_estado" not in st.session_state:
        st.session_state.input_estado = "Pendiente"
    if "input_moneda" not in st.session_state:
        st.session_state.input_moneda = "USD"

    with st.expander("🤖 Escanear captura con IA", expanded=True):
        captura_file = st.file_uploader("Sube la foto del ticket", type=["png", "jpg", "jpeg"])
        if captura_file is not None:
            if st.button("🔍 Escanear Ticket"):
                with st.spinner("Analizando ticket..."):
                    img = Image.open(captura_file)
                    datos = analizar_ticket_con_ia(img)
                    if datos:
                        if datos.get("fecha"):
                            try:
                                st.session_state.input_fecha = datetime.strptime(datos.get("fecha"), "%Y-%m-%d").date()
                            except Exception:
                                pass
                        st.session_state.input_deporte = datos.get("deporte_liga", "MLB")
                        st.session_state.input_seleccion = datos.get("seleccion", "")
                        st.session_state.input_monto = float(datos.get("monto", 10.0))
                        st.session_state.input_cuota = float(datos.get("cuota", 2.00))
                        st.session_state.input_estado = datos.get("estado", "Pendiente")
                        st.session_state.input_moneda = str(datos.get("moneda", "USD")).upper()
                        st.success("¡Datos extraídos! Verifica los campos abajo.")
                        st.rerun()

    with st.form("form_registro_parley"):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            fecha_val = st.date_input("Fecha", value=st.session_state.input_fecha)
            deporte_val = st.text_input("Deporte / Liga", value=st.session_state.input_deporte)
            seleccion_val = st.text_area("Selección / Logros", value=st.session_state.input_seleccion)

        with col_f2:
            moneda_opts = ["USD ($)", "VES (Bs)"]
            idx_m = 1 if st.session_state.input_moneda == "VES" else 0
            moneda_val = st.selectbox("Moneda", moneda_opts, index=idx_m)
            monto_val = st.number_input("Monto Apostado", min_value=0.01, step=1.0, value=float(st.session_state.input_monto), format="%.2f")
            cuota_val = st.number_input("Cuota Total (Decimal)", min_value=1.01, step=0.05, value=float(st.session_state.input_cuota), format="%.2f")
            
            estado_opts = ["Pendiente", "Ganada", "Perdida"]
            idx_e = estado_opts.index(st.session_state.input_estado) if st.session_state.input_estado in estado_opts else 0
            estado_val = st.selectbox("Estado", estado_opts, index=idx_e)

        btn_guardar = st.form_submit_button("💾 Guardar en Google Sheets")

        if btn_guardar:
            if deporte_val and seleccion_val:
                moneda_code = "VES" if "VES" in moneda_val else "USD"
                cap_name = f"Captura: {captura_file.name}" if captura_file is not None else "N/A"
                
                agregar_parley(
                    st.session_state.usuario_actual,
                    fecha_val.strftime("%Y-%m-%d"),
                    deporte_val,
                    seleccion_val,
                    monto_val,
                    cuota_val,
                    estado_val,
                    cap_name,
                    moneda_code
                )
                
                st.session_state.input_deporte = ""
                st.session_state.input_seleccion = ""
                st.session_state.input_monto = 10.0
                st.session_state.input_cuota = 2.00
                st.session_state.input_estado = "Pendiente"
                
                st.success("¡Apuesta registrada correctamente en Google Sheets!")
                st.rerun()
            else:
                st.warning("Completa la información del Deporte y los Logros.")

# --- 3. GESTIONAR HISTORIAL ---
elif opcion_menu == "⚙️ Gestionar Historial":
    st.title("⚙️ Editar o Eliminar Apuestas")

    df_actual = obtener_parleys()
    if not df_actual.empty and "Usuario" in df_actual.columns:
        df_user_hist = df_actual[df_actual["Usuario"].astype(str) == st.session_state.usuario_actual].reset_index()
    else:
        df_user_hist = pd.DataFrame()

    if not df_user_hist.empty:
        opciones = {}
        for idx, row in df_user_hist.iterrows():
            sheet_row_num = int(row["index"]) + 2
            mon_sym = "Bs" if str(row.get('Moneda', 'USD')) == "VES" else "$"
            label = f"Fila #{sheet_row_num} | {row.get('Fecha')} - {row.get('Deporte/Liga')} ({mon_sym}{row.get('Monto')}) [{row.get('Estado')}]"
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
            if st.button("🔴 Eliminar Definitivamente"):
                eliminar_apuesta(row_target)
                st.success("Apuesta eliminada.")
                st.rerun()
    else:
        st.info("No tienes apuestas en el historial para modificar.")
