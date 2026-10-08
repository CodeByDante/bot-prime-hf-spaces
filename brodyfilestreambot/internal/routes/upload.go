package routes

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os"

	"EverythingSuckz/fsb/config"
	"EverythingSuckz/fsb/internal/bot"
	"EverythingSuckz/fsb/internal/utils"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

type tgResponse struct {
	Ok          bool   `json:"ok"`
	Description string `json:"description"`
	ErrorCode   int    `json:"error_code"`
	Result      struct {
		MessageID int `json:"message_id"`
	} `json:"result"`
}

func (e *allRoutes) LoadUpload(r *Route) {
	log = e.log.Named("Upload")
	r.Engine.POST("/upload", uploadStreamRoute)
}

func uploadStreamRoute(ctx *gin.Context) {
	file, header, err := ctx.Request.FormFile("file")
	if err != nil {
		ctx.JSON(http.StatusBadRequest, gin.H{"success": false, "error": "Falta el archivo en el campo 'file'"})
		return
	}
	defer file.Close()

	log.Sugar().Infof("Archivo recibido para subir: %s (Tamaño: %d)", header.Filename, header.Size)

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	logChannel := os.Getenv("LOG_CHANNEL")
	if logChannel == "" {
		logChannel = fmt.Sprintf("-100%d", config.ValueOf.LogChannelID)
	}

	err = writer.WriteField("chat_id", logChannel)
	if err != nil {
		ctx.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": "Error interno"})
		return
	}

	part, err := writer.CreateFormFile("document", header.Filename)
	if err != nil {
		ctx.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": "Error interno creando documento"})
		return
	}

	_, err = io.Copy(part, file)
	if err != nil {
		ctx.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": "Error leyendo archivo"})
		return
	}
	writer.Close()

	url := fmt.Sprintf("https://api.telegram.org/bot%s/sendDocument", config.ValueOf.BotToken)
	req, err := http.NewRequest("POST", url, body)
	if err != nil {
		ctx.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": "Error preparando petici\u00f3n a Telegram"})
		return
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		log.Error("Error enviando a Telegram", zap.Error(err))
		ctx.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": "Error enviando a Telegram"})
		return
	}
	defer resp.Body.Close()

	bodyBytes, _ := io.ReadAll(resp.Body)
	var tgRes tgResponse
	if err := json.Unmarshal(bodyBytes, &tgRes); err != nil {
		log.Error("Error decoding Telegram response", zap.Error(err), zap.String("body", string(bodyBytes)))
		ctx.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": "Error decodificando respuesta de Telegram"})
		return
	}

	if !tgRes.Ok || tgRes.Result.MessageID == 0 {
		log.Error("Telegram rejected the file or upload failed", zap.Any("response", tgRes))
		errorMsg := fmt.Sprintf("Telegram rechazó el archivo: %s (Code: %d)", tgRes.Description, tgRes.ErrorCode)
		ctx.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": errorMsg})
		return
	}

	messageID := tgRes.Result.MessageID
	worker := bot.GetNextWorker()

	tgFile, err := utils.FileFromMessage(ctx.Request.Context(), worker.Client, messageID)
	if err != nil {
		log.Error("Failed to get file properties", zap.Error(err))
		ctx.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": "Error obteniendo propiedades de Telegram. " + err.Error()})
		return
	}

	expectedHash := utils.PackFile(
		tgFile.FileName,
		tgFile.FileSize,
		tgFile.MimeType,
		tgFile.ID,
	)
	hash := utils.GetShortHash(expectedHash)

	localLink := fmt.Sprintf("http://127.0.0.1:%d/stream/%d?hash=%s", config.ValueOf.Port, messageID, hash)
	hfLink := fmt.Sprintf("https://codebydante-brodyfilestreambot.hf.space/stream/%d?hash=%s", messageID, hash)

	ctx.JSON(http.StatusOK, gin.H{
		"success":    true,
		"message_id": messageID,
		"hash":       hash,
		"url":        hfLink,
		"local_url":  localLink,
	})
}
