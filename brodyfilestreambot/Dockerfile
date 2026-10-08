# Usar la imagen oficial de Go como base para compilación
FROM golang:1.25-alpine AS builder

# Configurar el directorio de trabajo dentro del contenedor
WORKDIR /app

# Instalar dependencias necesarias para compilar y para sqlite
RUN apk add --no-cache gcc musl-dev linux-headers

# Copiar los archivos de go.mod y descargar dependencias
COPY go.mod go.sum ./
RUN go mod download

# Copiar el resto del código fuente del proyecto
COPY . .

# Descargar cualquier dependencia nueva automáticamente (como github.com/gen2brain/webp)
RUN go mod tidy

# Compilar la aplicación
RUN CGO_ENABLED=1 GOOS=linux go build -o /app/fsb -ldflags="-w -s" ./cmd/fsb

# Crear una imagen final más ligera basada en alpine
FROM alpine:latest

# Instalar certificados (necesario para HTTPS/Telegram) y otras utilidades
RUN apk add --no-cache ca-certificates tzdata

# Crear un usuario no root (Requisito de Hugging Face Spaces para seguridad)
RUN adduser -D user
USER user
WORKDIR /home/user/app

# Copiar el archivo compilado desde el builder
COPY --from=builder --chown=user:user /app/fsb /home/user/app/fsb
# Copiar el archivo .sample.env configurado a la carpeta del bot (que es el que viene por defecto)
# O si el usuario ya tiene su fsb.env renombrado, copiamos todo
COPY --chown=user:user *.env /home/user/app/
RUN mv /home/user/app/fsb.sample.env /home/user/app/fsb.env || true

# Configurar el puerto requerido por Hugging Face y la variable local
ENV PORT=7860
EXPOSE 7860

# Comando para iniciar la aplicación
CMD ["./fsb", "run"]
