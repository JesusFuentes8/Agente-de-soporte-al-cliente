# 1. Partir de la imagen base oficial de Python 3.12 slim
FROM python:3.12-slim

# 2. Obligar a Python a emitir los prints de inmediato sin almacenarlos en buffer
ENV PYTHONUNBUFFERED=1

# 3. Establecer la carpeta de trabajo dentro del contenedor
WORKDIR /app

# 4. Copiar solo el archivo de requerimientos primero para aprovechar la cache de capas
COPY requirements.txt .

# 5. Instalar dependencias sin guardar temporales de pip
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiar el script principal del agente a la carpeta de trabajo
COPY agente_soporte.py .

# 7. Comando inicial por defecto que ejecutará el contenedor
ENTRYPOINT ["python", "agente_soporte.py"]