Agente de Soporte con IA (Docker + Google Sheets)

Este proyecto automatiza la atención de quejas de clientes. Lee las respuestas de un Google Form guardadas en Google Sheets, las analiza usando la inteligencia artificial de Google Gemini y escribe la respuesta de vuelta automáticamente.

Todo el sistema corre dentro de un contenedor Docker, lo que permite mantenerlo vigilando la hoja en segundo plano sin exponer contraseñas ni archivos privados.

 ¿Qué hace el agente?

Revisa la hoja: Detecta nuevas quejas enviadas por los usuarios que aún no tengan un "SI".

Analiza con Gemini:

Clasificación: Asigna el área responsable (Ventas, Soporte Técnico o Logística).

Sentimiento: Evalúa el tono del cliente (Positivo, Negativo o Neutro).

Actualiza Google Sheets: Guarda los resultados en las columnas correspondientes y marca la fila con "SI" para no repetirla.

 ¿Cómo funciona el flujo?

Cliente llena Formulario ──▶ Hoja de Google Sheets ──▶ Contenedor Docker (IA) ──▶ Actualiza con Resultados


 Manejo Seguro de Secretos

Para evitar fugas de seguridad, las contraseñas no se guardan en el código ni en GitHub:

.env: Guarda la clave GEMINI_API_KEY.

token.env: Guarda el token de acceso GOOGLE_TOKEN_JSON.

Ambos archivos están protegidos por .gitignore y .dockerignore.

 Comandos Rápidos de Docker

1. Construir la imagen del agente

docker build -t agente-soporte .


2. Probar una sola revisión

Ejecuta el agente una sola vez para revisar que todo funcione y salir a la terminal:

docker run --rm --env-file .env --env-file token.env agente-soporte --una-vez


3. Dejarlo trabajando en segundo plano

Inicia el contenedor para que revise la hoja de cálculo continuamente:

docker run -d --name agente --restart unless-stopped --env-file .env --env-file token.env agente-soporte


4. Ver qué está haciendo en vivo (Logs)

docker logs -f agente


5. Apagar el agente

docker stop agente
docker rm agente


 Tecnologías Utilizadas

Python 3.12

Google Gemini API (gemini-3.8-flash)

Google Sheets API (gspread)

Docker & WSL 2
