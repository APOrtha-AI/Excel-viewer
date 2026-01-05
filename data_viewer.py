import streamlit as st
import pandas as pd
import io
from datetime import datetime

# Seite konfigurieren
st.set_page_config(page_title="Data Viewer", layout="wide")

# Session State initialisieren
if 'df_original' not in st.session_state:
    st.session_state.df_original = None
if 'df_filtered' not in st.session_state:
    st.session_state.df_filtered = None


def load_data(uploaded_file):
    """
    Lädt Daten aus einer hochgeladenen Datei (CSV oder Excel).
    
    Args:
        uploaded_file: Die hochgeladene Datei (UploadedFile-Objekt)
    
    Returns:
        Tuple (erfolg: bool, dataframe: pd.DataFrame, fehlermeldung: str)
    """
    try:
        # Dateityp erkennen
        file_extension = uploaded_file.name.split('.')[-1].lower()
        
        if file_extension == 'csv':
            # CSV-Datei laden
            # Versuche verschiedene Encodings
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    uploaded_file.seek(0)  # Zurück zum Dateianfang
                    df = pd.read_csv(uploaded_file, encoding='latin-1')
                except:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, encoding='iso-8859-1')
        
        elif file_extension in ['xlsx', 'xls']:
            # Excel-Datei laden
            df = pd.read_excel(uploaded_file, engine='openpyxl')
        
        else:
            return False, None, f"Unbekannter Dateityp: {file_extension}. Unterstützt werden CSV und Excel (xlsx, xls)."
        
        # Prüfen ob Datei leer ist
        if df.empty:
            return False, None, "Die Datei ist leer oder enthält keine Daten."
        
        # Prüfen ob DataFrame ungültig ist
        if df is None:
            return False, None, "Fehler beim Laden der Datei. Die Datei könnte beschädigt sein."
        
        return True, df, ""
    
    except pd.errors.EmptyDataError:
        return False, None, "Die Datei ist leer."
    except pd.errors.ParserError as e:
        return False, None, f"Fehler beim Parsen der Datei: {str(e)}"
    except Exception as e:
        return False, None, f"Unerwarteter Fehler beim Laden: {str(e)}"


def detect_column_type(df, column):
    """
    Erkennt den Datentyp einer Spalte.
    
    Args:
        df: DataFrame
        column: Name der Spalte
    
    Returns:
        Datentyp als String: 'text', 'numeric', 'datetime'
    """
    if column not in df.columns:
        return 'text'
    
    # Prüfe auf Datum
    if pd.api.types.is_datetime64_any_dtype(df[column]):
        return 'datetime'
    
    # Prüfe auf numerisch
    if pd.api.types.is_numeric_dtype(df[column]):
        return 'numeric'
    
    # Ansonsten Text
    return 'text'


def build_filters(df):
    """
    Erstellt Filter-Widgets in der Sidebar basierend auf dem DataFrame.
    
    Args:
        df: DataFrame mit den Daten
    """
    if df is None or df.empty:
        return None
    
    st.sidebar.header("🔍 Filter")
    
    # Spaltenauswahl für Filter
    filter_column = st.sidebar.selectbox(
        "Spalte auswählen:",
        options=[''] + list(df.columns),
        key="filter_column"
    )
    
    if filter_column == '':
        return None
    
    # Datentyp der Spalte erkennen
    col_type = detect_column_type(df, filter_column)
    
    filter_config = {
        'column': filter_column,
        'type': col_type
    }
    
    # Filter-Widget je nach Datentyp
    if col_type == 'text':
        filter_value = st.sidebar.text_input(
            "Text enthält:",
            key=f"filter_text_{filter_column}",
            help="Suche nach Texten, die diesen Wert enthalten"
        )
        filter_config['value'] = filter_value
    
    elif col_type == 'numeric':
        col_min = float(df[filter_column].min())
        col_max = float(df[filter_column].max())
        
        filter_range = st.sidebar.slider(
            "Wertebereich:",
            min_value=col_min,
            max_value=col_max,
            value=(col_min, col_max),
            key=f"filter_numeric_{filter_column}"
        )
        filter_config['min'] = filter_range[0]
        filter_config['max'] = filter_range[1]
    
    elif col_type == 'datetime':
        # Versuche min/max aus DataFrame zu extrahieren
        try:
            date_min = pd.to_datetime(df[filter_column]).min()
            date_max = pd.to_datetime(df[filter_column]).max()
        except:
            date_min = datetime(2020, 1, 1)
            date_max = datetime.now()
        
        filter_date_from = st.sidebar.date_input(
            "Von:",
            value=date_min,
            min_value=date_min,
            max_value=date_max,
            key=f"filter_date_from_{filter_column}"
        )
        
        filter_date_to = st.sidebar.date_input(
            "Bis:",
            value=date_max,
            min_value=date_min,
            max_value=date_max,
            key=f"filter_date_to_{filter_column}"
        )
        
        filter_config['from'] = filter_date_from
        filter_config['to'] = filter_date_to
    
    return filter_config


