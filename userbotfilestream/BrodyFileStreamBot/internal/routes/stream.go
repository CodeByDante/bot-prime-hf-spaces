package routes

import (
	"EverythingSuckz/fsb/internal/bot"
	"EverythingSuckz/fsb/internal/stream"
	"EverythingSuckz/fsb/internal/types"
	"EverythingSuckz/fsb/internal/utils"
	"context"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"sync"
	"time"

	"github.com/gotd/td/tg"
	range_parser "github.com/quantumsheep/range-parser"
	"go.uber.org/zap"
	"golang.org/x/sync/semaphore"

	"github.com/gin-gonic/gin"
)

var log *zap.Logger

// Limitador de descargas simultaneas globales para evitar bloqueos por Flood
var downloadLimiter = semaphore.NewWeighted(60)

var dlMut sync.Mutex
var inProgress = make(map[string]bool)

func startBackgroundDownload(messageID int, loc tg.InputFileLocationClass, fileSize int64, destPath string, l *zap.Logger) {
	dlMut.Lock()
	if inProgress[destPath] {
		dlMut.Unlock()
		return
	}
	inProgress[destPath] = true
	dlMut.Unlock()

	go func() {
		defer func() {
			dlMut.Lock()
			delete(inProgress, destPath)
			dlMut.Unlock()
		}()

		if info, err := os.Stat(destPath); err == nil && !info.IsDir() {
			return // ya existe
		}
		
		tmpPath := destPath + ".tmp"
		f, err := os.Create(tmpPath)
		if err != nil {
			l.Error("Failed to create temp cache file", zap.Error(err))
			return
		}
		defer func() {
			f.Close()
			os.Remove(tmpPath)
		}()

		worker := bot.GetNextWorker()
		bgCtx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
		defer cancel()

		if err := downloadLimiter.Acquire(bgCtx, 1); err != nil {
			return
		}
		defer downloadLimiter.Release(1)

		pipe, err := stream.NewStreamPipe(bgCtx, worker.Client, messageID, loc, 0, fileSize-1, l)
		if err != nil {
			return
		}
		defer pipe.Close()

		if _, err := io.Copy(f, pipe); err != nil {
			l.Error("Error copying to cache file", zap.Error(err))
			return
		}
		f.Close()
		os.Rename(tmpPath, destPath)
		l.Sugar().Infof("✅ Archivo guardado en caché local en 2do plano: %s", destPath)
	}()
}

func (e *allRoutes) LoadHome(r *Route) {
	log = e.log.Named("Stream")
	defer log.Info("Loaded stream route")
	r.Engine.GET("/stream/:messageID", getStreamRoute)
	r.Engine.GET("/scene/:messageID/:sceneIndex", getSceneRoute)
}

func getStreamRoute(ctx *gin.Context) {
	w := ctx.Writer
	r := ctx.Request

	messageIDParm := ctx.Param("messageID")
	messageID, err := strconv.Atoi(messageIDParm)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	authHash := ctx.Query("hash")
	if authHash == "" {
		http.Error(w, "missing hash param", http.StatusBadRequest)
		return
	}

	worker := bot.GetNextWorker()
	log.Sugar().Infof("✅ Asignando petición de stream (MessageID: %d) al worker: @%s", messageID, worker.Self.Username)

	reqCtx := r.Context()

	file, err := utils.TimeFuncWithResult(log, "FileFromMessage", func() (*types.File, error) {
		// Pasa el contexto de la petición real para que si el cliente cierra la ventana, se aborte el fetch
		return utils.FileFromMessage(reqCtx, worker.Client, messageID)
	})
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	expectedHash := utils.PackFile(
		file.FileName,
		file.FileSize,
		file.MimeType,
		file.ID,
	)
	if !utils.CheckHash(authHash, expectedHash) {
		http.Error(w, "invalid hash", http.StatusBadRequest)
		return
	}

	isThumb := ctx.Query("thumb") == "true"
	if isThumb {
		thumbFile, err := utils.ThumbFromMessage(reqCtx, worker.Client, messageID)
		if err != nil {
			http.Error(w, fmt.Sprintf("failed to get thumbnail: %v", err), http.StatusInternalServerError)
			return
		}
		file = thumbFile
	}

	var cacheFilePath string
	if isThumb {
		cacheFilePath = filepath.Join("hf_cache", fmt.Sprintf("%d_%s_thumb.jpg", messageID, authHash))
	} else {
		cacheFilePath = filepath.Join("hf_cache", fmt.Sprintf("%d_%s", messageID, authHash))
	}
	if info, err := os.Stat(cacheFilePath); err == nil && !info.IsDir() {
		now := time.Now()
		os.Chtimes(cacheFilePath, now, now) // Renovar expiración

		log.Sugar().Infof("⚡ Servido instantáneo desde disco caché: %s", cacheFilePath)
		ctx.Header("Content-Disposition", fmt.Sprintf("inline; filename=\"%s\"", file.FileName))
		if r.Method != "HEAD" {
			http.ServeFile(w, r, cacheFilePath)
		}
		return
	}

	// for photo messages
	if file.FileSize == 0 {
		// Adquirir semáforo antes de pedir datos a Telegram
		if err := downloadLimiter.Acquire(reqCtx, 1); err != nil {
			http.Error(w, "server too busy", http.StatusTooManyRequests)
			return
		}
		res, err := worker.Client.API().UploadGetFile(reqCtx, &tg.UploadGetFileRequest{
			Location: file.Location,
			Offset:   0,
			Limit:    1024 * 1024,
		})
		downloadLimiter.Release(1)
		
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		result, ok := res.(*tg.UploadFile)
		if !ok {
			http.Error(w, "unexpected response", http.StatusInternalServerError)
			return
		}
		fileBytes := result.GetBytes()
		
		go func() {
			os.WriteFile(cacheFilePath, fileBytes, 0644)
		}()

		ctx.Header("Content-Disposition", fmt.Sprintf("inline; filename=\"%s\"", file.FileName))
		if r.Method != "HEAD" {
			ctx.Data(http.StatusOK, file.MimeType, fileBytes)
		}
		return
	}

	ctx.Header("Accept-Ranges", "bytes")
	var start, end int64
	rangeHeader := r.Header.Get("Range")

	if rangeHeader == "" {
		start = 0
		end = file.FileSize - 1
		w.WriteHeader(http.StatusOK)
	} else {
		ranges, err := range_parser.Parse(file.FileSize, r.Header.Get("Range"))
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		start = ranges[0].Start
		end = ranges[0].End
		ctx.Header("Content-Range", fmt.Sprintf("bytes %d-%d/%d", start, end, file.FileSize))
		log.Info("Content-Range", zap.Int64("start", start), zap.Int64("end", end), zap.Int64("fileSize", file.FileSize))
		w.WriteHeader(http.StatusPartialContent)
	}

	contentLength := end - start + 1
	mimeType := file.MimeType

	if mimeType == "" {
		mimeType = "application/octet-stream"
	}

	ctx.Header("Content-Type", mimeType)
	ctx.Header("Content-Length", strconv.FormatInt(contentLength, 10))

	disposition := "inline"

	if ctx.Query("d") == "true" {
		disposition = "attachment"
	}

	ctx.Header("Content-Disposition", fmt.Sprintf("%s; filename=\"%s\"", disposition, file.FileName))

	if r.Method != "HEAD" {
		startBackgroundDownload(messageID, file.Location, file.FileSize, cacheFilePath, log.Named("BgDownloader"))

		// Pasamos el reqCtx aquí para que corte la Tubería y las peticiones si el usuario se desconecta
		pipe, err := stream.NewStreamPipe(reqCtx, worker.Client, messageID, file.Location, start, end, log)
		if err != nil {
			log.Error("Failed to create stream pipe", zap.Error(err))
			return
		}
		defer pipe.Close()

		// Adquirir semáforo durante el streaming del archivo
		if err := downloadLimiter.Acquire(reqCtx, 1); err != nil {
			http.Error(w, "server too busy", http.StatusTooManyRequests)
			return
		}
		defer downloadLimiter.Release(1)

		if _, err := io.CopyN(w, pipe, contentLength); err != nil {
			if !utils.IsClientDisconnectError(err) && err != stream.ErrPipeDrained {
				log.Error("Error while copying stream", zap.Error(err))
			}
		}
	}
}

