import streamlit as st
import pandas as pd
import hashlib
import base64
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Control de Parleys",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

LISTA_DEPORTES = [
    "Fútbol", 
    "Béisbol (MLB)", 
    "Baloncesto (NBA)", 
    "Fútbol Americano (NFL)", 
    "Tenis", 
    "Combinado / Mixto", 
    "Otro"
]
LISTA_MONEDAS = ["USD ($)", "VES (Bs.)"]

# --- FUNCIÓN PARA ENCRIPTAR CONTRASEÑAS (SHA-256) ---
def encriptar_pass(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def cargar_usuarios():
    try:
        spreadsheet_id = st.secrets["spreadsheet_id"]
        # Lee la pestaña "Usuarios"
        df = conn.read(spreadsheet=spreadsheet_id, worksheet="Usuarios", ttl=0)
        df = df.fillna("")
        return df.to_dict(orient="records")
    except Exception:
        return []

def guardar_usuarios(lista_usuarios):
    try:
        spreadsheet_id = st.secrets["spreadsheet_id"]
        df = pd.DataFrame(lista_usuarios)
        conn.update(spreadsheet=spreadsheet_id, worksheet="Usuarios", data=df)
    except Exception as e:
        st.error(f"Error al guardar usuario en Google Sheets: {e}")

def cargar_parleys():
    try:
        spreadsheet_id = st.secrets["spreadsheet_id"]
        # Lee la pestaña "Parleys"
        df = conn.read(spreadsheet=spreadsheet_id, worksheet="Parleys", ttl=0)
        df = df.fillna("")
        datos = df.to_dict(orient="records")
        for item in datos:
            item["id"] = int(item["id"]) if item["id"] != "" else 0
            item["monto"] = float(item["monto"]) if item["monto"] != "" else 0.0
            item["cuota"] = float(item["cuota"]) if item["cuota"] != "" else 1.0
            item["retorno"] = float(item["retorno"]) if item["retorno"] != "" else 0.0
            item["neto"] = float(item["neto"]) if item["neto"] != "" else 0.0
        return datos
    except Exception:
        return []

def guardar_parleys(lista_parleys):
    try:
        spreadsheet_id = st.secrets["spreadsheet_id"]
        df = pd.DataFrame(lista_parleys)
        conn.update(spreadsheet=spreadsheet_id, worksheet="Parleys", data=df)
    except Exception as e:
        st.error(f"Error al guardar parleys en Google Sheets: {e}")

def convertir_imagen_a_base64(uploaded_file):
    if uploaded_file is not None:
        bytes_data = uploaded_file.getvalue()
        base64_str = base64.b64encode(bytes_data).decode('utf-8')
        mime_type = uploaded_file.type
        return f"data:{mime_type};base64,{base64_str}"
    return ""

# --- MANEJO DE SESIÓN DE AUTENTICACIÓN ---
if "usuario_logueado" not in st.session_state:
    st.session_state.usuario_logueado = None

# --- PANTALLA DE INICIO DE SESIÓN / REGISTRO ---
if st.session_state.usuario_logueado is None:
    st.title("⚽ Control de Parleys Pro")
    
    tab_login, tab_registro = st.tabs(["🔑 Iniciar Sesión", "📝 Registrar Nuevo Usuario"])
    
    # 1. FORMULARIO DE LOGIN
    with tab_login:
        with st.form("form_login"):
            usr_input = st.text_input("Nombre de Usuario").strip().lower()
            pwd_input = st.text_input("Contraseña", type="password")
            btn_login = st.form_submit_button("Ingresar", use_container_width=True)
            
            if btn_login:
                usuarios = cargar_usuarios()
                pwd_hashed = encriptar_pass(pwd_input)
                
                # Validar usuario y contraseña
                user_match = next((u for u in usuarios if str(u.get("usuario")).lower() == usr_input and str(u.get("password")) == pwd_hashed), None)
                
                if user_match:
                    st.session_state.usuario_logueado = {
                        "usuario": user_match["usuario"],
                        "nombre": user_match["nombre"]
                    }
                    st.success(f"¡Bienvenido {user_match['nombre']}!")
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")

    # 2. FORMULARIO DE REGISTRO
    with tab_registro:
        with st.form("form_registro"):
            reg_nombre = st.text_input("Nombre Completo (ej: Carlos)")
            reg_usr = st.text_input("Crea un Usuario (sin espacios)").strip().lower()
            reg_pwd = st.text_input("Crea una Contraseña", type="password")
            btn_registro = st.form_submit_button("Crear Cuenta", use_container_width=True)
            
            if btn_registro:
                if not reg_nombre or not reg_usr or not reg_pwd:
                    st.error("Por favor completa todos los campos.")
                else:
                    usuarios = cargar_usuarios()
                    if any(str(u.get("usuario")).lower() == reg_usr for u in usuarios):
                        st.error("Ese nombre de usuario ya existe. Elige otro.")
                    else:
                        nuevo_usuario = {
                            "usuario": reg_usr,
                            "password": encriptar_pass(reg_pwd),
                            "nombre": reg_nombre
                        }
                        usuarios.append(nuevo_usuario)
                        guardar_usuarios(usuarios)
                        st.success("¡Cuenta creada exitosamente! Ahora puedes iniciar sesión.")

    st.stop()  # Detiene la ejecución para que no cargue la app si no hay login

# --- SI EL USUARIO YA INICIÓ SESIÓN ---
user_actual = st.session_state.usuario_logueado

# Cargar todos los parleys
if "todos_los_parleys" not in st.session_state:
    st.session_state.todos_los_parleys = cargar_parleys()

todos_los_parleys = st.session_state.todos_los_parleys

# FILTRAR SOLO LOS PARLEYS DEL USUARIO ACTUAL
parleys_usuario = [p for p in todos_los_parleys if str(p.get("usuario")).lower() == str(user_actual["usuario"]).lower()]

# BARRA LATERAL
with st.sidebar:
    st.write(f"👤 **{user_actual['nombre']}** (`{user_actual['usuario']}`)")
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.usuario_logueado = None
        st.session_state.todos_los_parleys = None
        st.rerun()
    st.divider()
    if st.button("🔄 Sincronizar", use_container_width=True):
        st.session_state.todos_los_parleys = cargar_parleys()
        st.success("Sincronizado")
        st.rerun()

st.title(f"⚽ Control de Parleys - {user_actual['nombre']}")

# --- FORMULARIO DE REGISTRO DE PARLEY ---
with st.expander("➕ Registrar Nuevo Parley", expanded=True):
    with st.form("form_parley", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            fecha = st.text_input("Fecha (DD/MM/AAAA)", value=datetime.now().strftime("%d/%m/%Y"))
            moneda = st.selectbox("Moneda", LISTA_MONEDAS)
            deporte = st.selectbox("Deporte / Categoría", LISTA_DEPORTES)
            desc = st.text_input("Descripción / Equipos", placeholder="Ej: Real Madrid + Dodgers")
            
        with col2:
            monto = st.number_input("Monto Invertido", min_value=0.0, step=1.0, format="%.2f")
            cuota = st.number_input("Cuota Total", min_value=1.0, step=0.05, format="%.2f")
            estado = st.selectbox("Estado", ["Pendiente", "Ganado", "Perdido", "Cobrado"])
            cashout = st.number_input("Monto Cashout (Opcional)", min_value=0.0, step=1.0, format="%.2f", help="Solo si seleccionas 'Cobrado'")

        imagen_adjunta = st.file_uploader("Adjuntar captura / ticket (Opcional):", type=["png", "jpg", "jpeg", "webp"])
        btn_guardar = st.form_submit_button("Guardar Parley", use_container_width=True)

        if btn_guardar:
            if not desc:
                st.error("Por favor ingresa la descripción o los equipos del parley.")
            elif monto <= 0:
                st.error("El monto debe ser mayor a 0.")
            else:
                retorno = 0.0
                if estado == "Ganado":
                    retorno = monto * cuota
                elif estado == "Cobrado":
                    retorno = cashout
                elif estado == "Perdido":
                    retorno = 0.0

                neto = retorno - monto if estado != "Pendiente" else 0.0
                imagen_b64 = convertir_imagen_a_base64(imagen_adjunta)

                nuevo_id = max([p["id"] for p in todos_los_parleys], default=0) + 1

                nuevo_item = {
                    "id": nuevo_id,
                    "fecha": fecha,
                    "moneda": moneda,
                    "deporte": deporte,
                    "desc": desc,
                    "monto": monto,
                    "cuota": cuota,
                    "estado": estado,
                    "retorno": retorno,
                    "neto": neto,
                    "imagen": imagen_b64,
                    "usuario": user_actual["usuario"]  # Se asigna únicamente al usuario actual
                }

                st.session_state.todos_los_parleys.append(nuevo_item)
                guardar_parleys(st.session_state.todos_los_parleys)
                st.success("¡Parley registrado con éxito!")
                st.rerun()

# --- RESUMEN Y MÉTRICAS ---
if parleys_usuario:
    datos_usd = [p for p in parleys_usuario if p.get("moneda", "USD ($)") == "USD ($)"]
    datos_ves = [p for p in parleys_usuario if p.get("moneda") == "VES (Bs.)"]

    st.subheader("📊 Tus Métricas Generales")
    t1, t2 = st.tabs(["Dólares (USD)", "Bolívares (VES)"])
    
    with t1:
        if datos_usd:
            inv_usd = sum(p["monto"] for p in datos_usd if p["estado"] != "Pendiente")
            ret_usd = sum(p["retorno"] for p in datos_usd if p["estado"] != "Pendiente")
            neto_usd = ret_usd - inv_usd
            roi_usd = (neto_usd / inv_usd * 100) if inv_usd > 0 else 0.0

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Registros (USD)", len(datos_usd))
            m2.metric("Invertido", f"${inv_usd:.2f}")
            m3.metric("Retornado", f"${ret_usd:.2f}")
            m4.metric("Balance Neto", f"${neto_usd:+.2f}", delta=f"{roi_usd:+.2f}% ROI")
        else:
            st.info("No tienes registros en Dólares aún.")

    with t2:
        if datos_ves:
            inv_ves = sum(p["monto"] for p in datos_ves if p["estado"] != "Pendiente")
            ret_ves = sum(p["retorno"] for p in datos_ves if p["estado"] != "Pendiente")
            neto_ves = ret_ves - inv_ves
            roi_ves = (neto_ves / inv_ves * 100) if inv_ves > 0 else 0.0

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Registros (VES)", len(datos_ves))
            m2.metric("Invertido", f"Bs. {inv_ves:.2f}")
            m3.metric("Retornado", f"Bs. {ret_ves:.2f}")
            m4.metric("Balance Neto", f"Bs. {neto_ves:+.2f}", delta=f"{roi_ves:+.2f}% ROI")
        else:
            st.info("No tienes registros en Bolívares aún.")

    # --- RENDIMIENTO POR DEPORTE ---
    with st.expander("🏆 Tu Rendimiento por Deporte", expanded=False):
        deportes_presentes = list(set(p.get("deporte", "Sin Deporte") for p in parleys_usuario))
        tabla_deportes = []
        for dep in deportes_presentes:
            items_dep = [p for p in parleys_usuario if p.get("deporte", "Sin Deporte") == dep]
            cerrados = [p for p in items_dep if p["estado"] != "Pendiente"]
            total_reg = len(items_dep)
            ganados = sum(1 for p in cerrados if p["estado"] in ["Ganado", "Cobrado"])
            efectividad = (ganados / len(cerrados) * 100) if len(cerrados) > 0 else 0.0

            tabla_deportes.append({
                "Deporte / Categoría": dep,
                "Total Jugados": total_reg,
                "Finalizados": len(cerrados),
                "Ganados / Cobrados": ganados,
                "% Efectividad": f"{efectividad:.1f}%"
            })
        st.table(tabla_deportes)

    st.divider()

    # --- FILTROS Y HISTORIAL ---
    st.subheader("🔍 Filtrar Mis Registros")
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
    
    with f_col1:
        filtro_moneda = st.selectbox("Filtrar Moneda:", ["Todas"] + LISTA_MONEDAS)
    with f_col2:
        filtro_estado = st.selectbox("Filtrar Estado:", ["Todos", "Pendiente", "Ganado", "Perdido", "Cobrado"])
    with f_col3:
        filtro_deporte = st.selectbox("Filtrar Deporte:", ["Todos"] + LISTA_DEPORTES)
    with f_col4:
        busqueda_texto = st.text_input("Buscar equipo:", placeholder="Ej: Real Madrid")

    datos_filtrados = parleys_usuario
    if filtro_moneda != "Todas":
        datos_filtrados = [p for p in datos_filtrados if p.get("moneda", "USD ($)") == filtro_moneda]
    if filtro_estado != "Todos":
        datos_filtrados = [p for p in datos_filtrados if p["estado"] == filtro_estado]
    if filtro_deporte != "Todos":
        datos_filtrados = [p for p in datos_filtrados if p.get("deporte") == filtro_deporte]
    if busqueda_texto:
        datos_filtrados = [p for p in datos_filtrados if busqueda_texto.lower() in p["desc"].lower()]

    st.markdown(f"**Mostrando {len(datos_filtrados)} de {len(parleys_usuario)} registros:**")
    
    tabla_display = []
    for p in datos_filtrados:
        moneda_actual = p.get("moneda", "USD ($)")
        simbolo = "$" if moneda_actual == "USD ($)" else "Bs."

        tabla_display.append({
            "ID": p["id"],
            "Fecha": p["fecha"],
            "Deporte": p.get("deporte", "N/A"),
            "Descripción": p["desc"],
            "Monto": f"{simbolo} {p['monto']:.2f}",
            "Cuota": f"{p['cuota']:.2f}",
            "Estado": p["estado"],
            "Retorno": f"{simbolo} {p['retorno']:.2f}",
            "Neto": f"{simbolo} {p['neto']:+.2f}",
            "Ticket": "📸 Sí" if p.get("imagen") else "❌ No"
        })

    if tabla_display:
        st.table(tabla_display)
    else:
        st.warning("No se encontraron registros.")

    # --- EDITAR O ELIMINAR REGISTRO ---
    with st.expander("⚙️ Ver Ticket o Modificar Registro"):
        listado_ids = [p["id"] for p in datos_filtrados]
        if listado_ids:
            id_sel = st.selectbox("Selecciona el ID del Parley para ver o editar:", listado_ids)
            parley_sel = next((p for p in todos_los_parleys if p["id"] == id_sel and str(p.get("usuario")).lower() == str(user_actual["usuario"]).lower()), None)
            
            if parley_sel:
                col_info, col_img = st.columns([1, 1])

                with col_info:
                    moneda_actual = parley_sel.get("moneda", "USD ($)")
                    simb = "$" if moneda_actual == "USD ($)" else "Bs."

                    st.markdown(f"**Detalles del Parley #{parley_sel['id']}**")
                    st.write(f"**Fecha:** {parley_sel['fecha']}")
                    st.write(f"**Apuesta:** {parley_sel['desc']}")
                    st.write(f"**Monto:** {simb} {parley_sel['monto']:.2f} | **Cuota:** {parley_sel['cuota']:.2f}")
                    
                    nuevo_dep = st.selectbox("Actualizar Deporte:", LISTA_DEPORTES, index=LISTA_DEPORTES.index(parley_sel.get("deporte", "Fútbol")) if parley_sel.get("deporte") in LISTA_DEPORTES else 0)
                    nuevo_est = st.selectbox("Actualizar Estado:", ["Pendiente", "Ganado", "Perdido", "Cobrado"], index=["Pendiente", "Ganado", "Perdido", "Cobrado"].index(parley_sel["estado"]))
                    
                    nuevo_cashout = 0.0
                    if nuevo_est == "Cobrado":
                        nuevo_cashout = st.number_input("Monto Cashout:", value=float(parley_sel["retorno"]))

                    c_act, c_elim = st.columns(2)
                    with c_act:
                        if st.button("Actualizar", use_container_width=True):
                            ret = 0.0
                            if nuevo_est == "Ganado":
                                ret = parley_sel["monto"] * parley_sel["cuota"]
                            elif nuevo_est == "Cobrado":
                                ret = nuevo_cashout
                            elif nuevo_est == "Perdido":
                                ret = 0.0

                            parley_sel["deporte"] = nuevo_dep
                            parley_sel["estado"] = nuevo_est
                            parley_sel["retorno"] = ret
                            parley_sel["neto"] = ret - parley_sel["monto"] if nuevo_est != "Pendiente" else 0.0
                            
                            guardar_parleys(st.session_state.todos_los_parleys)
                            st.success("Actualizado con éxito.")
                            st.rerun()

                    with c_elim:
                        if st.button("Eliminar", type="primary", use_container_width=True):
                            st.session_state.todos_los_parleys = [p for p in todos_los_parleys if p["id"] != id_sel]
                            guardar_parleys(st.session_state.todos_los_parleys)
                            st.warning("Registro eliminado.")
                            st.rerun()

                with col_img:
                    st.markdown("**Captura del Ticket:**")
                    if parley_sel.get("imagen"):
                        st.image(parley_sel["imagen"], use_column_width=True, caption=f"Ticket Parley #{parley_sel['id']}")
                    else:
                        st.info("Este registro no tiene ninguna captura adjunta.")
else:
    st.info("No tienes registros guardados aún. Agrega tu primer parley arriba.")