def apply_filters(df, filter_config):
    """
    Wendet Filter auf einen DataFrame an.
    
    Args:
        df: Original DataFrame
        filter_config: Filter-Konfiguration von build_filters
    
    Returns:
        Gefilterter DataFrame
    """
    if df is None or df.empty:
        return df
    
    if filter_config is None:
        return df
    
    df_filtered = df.copy()
    column = filter_config['column']
    col_type = filter_config['type']
    
    try:
        if col_type == 'text':
            filter_value = filter_config.get('value', '')
            if filter_value:
                df_filtered = df_filtered[
                    df_filtered[column].astype(str).str.contains(
                        filter_value, 
                        case=False, 
                        na=False
                    )
                ]
        
        elif col_type == 'numeric':
            min_val = filter_config.get('min')
            max_val = filter_config.get('max')
            if min_val is not None and max_val is not None:
                df_filtered = df_filtered[
                    (df_filtered[column] >= min_val) & 
                    (df_filtered[column] <= max_val)
                ]
        
        elif col_type == 'datetime':
            date_from = filter_config.get('from')
            date_to = filter_config.get('to')
            if date_from and date_to:
                # Konvertiere zu datetime falls nötig
                df_filtered[column] = pd.to_datetime(df_filtered[column], errors='coerce')
                df_filtered = df_filtered[
                    (df_filtered[column] >= pd.Timestamp(date_from)) &
                    (df_filtered[column] <= pd.Timestamp(date_to))
                ]
    
    except Exception as e:
        st.error(f"Fehler beim Anwenden des Filters: {str(e)}")
        return df
    
    return df_filtered


def apply_sorting(df, sort_column, sort_ascending):
    """
    Wendet Sortierung auf einen DataFrame an.
    
    Args:
        df: DataFrame
        sort_column: Spalte nach der sortiert werden soll
        sort_ascending: True für aufsteigend, False für absteigend
    
    Returns:
        Sortierter DataFrame
    """
    if df is None or df.empty:
        return df
    
    if sort_column == '':
        return df
    
    try:
        return df.sort_values(by=sort_column, ascending=sort_ascending, na_position='last')
    except Exception as e:
        st.error(f"Fehler beim Sortieren: {str(e)}")
        return df


# Hauptbereich
st.title("📊 Data Viewer")
st.markdown("Laden Sie CSV oder Excel-Dateien hoch und filtern Sie die Daten.")

# Datei-Upload
uploaded_file = st.file_uploader(
    "Datei hochladen",
    type=['csv', 'xlsx', 'xls'],
    help="Unterstützte Formate: CSV, Excel (.xlsx, .xls)"
)

# Datei verarbeiten
if uploaded_file is not None:
    # Daten laden
    success, df, error_msg = load_data(uploaded_file)
    
    if success:
        st.session_state.df_original = df
        st.success(f"✅ Datei erfolgreich geladen: {uploaded_file.name}")
        st.info(f"📊 Daten: {len(df)} Zeilen, {len(df.columns)} Spalten")
        
        # Sidebar-Filter
        filter_config = build_filters(df)
        
        # Sortierung
        st.sidebar.header("🔢 Sortierung")
        sort_column = st.sidebar.selectbox(
            "Sortieren nach:",
            options=[''] + list(df.columns),
            key="sort_column"
        )
        
        sort_ascending = True
        if sort_column != '':
            sort_ascending = st.sidebar.radio(
                "Richtung:",
                ["Aufsteigend ↑", "Absteigend ↓"],
                key="sort_direction"
            )
            sort_ascending = sort_ascending == "Aufsteigend ↑"
        
        # Filter anwenden
        df_filtered = apply_filters(st.session_state.df_original, filter_config)
        
        # Sortierung anwenden
        df_filtered = apply_sorting(df_filtered, sort_column, sort_ascending)
        
        st.session_state.df_filtered = df_filtered
        
        # Statistiken anzeigen
        if len(df_filtered) != len(df):
            st.warning(f"⚠️ Gefiltert: {len(df_filtered)} von {len(df)} Zeilen angezeigt")
        else:
            st.info(f"📋 Alle {len(df_filtered)} Zeilen werden angezeigt")
        
        # Datenanzeige
        st.header("📋 Daten")
        st.dataframe(df_filtered, use_container_width=True, height=400)
        
        # Download-Button
        st.markdown("---")
        st.header("💾 Download")
        
        # CSV als String konvertieren
        csv_buffer = io.StringIO()
        df_filtered.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        csv_string = csv_buffer.getvalue()
        
        st.download_button(
            label="📥 Gefilterte Daten als CSV herunterladen",
            data=csv_string,
            file_name=f"gefilterte_daten_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
        
    else:
        st.error(f"❌ Fehler beim Laden der Datei: {error_msg}")
        st.session_state.df_original = None
        st.session_state.df_filtered = None

else:
    st.info("👆 Bitte laden Sie eine CSV oder Excel-Datei hoch, um zu beginnen.")