func getSceneRoute(ctx *gin.Context) {
	w := ctx.Writer
	r := ctx.Request

	messageIDParm := ctx.Param("messageID")
	messageID, err := strconv.Atoi(messageIDParm)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	sceneIndexParm := ctx.Param("sceneIndex")
	sceneIndex, err := strconv.Atoi(sceneIndexParm)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	authHash := ctx.Query("hash")
	if authHash == "" {
		http.Error(w, "missing hash param", http.StatusBadRequest)
		return
	}

	worker := bot.GetNextWorker()
	reqCtx := r.Context()

	// 1. Get video metadata to validate hash
	file, err := utils.TimeFuncWithResult(log, "FileFromMessage", func() (*types.File, error) {
		return utils.FileFromMessage(reqCtx, worker.Client, messageID)
	})
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	expectedHash := utils.PackFile(
		file.FileName,
		file.FileSize,
		file.MimeType,
		file.ID,
	)
	if !utils.CheckHash(authHash, expectedHash) {
		http.Error(w, "invalid hash", http.StatusBadRequest)
		return
	}

	// 2. Fetch scene file location
	sceneFile, err := utils.SceneFromMessage(reqCtx, worker.Client, messageID, sceneIndex)
	if err != nil {
		http.Error(w, fmt.Sprintf("failed to get scene: %v", err), http.StatusInternalServerError)
		return
	}

	cacheFilePath := filepath.Join("hf_cache", fmt.Sprintf("scene_%d_%d_%s.jpg", messageID, sceneIndex, authHash))
	if info, err := os.Stat(cacheFilePath); err == nil && !info.IsDir() {
		now := time.Now()
		os.Chtimes(cacheFilePath, now, now) // Renew expiration
		ctx.Header("Content-Disposition", fmt.Sprintf("inline; filename=\"%s\"", sceneFile.FileName))
		if r.Method != "HEAD" {
			http.ServeFile(w, r, cacheFilePath)
		}
		return
	}

	// Serve and cache scene file
	ctx.Header("Content-Type", "image/jpeg")
	ctx.Header("Content-Disposition", fmt.Sprintf("inline; filename=\"%s\"", sceneFile.FileName))

	if r.Method != "HEAD" {
		startBackgroundDownload(messageID, sceneFile.Location, sceneFile.FileSize, cacheFilePath, log.Named("SceneBgDownloader"))
		
		pipe, err := stream.NewStreamPipe(reqCtx, worker.Client, messageID, sceneFile.Location, 0, sceneFile.FileSize-1, log)
		if err != nil {
			log.Error("Failed to create stream pipe for scene", zap.Error(err))
			return
		}
		defer pipe.Close()

		if err := downloadLimiter.Acquire(reqCtx, 1); err != nil {
			http.Error(w, "server too busy", http.StatusTooManyRequests)
			return
		}
		defer downloadLimiter.Release(1)

		if _, err := io.Copy(w, pipe); err != nil {
			if !utils.IsClientDisconnectError(err) && err != stream.ErrPipeDrained {
				log.Error("Error while copying scene stream", zap.Error(err))
			}
		}
	}
}

