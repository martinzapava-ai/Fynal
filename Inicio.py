import pandas as pd
import streamlit as st

# ============================================================
#  Configuración de la página
# ============================================================
st.set_page_config(
    page_title="Monitoreo de Vibración IoT - ESP32",
    page_icon="📳",
    layout="wide"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    code, pre, [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
    }

    .stApp {
        background: radial-gradient(circle at top left, #101820 0%, #0b0f14 55%, #080b0f 100%);
        color: #e6edf3;
    }

    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1280px;
    }

    .hero-banner {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.14) 0%, rgba(14, 165, 233, 0.10) 100%);
        border: 1px solid rgba(56, 189, 248, 0.22);
        border-radius: 16px;
        padding: 1.5rem 1.75rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
    }

    .hero-tag {
        display: inline-block;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #34d399;
        background: rgba(16, 185, 129, 0.14);
        border: 1px solid rgba(52, 211, 153, 0.3);
        padding: 0.25rem 0.65rem;
        border-radius: 999px;
        margin-bottom: 0.65rem;
    }

    .hero-title {
        font-size: 1.9rem;
        font-weight: 700;
        color: #f8fafc;
        margin: 0 0 0.4rem 0;
        line-height: 1.2;
    }

    .hero-sub {
        color: #94a3b8;
        font-size: 0.98rem;
        margin: 0;
        line-height: 1.5;
    }

    [data-testid="stMetric"] {
        background: rgba(17, 24, 39, 0.78);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 14px;
        padding: 1rem 1.15rem;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.22);
    }

    [data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
        font-size: 0.85rem !important;
    }

    [data-testid="stMetricValue"] {
        color: #38bdf8 !important;
        font-size: 1.55rem !important;
        font-weight: 600 !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background: rgba(15, 23, 42, 0.65);
        padding: 0.4rem;
        border-radius: 12px;
        border: 1px solid rgba(148, 163, 184, 0.14);
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 9px;
        padding: 0.5rem 1rem;
        color: #94a3b8;
        font-weight: 500;
    }

    .stTabs [aria-selected="true"] {
        background: rgba(16, 185, 129, 0.18) !important;
        color: #ecfdf5 !important;
        border: 1px solid rgba(52, 211, 153, 0.35) !important;
    }

    .stAlert {
        border-radius: 12px;
        margin-top: 0.85rem;
        border-width: 1px;
    }

    [data-testid="stSidebar"] {
        background: #0d131a;
        border-right: 1px solid rgba(148, 163, 184, 0.14);
    }

    .footer-note {
        margin-top: 2.5rem;
        padding-top: 1.1rem;
        border-top: 1px solid rgba(148, 163, 184, 0.15);
        color: #64748b;
        font-size: 0.86rem;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# Nombres que se reconocen como columna de tiempo (sin importar mayúsculas)
CANDIDATAS_TIEMPO = ["time", "_time", "timestamp", "fecha", "date", "datetime"]


# ============================================================
#  Preparación de datos
# ============================================================
def preparar_datos(df):
    """Detecta la columna de tiempo y las columnas numéricas del CSV exportado de Grafana."""
    df = df.copy()

    # 1. Columna de tiempo -> índice
    col_tiempo = next(
        (c for c in df.columns if str(c).strip().lower() in CANDIDATAS_TIEMPO),
        None
    )
    if col_tiempo is not None:
        df[col_tiempo] = pd.to_datetime(df[col_tiempo], errors="coerce")
        df = df.dropna(subset=[col_tiempo]).set_index(col_tiempo).sort_index()
        df.index.name = "Time"

    # 2. Columnas de texto que en realidad son números (p. ej. "12,4")
    for c in df.columns:
        if not pd.api.types.is_numeric_dtype(df[c]):
            convertida = pd.to_numeric(
                df[c].astype(str).str.replace(",", ".", regex=False),
                errors="coerce"
            )
            if convertida.notna().mean() >= 0.9:
                df[c] = convertida

    # 3. Variables numéricas disponibles para el análisis
    numericas = df.select_dtypes(include="number").columns.tolist()
    return df, numericas, col_tiempo


def normalizar(df):
    """Escala cada columna a 0-1 para comparar variables con distintas unidades."""
    rango = (df.max() - df.min()).replace(0, 1)
    return (df - df.min()) / rango


def obtener_unidad_y_rango(nombre_col, vib_min, vib_max, unidad_vib):
    """Asigna unidad y rango de referencia según el nombre de la columna."""
    nombre_lower = str(nombre_col).strip().lower()
    if any(k in nombre_lower for k in ["vib", "acel", "accel", "g_force", "hz"]):
        return unidad_vib, vib_min, vib_max
    if "temp" in nombre_lower:
        return "°C", 15.0, 32.0
    if "hum" in nombre_lower:
        return "%", 45.0, 85.0
    return "", None, None


# ============================================================
#  Encabezado y barra lateral de vibración
# ============================================================
st.markdown("""
    <div class="hero-banner">
        <div class="hero-tag">ESP32 · MQTT · InfluxDB · Grafana</div>
        <h1 class="hero-title">📳 Análisis de Vibración y Telemetría IoT</h1>
        <p class="hero-sub">
            Consola de análisis histórico para revisar comportamiento, umbrales y tendencias
            a partir de los datos exportados desde Grafana[cite: 1].
        </p>
    </div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Parámetros de Vibración")
    unidad_vib = st.selectbox(
        "Unidad de vibración",
        ["mm/s", "g", "Hz", "Nivel (0-100)"],
        index=0
    )
    vib_min = st.number_input(f"Vibración mínima ({unidad_vib})", value=0.0, step=0.5)
    vib_max = st.number_input(f"Vibración máxima permitida ({unidad_vib})", value=10.0, step=0.5)


# ============================================================
#  Carga del archivo CSV desde Grafana
# ============================================================
uploaded_file = st.file_uploader(
    "Carga el archivo CSV exportado desde Grafana",
    type=["csv"],
    help="Exporta los datos desde Grafana (Inspect -> Data -> Download CSV) y súbelos aquí."
)

if uploaded_file is not None:
    try:
        df_original = pd.read_csv(uploaded_file)
        df1, variables, col_tiempo = preparar_datos(df_original)

        if not variables:
            st.error("No se encontraron columnas numéricas en el archivo CSV.")
            st.stop()

        st.success(
            f"Archivo cargado: **{len(df1)}** registros y **{len(variables)}** variable(s): "
            + ", ".join(f"`{v}`" for v in variables)
        )
        if col_tiempo is None:
            st.info("No se encontró columna de tiempo; se usará el índice de registro como eje X.")

        # Evaluación de vibración y alertas por umbral
        st.subheader("🚨 Diagnóstico de Vibración y Alertas")
        vars_vibracion = [
            v for v in variables
            if any(k in v.lower() for k in ["vib", "acel", "accel", "g_force", "hz"])
        ]
        objetivo_alerta = vars_vibracion if vars_vibracion else [variables[0]]

        alertas = []
        for col in objetivo_alerta:
            fuera = df1[(df1[col] < vib_min) | (df1[col] > vib_max)]
            if len(fuera) > 0:
                alertas.append(
                    f"**{col}** ({unidad_vib}): **{len(fuera)}** lectura(s) fuera del rango "
                    f"[{vib_min} – {vib_max} {unidad_vib}] · Máx: `{df1[col].max():.2f}` · Mín: `{df1[col].min():.2f}`."
                )

        if alertas:
            for msg in alertas:
                st.warning(f"⚠️ Vibración fuera de rango: {msg}")
        else:
            st.info(
                f"✅ Nivel de vibración dentro del rango [{vib_min} – {vib_max} {unidad_vib}] "
                f"en `{', '.join(objetivo_alerta)}`."
            )

        tab1, tab2, tab3, tab4 = st.tabs([
            "📈 Gráficos de Vibración",
            "📊 Estadísticas",
            "🔍 Filtros por Umbral",
            "📋 Resumen del Sistema"
        ])

        # ----------------------------------------------------
        #  TAB 1 · Visualización
        # ----------------------------------------------------
        with tab1:
            st.subheader("Serie Temporal de Vibración y Sensores")

            col_a, col_b = st.columns([3, 1])
            default_vars = vars_vibracion if vars_vibracion else (
                variables if len(variables) <= 4 else variables[:2]
            )
            with col_a:
                vars_graf = st.multiselect(
                    "Variables a graficar",
                    variables,
                    default=default_vars
                )
            with col_b:
                chart_type = st.selectbox("Tipo de gráfico", ["Línea", "Área", "Barra"])

            normalizado = st.checkbox(
                "Normalizar escalas (0–1)",
                help="Útil para comparar vibración con otras variables de distintas unidades."
            )

            if not vars_graf:
                st.warning("Selecciona al menos una variable para graficar.")
            else:
                datos_graf = df1[vars_graf]
                if normalizado:
                    datos_graf = normalizar(datos_graf)

                if chart_type == "Línea":
                    st.line_chart(datos_graf)
                elif chart_type == "Área":
                    st.area_chart(datos_graf)
                else:
                    st.bar_chart(datos_graf)

            if st.checkbox("Mostrar tabla de datos"):
                st.dataframe(df1, use_container_width=True)

        # ----------------------------------------------------
        #  TAB 2 · Estadísticas
        # ----------------------------------------------------
        with tab2:
            st.subheader("Indicadores Estadísticos de Vibración")

            st.write("#### Resumen general")
            st.dataframe(df1[variables].describe().T.round(2), use_container_width=True)

            st.write("#### Detalle por variable")
            default_idx = variables.index(vars_vibracion[0]) if vars_vibracion else 0
            var_stats = st.selectbox("Variable", variables, index=default_idx, key="var_stats")
            unidad_col, _, _ = obtener_unidad_y_rango(var_stats, vib_min, vib_max, unidad_vib)
            sufijo = f" {unidad_col}" if unidad_col else ""
            serie = df1[var_stats].dropna()

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Promedio", f"{serie.mean():.2f}{sufijo}")
            m2.metric("Pico máximo", f"{serie.max():.2f}{sufijo}")
            m3.metric("Mínimo", f"{serie.min():.2f}{sufijo}")
            m4.metric("Desv. estándar", f"{serie.std():.2f}{sufijo}")

            if len(variables) >= 2:
                st.write("#### Correlación entre variables")
                st.dataframe(df1[variables].corr().round(2), use_container_width=True)
                st.caption(
                    "Valores cercanos a 1 o -1 indican correlación lineal fuerte; "
                    "valores cercanos a 0 indican poca relación."
                )

        # ----------------------------------------------------
        #  TAB 3 · Filtros
        # ----------------------------------------------------
        with tab3:
            st.subheader("Filtrar Eventos de Vibración")

            default_filtro_idx = variables.index(vars_vibracion[0]) if vars_vibracion else 0
            var_filtro = st.selectbox(
                "Variable a filtrar",
                variables,
                index=default_filtro_idx,
                key="var_filtro"
            )
            min_value = float(df1[var_filtro].min())
            max_value = float(df1[var_filtro].max())

            if min_value == max_value:
                st.warning(f"⚠️ Todos los valores de `{var_filtro}` son iguales: {min_value:.2f}")
                st.dataframe(df1, use_container_width=True)
            else:
                rango = st.slider(
                    f"Rango de {var_filtro}",
                    min_value,
                    max_value,
                    (min_value, max_value),
                    key=f"rango_{var_filtro}"
                )

                filtrado = df1[df1[var_filtro].between(rango[0], rango[1])]
                st.write(
                    f"**{len(filtrado)}** de **{len(df1)}** registros con `{var_filtro}` "
                    f"entre **{rango[0]:.2f}** y **{rango[1]:.2f}**:"
                )
                st.dataframe(filtrado, use_container_width=True)

                st.download_button(
                    label="⬇️ Descargar datos filtrados (CSV)",
                    data=filtrado.to_csv().encode("utf-8"),
                    file_name=f"vibracion_filtrada_{var_filtro}.csv",
                    mime="text/csv",
                )

        # ----------------------------------------------------
        #  TAB 4 · Resumen del sistema
        # ----------------------------------------------------
        with tab4:
            st.subheader("Parámetros del Sistema IoT")

            col1, col2 = st.columns(2)

            with col1:
                st.write("### Control y Sensado")
                st.write("- **Microcontrolador:** ESP32")
                st.write("- **Enfoque:** Monitoreo de vibración y telecontrol remoto por MQTT[cite: 1]")
                st.write(f"- **Umbral configurado:** {vib_min} – {vib_max} {unidad_vib}")

            with col2:
                st.write("### Datos Analizados")
                st.write("- **Variables numéricas:** " + ", ".join(variables))
                st.write(f"- **Total de registros:** {len(df1)}")
                if col_tiempo is not None and len(df1) > 0:
                    st.write(f"- **Desde:** {df1.index.min():%Y-%m-%d %H:%M:%S}")
                    st.write(f"- **Hasta:** {df1.index.max():%Y-%m-%d %H:%M:%S}")

    except Exception as e:
        st.error(f"Error al procesar el archivo: {str(e)}")
        st.info("Verifica que el archivo CSV tenga columnas numéricas válidas.")
else:
    st.warning("Sube un archivo CSV exportado desde Grafana para comenzar el análisis de vibración[cite: 1].")

# ============================================================
#  Pie de página
# ============================================================
st.markdown("""
    <div class="footer-note">
        Proyecto Final · Computación Física e Internet de las Cosas (IoT) — Análisis de Vibración[cite: 1]
    </div>
""", unsafe_allow_html=True)
