import sys
import os
from datetime import datetime

# Desactivar aceleraciones de hardware para estabilidad en Windows
os.environ["NPY_DISABLE_CPU_FEATURES"] = "X86_V2,AVX2,FMA3"
os.environ["STREAMLIT_WATCH_MODULES"] = "false"

import streamlit as st
import gspread

st.set_page_config(page_title="Control de Parleys", layout="wide", page_icon="⚽")

# Inicializar estados de sesión
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = ""

# Conexión nativa a Google Sheets
@st.cache_resource
def conectar_gsheets():
    try:
        cred_dict = dict(st.secrets["connections"]["gsheets"])
        if "private_key" in cred_dict:
            cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
            
        gc = gspread.service_account_from_dict(cred_dict)
        sh = gc.open_by_url(cred_dict["spreadsheet"])
        return sh
    except Exception as e:
        st.error(f"Error de conexión con Google Sheets: {e}")
        return None

sh = conectar_gsheets()

# Función para obtener o crear una hoja específica
def obtener_hoja(nombre_hoja, encabezados):
    if not sh:
        return None
    try:
        sheet = sh.worksheet(nombre_hoja)
    except gspread.WorksheetNotFound:
        sheet = sh.add_worksheet(title=nombre_hoja, rows="1000", cols="10")
        sheet.append_row(encabezados)
    return sheet

sheet_usuarios = obtener_hoja("Usuarios", ["usuario", "clave"])
sheet_parleys = obtener_hoja("Parleys", ["usuario", "fecha", "deporte", "descripcion", "monto", "cuota", "estado", "retorno"])

# ==============================================================================
# PANTALLA PRINCIPAL (SISTEMA DE CONTROL)
# ==============================================================================
if st.session_state.logged_in:
    usuario_actual = st.session_state.usuario_actual

    # Barra lateral
    st.sidebar.title("⚽ Control de Parleys")
    st.sidebar.write(f"Usuario: **{usuario_actual}**")
    
    opcion_menu = st.sidebar.radio("Navegación", ["📊 Dashboard / Estadísticas", "➕ Registrar Apuesta", "📋 Historial de Jugadas"])
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logged_in = False
        st.session_state.usuario_actual = ""
        st.rerun()

    # Cargar datos del usuario
    registros_usuario = []
    if sheet_parleys:
        try:
            todas_filas = sheet_parleys.get_all_values()
            if len(todas_filas) > 1:
                for fila in todas_filas[1:]:
                    if len(fila) >= 8 and fila[0].strip() == usuario_actual:
                        registros_usuario.append({
                            "fecha": fila[1],
                            "deporte": fila[2],
                            "descripcion": fila[3],
                            "monto": float(fila[4]) if fila[4] else 0.0,
                            "cuota": float(fila[5]) if fila[5] else 0.0,
                            "estado": fila[6],
                            "retorno": float(fila[7]) if fila[7] else 0.0
                        })
        except Exception as e:
            st.error(f"Error al cargar historial: {e}")

    # --- OPCIÓN 1: DASHBOARD DE ESTADÍSTICAS ---
    if opcion_menu == "📊 Dashboard / Estadísticas":
        st.title(f"📊 Panel General - {usuario_actual}")
        
        total_apuestas = len(registros_usuario)
        total_invertido = sum(r["monto"] for r in registros_usuario)
        total_ganado = sum(r["retorno"] for r in registros_usuario if r["estado"] == "Ganado")
        balance_neto = total_ganado - total_invertido
        
        ganadas = len([r for r in registros_usuario if r["estado"] == "Ganado"])
        perdidas = len([r for r in registros_usuario if r["estado"] == "Perdido"])
        pendientes = len([r for r in registros_usuario if r["estado"] == "Pendiente"])
        
        efectividad = (ganadas / (ganadas + perdidas) * 100) if (ganadas + perdidas) > 0 else 0.0

        # Tarjetas de resumen
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Invertido", f"${total_invertido:.2f}")
        col2.metric("Total Retorno", f"${total_ganado:.2f}")
        col3.metric("Balance Neto", f"${balance_neto:.2f}", delta=f"{balance_neto:.2f}")
        col4.metric("Efectividad", f"{efectividad:.1f}%")

        st.markdown("---")
        
        st.subheader("📈 Resumen de Resultados")
        c1, c2, c3 = st.columns(3)
        c1.info(f"🟢 **Ganadas:** {ganadas}")
        c2.error(f"🔴 **Perdidas:** {perdidas}")
        c3.warning(f"🟡 **Pendientes:** {pendientes}")

    # --- OPCIÓN 2: REGISTRAR APUESTA ---
    elif opcion_menu == "➕ Registrar Apuesta":
        st.title("➕ Registrar Nuevo Parley / Jugada")
        
        with st.form("form_parley"):
            fecha = st.date_input("Fecha de la jugada", datetime.now())
            deporte = st.selectbox("Deporte / Liga", ["Fútbol", "Béisbol (MLB)", "Baloncesto (NBA)", "NFL", "Tenis", "Otro"])
            descripcion = st.text_area("Detalle de los logros (Ej: Real Madrid a ganar + Over 2.5 goles)")
            
            col_m, col_c, col_e = st.columns(3)
            monto = col_m.number_input("Monto apostado ($)", min_value=0.5, value=5.0, step=0.5)
            cuota = col_c.number_input("Cuota / Logro total", min_value=1.01, value=2.00, step=0.1)
            estado = col_e.selectbox("Estado inicial", ["Pendiente", "Ganado", "Perdido"])
            
            retorno_estimado = monto * cuota
            st.caption(f"💡 **Posible ganancia total:** ${retorno_estimado:.2f}")
            
            btn_guardar = st.form_submit_button("Guardar Apuesta")
            
            if btn_guardar:
                if descripcion.strip():
                    retorno_final = retorno_estimado if estado == "Ganado" else (0.0 if estado == "Perdido" else 0.0)
                    nueva_fila = [
                        usuario_actual,
                        str(fecha),
                        deporte,
                        descripcion.strip(),
                        str(monto),
                        str(cuota),
                        estado,
                        str(retorno_final)
                    ]
                    
                    try:
                        sheet_parleys.append_row(nueva_fila)
                        st.success("¡Apuesta registrada con éxito!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar en Google Sheets: {e}")
                else:
                    st.warning("Por favor agrega una descripción o detalle a tu jugada.")

    # --- OPCIÓN 3: HISTORIAL DE JUGADAS ---
    elif opcion_menu == "📋 Historial de Jugadas":
        st.title("📋 Historial de Parleys")
        
        if registros_usuario:
            st.dataframe(registros_usuario, use_container_width=True)
        else:
            st.info("Aún no has registrado ninguna jugada. Dirígete a '➕ Registrar Apuesta' para añadir la primera.")

