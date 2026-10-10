import json
import os
import time
import schedule
import gspread
from google import genai
from google.genai import types

# --- Configuración ---
ARCHIVO_CREDENCIALES = "client_secrets.json"
NOMBRE_HOJA = "Respuestas de Quejas (Base de Datos)"

# PEGA AQUÍ TU API KEY ENTRE LAS COMILLAS:
GEMINI_API_KEY = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
INTERVALO_MINUTOS = 15

# Columnas en Google Sheets (base 1 para gspread)
COL_CLASIFICACION = 4  # Columna D: Clasificación IA
COL_SENTIMIENTO = 5    # Columna E: Sentimiento IA
COL_EJECUTADO = 6      # Columna F: Agente Ejecutado

cliente_gemini = None


def conectar_sheets():
    """Autentica con OAuth 2.0 y retorna la primera hoja del spreadsheet."""
    try:
        gc = gspread.oauth(
            credentials_filename=ARCHIVO_CREDENCIALES,
            authorized_user_filename="token.json"
        )
        spreadsheet = gc.open(NOMBRE_HOJA)
        return spreadsheet.sheet1
    except Exception as e:
        print(f"[ERROR] Error al conectar con Google Sheets: {e}")
        return None


def analizar_con_gemini(comentario: str, max_reintentos: int = 3) -> dict:
    """Envía el comentario a Gemini con reintentos automáticos si el modelo está ocupado (503)."""
    system_instruction = (
        "Eres un analista de soporte al cliente. Tu única tarea es devolver una "
        "respuesta en formato JSON, sin texto adicional ni explicaciones."
    )

    prompt = (
        f'Comentario del cliente: "{comentario}"\n\n'
        "Clasifica el comentario en exactamente una de estas tres categorías: [Ventas, Soporte Técnico, Logística].\n"
        "Detecta el sentimiento en exactamente uno de estos tres valores: [Positivo, Negativo, Neutro].\n"
        'Devuelve únicamente un objeto JSON con las claves "clasificacion" y "sentimiento".'
    )

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.1
    )

    # Bucle con reintentos para manejar saturación de servidores (503 UNAVAILABLE)
    for intento in range(1, max_reintentos + 1):
        try:
            respuesta = cliente_gemini.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
                config=config
            )

            # Limpieza de formato markdown si el modelo lo incluye
            texto = respuesta.text.strip()
            if texto.startswith("```"):
                lineas = texto.splitlines()
                texto = "\n".join(lineas[1:-1] if lineas[-1].startswith("```") else lineas[1:])

            return json.loads(texto)

        except Exception as e:
            if "503" in str(e) and intento < max_reintentos:
                tiempo_espera = intento * 3
                print(f"   [AVISO] Servidor saturado (503). Reintentando en {tiempo_espera}s (Intento {intento}/{max_reintentos})...")
                time.sleep(tiempo_espera)
            else:
                raise e


def ejecutar_agente():
    """Ciclo principal: lee quejas pendientes, analiza con IA y escribe en Sheets."""
    print("\n--- Ejecutando revisión del agente ---")
    hoja = conectar_sheets()
    if not hoja:
        return

    filas = hoja.get_all_values()
    if len(filas) <= 1:
        print("No hay filas para procesar.")
        return

    # Omitir fila 1 (encabezados). En Sheets los datos inician en fila 2
    for idx, fila in enumerate(filas[1:], start=2):
        # Revisar si la columna F ya contiene "SI"
        agente_ejecutado = fila[COL_EJECUTADO - 1] if len(fila) >= COL_EJECUTADO else ""
        if agente_ejecutado.strip().upper() == "SI":
            continue

        nombre_cliente = fila[1] if len(fila) > 1 and fila[1] else "Anónimo"
        comentario = fila[2] if len(fila) > 2 else ""

        if not comentario.strip():
            continue

        print(f"\nProcesando fila {idx} | Cliente: {nombre_cliente}")
        print(f"Comentario: {comentario}")

        try:
            resultado = analizar_con_gemini(comentario)
            clasificacion = resultado.get("clasificacion", "Sin clasificar")
            sentimiento = resultado.get("sentimiento", "Neutro")

            print(f"-> Clasificación: {clasificacion} | Sentimiento: {sentimiento}")

            # Escribir en columnas D, E y F
            hoja.update_cell(idx, COL_CLASIFICACION, clasificacion)
            hoja.update_cell(idx, COL_SENTIMIENTO, sentimiento)
            hoja.update_cell(idx, COL_EJECUTADO, "SI")
            print(f"[OK] Fila {idx} actualizada exitosamente.")

        except json.JSONDecodeError as jde:
            print(f"[ERROR] Gemini no devolvió un JSON válido en fila {idx}: {jde}")
        except Exception as e:
            print(f"[ERROR] Error procesando fila {idx}: {e}")

        # Pausa de 2 segundos entre filas para no saturar la API
        time.sleep(2)


if __name__ == "__main__":
    if GEMINI_API_KEY == "TU_API_KEY_AQUI" or not GEMINI_API_KEY.strip():
        print("[ERROR] Debes configurar una GEMINI_API_KEY válida en el script.")
        exit(1)

    if not os.path.exists(ARCHIVO_CREDENCIALES):
        print(f"[ERROR] No se encontró '{ARCHIVO_CREDENCIALES}' en la carpeta actual.")
        exit(1)

    # Inicializar cliente oficial de google-genai
    cliente_gemini = genai.Client(api_key=GEMINI_API_KEY)

    print(f"Iniciando agente. Revisión programada cada {INTERVALO_MINUTOS} minutos.")

    # Primera ejecución inmediata
    ejecutar_agente()

    # Programar revisiones automáticas periódicas
    schedule.every(INTERVALO_MINUTOS).minutes.do(ejecutar_agente)

    while True:
        schedule.run_pending()
        time.sleep(30)
        #python agente_soporte.py