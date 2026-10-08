package commands

import (
	"bytes"
	"fmt"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"

	"EverythingSuckz/fsb/internal/utils"

	"github.com/celestix/gotgproto/dispatcher"
	"github.com/celestix/gotgproto/ext"
	"go.uber.org/zap"
)

type MangaFile struct {
	OriginalName  string
	IsWebP        bool
	LocalLink     string
	LocalDownload string
	HFLink        string
	HFDownload    string
}

type MangaSession struct {
	Active bool
	Timer  *time.Timer
	Files  []MangaFile
	Ctx    *ext.Context
	Update *ext.Update
	mu     sync.Mutex
}

var (
	mangaflowSessions = make(map[int64]*MangaSession)
	mangaflowMu       sync.Mutex
)

func (m *command) LoadMangaFlow(dispatcher dispatcher.Dispatcher) {
	// Logic is now integrated into stream.go and start.go
}

func ToggleMangaFlow(ctx *ext.Context, u *ext.Update) error {
	chatId := u.EffectiveChat().GetID()
	messageText := u.EffectiveMessage.Message.Message
	args := strings.Split(messageText, " ")
	cmd := strings.ToLower(args[0])

	var state string
	if strings.Contains(cmd, "on") {
		state = "on"
	} else if strings.Contains(cmd, "off") {
		state = "off"
	} else if len(args) >= 2 {
		state = strings.ToLower(args[1])
	}

	if state == "" {
		_, _ = ctx.Reply(u, ext.ReplyTextString("Uso: /twistedbrodymangaflow on|off o usa los comandos rápidos del menú."), nil)
		return dispatcher.EndGroups
	}

	mangaflowMu.Lock()
	session, ok := mangaflowSessions[chatId]
	if !ok {
		session = &MangaSession{Active: false}
		mangaflowSessions[chatId] = session
	}
	mangaflowMu.Unlock()

	session.mu.Lock()
	defer session.mu.Unlock()

	if state == "on" {
		if session.Active {
			_, _ = ctx.Reply(u, ext.ReplyTextString("MangaFlow ya está activado."), nil)
			return dispatcher.EndGroups
		}
		session.Active = true
		_, _ = ctx.Reply(u, ext.ReplyTextString("✅ MangaFlow activado. Envía tus imágenes."), nil)
		return dispatcher.EndGroups
	} else if state == "off" {
		if !session.Active {
			_, _ = ctx.Reply(u, ext.ReplyTextString("MangaFlow ya está desactivado."), nil)
			return dispatcher.EndGroups
		}
		if session.Timer != nil {
			session.Timer.Stop()
			session.Timer = nil
		}
		// Process remaining files if any
		if len(session.Files) > 0 {
			go finishMangaSession(chatId, session)
		}
		session.Active = false
		_, _ = ctx.Reply(u, ext.ReplyTextString("❌ MangaFlow desactivado."), nil)
		return dispatcher.EndGroups
	}

	_, _ = ctx.Reply(u, ext.ReplyTextString("Uso: /twistedbrodymangaflow on|off"), nil)
	return dispatcher.EndGroups
}

func GetMangaSession(chatId int64) *MangaSession {
	mangaflowMu.Lock()
	defer mangaflowMu.Unlock()
	return mangaflowSessions[chatId]
}

func HandleMangaFlowFile(chatId int64, session *MangaSession, file MangaFile, ctx *ext.Context, u *ext.Update) {
	session.mu.Lock()
	defer session.mu.Unlock()

	session.Files = append(session.Files, file)
	session.Ctx = ctx
	session.Update = u

	if session.Timer != nil {
		session.Timer.Stop()
	}

	session.Timer = time.AfterFunc(2*time.Second, func() {
		finishMangaSession(chatId, session)
	})
}

func generateMangaText(files []MangaFile) string {
	// Sort files by OriginalName
	sort.Slice(files, func(i, j int) bool {
		return files[i].OriginalName < files[j].OriginalName
	})

	var webpFiles []MangaFile
	var originalFiles []MangaFile

	// Heuristic for title
	title := "MangaFlow_Collection"
	if len(files) > 0 {
		baseName := files[0].OriginalName
		re := regexp.MustCompile(`(?i)_pagina_\d+.*$`)
		cleaned := re.ReplaceAllString(baseName, "")
		if cleaned == "" {
			re2 := regexp.MustCompile(`(?i)\.(png|webp|jpg|jpeg)$`)
			cleaned = re2.ReplaceAllString(baseName, "")
		}
		if cleaned != "" {
			title = strings.TrimSuffix(cleaned, "_")
			title = strings.TrimSpace(title)
		}
	}

	for _, f := range files {
		if f.IsWebP {
			webpFiles = append(webpFiles, f)
		} else {
			originalFiles = append(originalFiles, f)
		}
	}

	var buf bytes.Buffer
	buf.WriteString(fmt.Sprintf("==== %s ====\n\n", title))

	if len(webpFiles) > 0 {
		buf.WriteString("---- WEB P LINKS ----\n\n")
		buf.WriteString("🚀 Para Hugging Face (Público):\n")
		for i, f := range webpFiles {
			buf.WriteString(fmt.Sprintf("(%d) %s = %s\n", i+1, f.OriginalName, f.HFLink))
		}
		buf.WriteString("\n🖥 Para tu PC Local (Pruebas):\n")
		for i, f := range webpFiles {
			buf.WriteString(fmt.Sprintf("(%d) %s = %s\n", i+1, f.OriginalName, f.LocalLink))
		}
		buf.WriteString("\n----------------------------------\n\n")
	}

	if len(originalFiles) > 0 {
		buf.WriteString("---- ORIGINAL LINKS ----\n\n")
		buf.WriteString("🚀 Para Hugging Face (Público):\n")
		for i, f := range originalFiles {
			buf.WriteString(fmt.Sprintf("(%d) %s = %s\n", i+1, f.OriginalName, f.HFLink))
		}
		buf.WriteString("\n🖥 Para tu PC Local (Pruebas):\n")
		for i, f := range originalFiles {
			buf.WriteString(fmt.Sprintf("(%d) %s = %s\n", i+1, f.OriginalName, f.LocalLink))
		}
	}
	buf.WriteString("\n")

	return buf.String()
}

func finishMangaSession(chatId int64, session *MangaSession) {
	session.mu.Lock()
	files := session.Files
	session.Files = nil
	session.Timer = nil
	ctx := session.Ctx
	u := session.Update
	session.mu.Unlock()

	if len(files) == 0 {
		return
	}

	textContent := generateMangaText(files)

	// Determine fileName
	fileName := "MangaFlow_Links.txt"
	if len(files) > 0 {
		baseName := files[0].OriginalName
		re := regexp.MustCompile(`(?i)_pagina_\d+.*$`)
		cleaned := re.ReplaceAllString(baseName, "")
		if cleaned == "" {
			re2 := regexp.MustCompile(`(?i)\.(png|webp|jpg|jpeg)$`)
			cleaned = re2.ReplaceAllString(baseName, "")
		}
		if cleaned != "" {
			fileName = fmt.Sprintf("%s.txt", strings.TrimSuffix(cleaned, "_"))
		}
	}

	// Send file back to user
	err := utils.UploadToTG(ctx, chatId, []byte(textContent), fileName)
	if err != nil {
		utils.Logger.Error("Failed to upload mangaflow txt", zap.Error(err))
		_, _ = ctx.Reply(u, ext.ReplyTextString(fmt.Sprintf("Error enviando el archivo: %v", err)), nil)
	}
}