# ==============================================================================
# PANTALLA DE AUTENTICACIÓN (LOGIN Y REGISTRO)
# ==============================================================================
else:
    st.title("⚽ Control de Parleys")
    st.subheader("Registro / Inicio de Sesión")
    
    tab1, tab2 = st.tabs(["Iniciar Sesión", "Registrarse"])

    # ----------------- TAB 1: INICIAR SESIÓN -----------------
    with tab1:
        st.subheader("Login")
        usuario = st.text_input("Usuario", key="login_user")
        clave = st.text_input("Contraseña", type="password", key="login_pass")
        
        if st.button("Ingresar"):
            if usuario and clave:
                if sheet_usuarios:
                    try:
                        filas = sheet_usuarios.get_all_values()
                        if len(filas) > 1:
                            usr_input = str(usuario).strip()
                            pass_input = str(clave).strip()
                            usuario_encontrado = False
                            
                            for fila in filas[1:]:
                                if len(fila) >= 2:
                                    if str(fila[0]).strip() == usr_input:
                                        usuario_encontrado = True
                                        if str(fila[1]).strip() == pass_input:
                                            st.session_state.logged_in = True
                                            st.session_state.usuario_actual = usr_input
                                            st.rerun()
                                        else:
                                            st.error("Contraseña incorrecta.")
                                        break
                            if not usuario_encontrado:
                                st.error("El usuario no existe.")
                        else:
                            st.error("La base de datos de usuarios está vacía.")
                    except Exception as e:
                        st.error(f"Error al leer la hoja: {e}")
            else:
                st.warning("Por favor ingresa usuario y contraseña.")

    # ----------------- TAB 2: REGISTRO -----------------
    with tab2:
        st.subheader("Registro de nuevo usuario")
        nuevo_usuario = st.text_input("Nuevo Usuario", key="reg_user")
        nueva_clave = st.text_input("Nueva Contraseña", type="password", key="reg_pass")
        
        if st.button("Crear cuenta"):
            if nuevo_usuario and nueva_clave:
                if sheet_usuarios:
                    try:
                        filas = sheet_usuarios.get_all_values()
                        usr_nuevo = str(nuevo_usuario).strip()
                        pass_nueva = str(nueva_clave).strip()
                        
                        registrados = [str(f[0]).strip() for f in filas[1:] if len(f) > 0] if len(filas) > 1 else []
                        
                        if usr_nuevo in registrados:
                            st.warning("El nombre de usuario ya existe.")
                        else:
                            sheet_usuarios.append_row([usr_nuevo, pass_nueva])
                            st.success("¡Cuenta creada exitosamente! Ya puedes iniciar sesión.")
                    except Exception as e:
                        st.error(f"Error al registrar: {e}")
            else:
                st.warning("Por favor completa todos los campos.")


     
               
