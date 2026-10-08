package routes

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"strconv"

	"EverythingSuckz/fsb/config"
	"EverythingSuckz/fsb/internal/bot"
	"EverythingSuckz/fsb/internal/utils"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

type tgResponse struct {
	Ok     bool `json:"ok"`
	Result struct {
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

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	err = writer.WriteField("chat_id", strconv.FormatInt(config.ValueOf.LogChannelID, 10))
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

	var tgRes tgResponse
	if err := json.NewDecoder(resp.Body).Decode(&tgRes); err != nil {
		log.Error("Error decoding Telegram response", zap.Error(err))
		ctx.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": "Error decodificando respuesta de Telegram"})
		return
	}

	if !tgRes.Ok || tgRes.Result.MessageID == 0 {
		log.Error("Telegram rejected the file or upload failed", zap.Any("response", tgRes))
		ctx.JSON(http.StatusInternalServerError, gin.H{"success": false, "error": "Telegram rechaz\u00f3 el archivo o subida fallida"})
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
