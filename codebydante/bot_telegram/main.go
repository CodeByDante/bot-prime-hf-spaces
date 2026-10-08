package main

import (
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"

	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
	"github.com/joho/godotenv"
)

func main() {
	// 1. Cargar variables de entorno
	err := godotenv.Load()
	if err != nil {
		log.Println("Aviso: No se encontró archivo .env, usando variables de sistema")
	}

	token := os.Getenv("TELEGRAM_BOT_TOKEN")
	channelIDStr := os.Getenv("TELEGRAM_CHANNEL_ID")
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	if token == "" || token == "tu_token_aqui" {
		log.Fatal("ERROR: TELEGRAM_BOT_TOKEN no configurado en .env")
	}

	channelID, _ := strconv.ParseInt(channelIDStr, 10, 64)

	// 2. Inicializar Bot de Telegram
	bot, err := tgbotapi.NewBotAPI(token)
	if err != nil {
		log.Panic(err)
	}

	bot.Debug = true
	log.Printf("Bot autorizado en la cuenta: %s", bot.Self.UserName)

	// 3. Goroutine para manejar mensajes entrantes (Útil para obtener IDs de canales)
	go func() {
		u := tgbotapi.NewUpdate(0)
		u.Timeout = 60
		updates := bot.GetUpdatesChan(u)

		for update := range updates {
			if update.Message != nil {
				log.Printf("[%s] %s", update.Message.From.UserName, update.Message.Text)
				
				// Responder con el ID del chat si el usuario envía /id
				if update.Message.Text == "/id" {
					msg := tgbotapi.NewMessage(update.Message.Chat.ID, fmt.Sprintf("El ID de este chat es: %d", update.Message.Chat.ID))
					bot.Send(msg)
				}
			}
		}
	}()

	// 4. Servidor HTTP para recibir archivos de la Web
	http.HandleFunc("/upload", func(w http.ResponseWriter, r *http.Request) {
		// Habilitar CORS para que tu página web pueda conectar
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")

		if r.Method == "OPTIONS" {
			return
		}

		if r.Method != "POST" {
			http.Error(w, "Método no permitido", http.StatusMethodNotAllowed)
			return
		}

		// Recibir el archivo del formulario
		file, header, err := r.FormFile("file")
		if err != nil {
			http.Error(w, "Error al recibir archivo: "+err.Error(), http.StatusBadRequest)
			return
		}
		defer file.Close()

		log.Printf("Recibiendo archivo: %s (%d bytes)", header.Filename, header.Size)

		// Preparar el envío a Telegram
		fileBytes, err := io.ReadAll(file)
		if err != nil {
			http.Error(w, "Error al leer archivo", http.StatusInternalServerError)
			return
		}

		// Crear el archivo para Telegram
		// Puedes usar NewDocument (genérico) o NewVideo según el tipo
		fileData := tgbotapi.FileBytes{
			Name:  header.Filename,
			Bytes: fileBytes,
		}

		// Enviamos como documento por defecto para no perder calidad
		docMsg := tgbotapi.NewDocument(channelID, fileData)
		docMsg.Caption = "Archivo subido desde CodeByDante: " + header.Filename
		
		sentMsg, err := bot.Send(docMsg)
		if err != nil {
			http.Error(w, "Error al enviar a Telegram: "+err.Error(), http.StatusInternalServerError)
			return
		}

		// Responder con el ID del mensaje para guardarlo en Firebase
		response := fmt.Sprintf("{\"status\": \"success\", \"message_id\": %d, \"channel_id\": %d}", sentMsg.MessageID, channelID)
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(response))
		
		log.Printf("Archivo enviado con éxito a Telegram. MessageID: %d", sentMsg.MessageID)
	})

	log.Printf("Servidor API escuchando en el puerto %s...", port)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}
