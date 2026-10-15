import sys
import json
import os
import time
import schedule
import gspread
from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials

# --- Configuración ---
ARCHIVO_CREDENCIALES = "client_secrets.json"
NOMBRE_HOJA = "Respuestas de Quejas (Base de Datos)"
INTERVALO_MINUTOS = 1  # 1 minuto según las instrucciones de Docker para modo continuo

# Columnas en Google Sheets (base 1 para gspread)
COL_CLASIFICACION = 4  # Columna D: Clasificación IA
COL_SENTIMIENTO = 5    # Columna E: Sentimiento IA
COL_EJECUTADO = 6      # Columna F: Agente Ejecutado

cliente_gemini = None


def conectar_sheets():
    """Autentica con GOOGLE_TOKEN_JSON de entorno si existe, o local con client_secrets.json."""
    token_env = os.getenv("GOOGLE_TOKEN_JSON")
    if token_env:
        try:
            info = json.loads(token_env)
            creds = Credentials.from_authorized_user_info(info)
            gc = gspread.authorize(creds)
            spreadsheet = gc.open(NOMBRE_HOJA)
            return spreadsheet.sheet1
        except Exception as e:
            print(f"[ERROR] Error al autenticar con GOOGLE_TOKEN_JSON: {e}")
            return None
    else:
        try:
            gc = gspread.oauth(
                credentials_filename=ARCHIVO_CREDENCIALES,
                authorized_user_filename="token.json"
            )
            spreadsheet = gc.open(NOMBRE_HOJA)
            return spreadsheet.sheet1
        except Exception as e:
            print(f"[ERROR] Error al conectar con Google Sheets de forma local: {e}")
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

    for intento in range(1, max_reintentos + 1):
        try:
            respuesta = cliente_gemini.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
                config=config
            )

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

    filas_pendientes = 0
    filas_procesadas = 0

    for idx, fila in enumerate(filas[1:], start=2):
        agente_ejecutado = fila[COL_EJECUTADO - 1] if len(fila) >= COL_EJECUTADO else ""
        if agente_ejecutado.strip().upper() == "SI":
            filas_procesadas += 1
            continue

        nombre_cliente = fila[1] if len(fila) > 1 and fila[1] else "Anónimo"
        comentario = fila[2] if len(fila) > 2 else ""

        if not comentario.strip():
            continue

        filas_pendientes += 1
        print(f"\nProcesando fila {idx} | Cliente: {nombre_cliente}")
        print(f"Comentario: {comentario}")

        try:
            resultado = analizar_con_gemini(comentario)
            clasificacion = resultado.get("clasificacion", "Sin clasificar")
            sentimiento = resultado.get("sentimiento", "Neutro")

            print(f"-> Clasificación: {clasificacion} | Sentimiento: {sentimiento}")

            hoja.update_cell(idx, COL_CLASIFICACION, clasificacion)
            hoja.update_cell(idx, COL_SENTIMIENTO, sentimiento)
            hoja.update_cell(idx, COL_EJECUTADO, "SI")
            print(f"[OK] Fila {idx} actualizada exitosamente.")

        except json.JSONDecodeError as jde:
            print(f"[ERROR] Gemini no devolvió un JSON válido en fila {idx}: {jde}")
        except Exception as e:
            print(f"[ERROR] Error procesando fila {idx}: {e}")

        time.sleep(2)

    print(f"\n[RESUMEN] Ya procesadas: {filas_procesadas} | Nuevas atendidas: {filas_pendientes}")


if __name__ == "__main__":
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] Debes configurar la variable de entorno GEMINI_API_KEY.")
        sys.exit(1)

    cliente_gemini = genai.Client(api_key=api_key)

    # Si se pasa el argumento --una-vez, ejecuta el ciclo y termina inmediatamente
    if "--una-vez" in sys.argv:
        ejecutar_agente()
        sys.exit(0)

    print(f"Iniciando agente en modo continuo. Revisión cada {INTERVALO_MINUTOS} minuto(s).")
    ejecutar_agente()
    schedule.every(INTERVALO_MINUTOS).minutes.do(ejecutar_agente)

    while True:
        schedule.run_pending()
        time.sleep(10)