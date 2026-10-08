package commands

import (
	"bufio"
	"bytes"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"EverythingSuckz/fsb/config"
	"EverythingSuckz/fsb/internal/utils"

	"github.com/celestix/gotgproto/dispatcher"
	"github.com/celestix/gotgproto/ext"
	"github.com/gotd/td/telegram/downloader"
	"github.com/gotd/td/tg"
	"go.uber.org/zap"
)

type FileStreamSession struct {
	Active bool
	mu     sync.Mutex
}

var (
	fileStreamSessions = make(map[int64]*FileStreamSession)
	fileStreamMu       sync.Mutex
)

func ToggleFileStream(ctx *ext.Context, u *ext.Update) error {
	chatId := u.EffectiveChat().GetID()
	messageText := u.EffectiveMessage.Message.Message
	args := strings.Split(messageText, " ")
	cmd := strings.ToLower(args[0])

	var state string
	if strings.Contains(cmd, "on") {
		state = "on"
	} else if strings.Contains(cmd, "off") {
		state = "off"
	}

	if state == "" {
		_, _ = ctx.Reply(u, ext.ReplyTextString("Uso: /file_id_stream_on o /file_id_stream_off"), nil)
		return dispatcher.EndGroups
	}

	fileStreamMu.Lock()
	session, ok := fileStreamSessions[chatId]
	if !ok {
		session = &FileStreamSession{Active: false}
		fileStreamSessions[chatId] = session
	}
	fileStreamMu.Unlock()

	session.mu.Lock()
	defer session.mu.Unlock()

	if state == "on" {
		if session.Active {
			_, _ = ctx.Reply(u, ext.ReplyTextString("File Stream ya está activado."), nil)
			return dispatcher.EndGroups
		}
		session.Active = true
		_, _ = ctx.Reply(u, ext.ReplyTextString("✅ File Stream activado. Envía tu archivo .txt con File IDs."), nil)
		return dispatcher.EndGroups
	} else if state == "off" {
		if !session.Active {
			_, _ = ctx.Reply(u, ext.ReplyTextString("File Stream ya está desactivado."), nil)
			return dispatcher.EndGroups
		}
		session.Active = false
		_, _ = ctx.Reply(u, ext.ReplyTextString("❌ File Stream desactivado."), nil)
		return dispatcher.EndGroups
	}

	return dispatcher.EndGroups
}

func GetFileStreamSession(chatId int64) *FileStreamSession {
	fileStreamMu.Lock()
	defer fileStreamMu.Unlock()
	return fileStreamSessions[chatId]
}

type ParsedFileItem struct {
	Type      string // "ORIGINAL" or "WEBP"
	Name      string
	MessageID int
	HFLink    string
	LocalLink string
}

func HandleFileStreamFile(chatId int64, ctx *ext.Context, u *ext.Update, fileMedia interface{}) error {
	fileDoc, err := utils.FileFromMedia(fileMedia.(tg.MessageMediaClass))
	if err != nil {
		_, _ = ctx.Reply(u, ext.ReplyTextString(fmt.Sprintf("Error obteniendo media de telegram: %v", err)), nil)
		return err
	}

	// Download the .txt file
	d := downloader.NewDownloader()
	var docBuf bytes.Buffer
	_, err = d.Download(ctx.Raw, fileDoc.Location).Stream(ctx.Context, &docBuf)
	if err != nil {
		_, _ = ctx.Reply(u, ext.ReplyTextString(fmt.Sprintf("Error descargando el archivo: %v", err)), nil)
		return err
	}

	fileBytes := docBuf.Bytes()

	// Parse the .txt content
	scanner := bufio.NewScanner(bytes.NewReader(fileBytes))
	var title string = "FileStream_Collection"
	var currentItem *ParsedFileItem
	var items []ParsedFileItem

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "--") {
			continue
		}

		if strings.HasPrefix(line, "=== Datos del ZIP: ") {
			titleRaw := strings.TrimPrefix(line, "=== Datos del ZIP: ")
			titleRaw = strings.TrimSuffix(titleRaw, " ===")
			title = strings.TrimSuffix(titleRaw, ".zip")
			title = strings.TrimSpace(title)
			continue
		}

		if strings.HasPrefix(line, "[ORIGINAL]") {
			if currentItem != nil && currentItem.MessageID != 0 {
				items = append(items, *currentItem)
			}
			currentItem = &ParsedFileItem{
				Type: "ORIGINAL",
				Name: strings.TrimSpace(strings.TrimPrefix(line, "[ORIGINAL]")),
			}
			continue
		}

		if strings.HasPrefix(line, "[WEBP]") {
			if currentItem != nil && currentItem.MessageID != 0 {
				items = append(items, *currentItem)
			}
			currentItem = &ParsedFileItem{
				Type: "WEBP",
				Name: strings.TrimSpace(strings.TrimPrefix(line, "[WEBP]")),
			}
			continue
		}

		if strings.HasPrefix(line, "[VIDEO]") {
			if currentItem != nil && currentItem.MessageID != 0 {
				items = append(items, *currentItem)
			}
			currentItem = &ParsedFileItem{
				Type: "VIDEO",
				Name: strings.TrimSpace(strings.TrimPrefix(line, "[VIDEO]")),
			}
			continue
		}

		if strings.HasPrefix(line, "Message ID (Canal):") {
			if currentItem != nil {
				idStr := strings.TrimSpace(strings.TrimPrefix(line, "Message ID (Canal):"))
				id, err := strconv.Atoi(idStr)
				if err == nil {
					currentItem.MessageID = id
				}
			}
			continue
		}
	}
	if currentItem != nil && currentItem.MessageID != 0 {
		items = append(items, *currentItem)
	}

	if len(items) == 0 {
		_, _ = ctx.Reply(u, ext.ReplyTextString("No se encontraron elementos válidos (Message ID) en el txt."), nil)
		return nil
	}

	// Send processing message
	loadingMsg, err := ctx.Reply(u, ext.ReplyTextString(fmt.Sprintf("Procesando %d archivos... Por favor espera.", len(items))), nil)
	
	channel, err := utils.GetLogChannelPeer(ctx.Context, ctx.Raw, ctx.PeerStorage)
	if err != nil {
		_, _ = ctx.Reply(u, ext.ReplyTextString(fmt.Sprintf("Error obteniendo el canal de log: %v", err)), nil)
		return err
	}

	for i := range items {
		// Add small delay to avoid hitting FloodWait limit too fast
		time.Sleep(200 * time.Millisecond)

		inputMessageID := tg.InputMessageClass(&tg.InputMessageID{ID: items[i].MessageID})
		messageRequest := tg.ChannelsGetMessagesRequest{Channel: channel, ID: []tg.InputMessageClass{inputMessageID}}
		res, err := ctx.Raw.ChannelsGetMessages(ctx.Context, &messageRequest)
		if err != nil {
			utils.Logger.Error("Failed to fetch message", zap.Error(err))
			continue
		}
		messages, ok := res.(*tg.MessagesChannelMessages)
		if !ok || len(messages.Messages) == 0 {
			utils.Logger.Error("Message not found or bad response")
			continue
		}
		message, ok := messages.Messages[0].(*tg.Message)
		if !ok {
			utils.Logger.Error("Message cast failed")
			continue
		}

		fileInfo, err := utils.FileFromMedia(message.Media)
		if err != nil {
			utils.Logger.Error("Failed to parse file media", zap.Error(err))
			continue
		}
		if err != nil {
			utils.Logger.Error("Failed to fetch message details for stream generation", zap.Int("messageId", items[i].MessageID), zap.Error(err))
			continue
		}
		fullHash := utils.PackFile(
			fileInfo.FileName,
			fileInfo.FileSize,
			fileInfo.MimeType,
			fileInfo.ID,
		)
		hash := utils.GetShortHash(fullHash)

		items[i].LocalLink = fmt.Sprintf("http://127.0.0.1:%d/stream/%d?hash=%s", config.ValueOf.Port, items[i].MessageID, hash)
		items[i].HFLink = fmt.Sprintf("https://codebydante-brodyfilestreambot.hf.space/stream/%d?hash=%s", items[i].MessageID, hash)
	}

	// Generate Text Content Output
	var webpItems []ParsedFileItem
	var originalItems []ParsedFileItem
	var videoItems []ParsedFileItem
	
	// Sort by name if desired, keeping original logic if preferred. User wants alphabetical "ordenando alfabeticamente" -> Yes we can do that!
	for _, it := range items {
		if it.LocalLink == "" {
			continue // skip failed ones
		}
		if it.Type == "WEBP" {
			webpItems = append(webpItems, it)
		} else if it.Type == "VIDEO" {
			videoItems = append(videoItems, it)
		} else {
			originalItems = append(originalItems, it)
		}
	}

	sort.Slice(webpItems, func(i, j int) bool {
		return webpItems[i].Name < webpItems[j].Name
	})
	sort.Slice(originalItems, func(i, j int) bool {
		return originalItems[i].Name < originalItems[j].Name
	})
	sort.Slice(videoItems, func(i, j int) bool {
		return videoItems[i].Name < videoItems[j].Name
	})

	var buf bytes.Buffer
	buf.WriteString(fmt.Sprintf("==== %s ====\n\n", title))

	if len(webpItems) > 0 {
		buf.WriteString("---- WEB P LINKS ----\n\n")
		buf.WriteString("🚀 Para Hugging Face (Público):\n")
		for i, f := range webpItems {
			buf.WriteString(fmt.Sprintf("(%d) %s = %s\n", i+1, f.Name, f.HFLink))
		}
		buf.WriteString("\n🖥 Para tu PC Local (Pruebas):\n")
		for i, f := range webpItems {
			buf.WriteString(fmt.Sprintf("(%d) %s = %s\n", i+1, f.Name, f.LocalLink))
		}
		buf.WriteString("\n----------------------------------\n\n")
	}

	if len(originalItems) > 0 {
		buf.WriteString("---- ORIGINAL LINKS ----\n\n")
		buf.WriteString("🚀 Para Hugging Face (Público):\n")
		for i, f := range originalItems {
			buf.WriteString(fmt.Sprintf("(%d) %s = %s\n", i+1, f.Name, f.HFLink))
		}
		buf.WriteString("\n🖥 Para tu PC Local (Pruebas):\n")
		for i, f := range originalItems {
			buf.WriteString(fmt.Sprintf("(%d) %s = %s\n", i+1, f.Name, f.LocalLink))
		}
		buf.WriteString("\n----------------------------------\n\n")
	}

	if len(videoItems) > 0 {
		buf.WriteString("---- VIDEO LINKS ----\n\n")
		buf.WriteString("🚀 Para Hugging Face (Público):\n")
		for i, f := range videoItems {
			buf.WriteString(fmt.Sprintf("(%d) %s = %s\n", i+1, f.Name, f.HFLink))
		}
		buf.WriteString("\n🖥 Para tu PC Local (Pruebas):\n")
		for i, f := range videoItems {
			buf.WriteString(fmt.Sprintf("(%d) %s = %s\n", i+1, f.Name, f.LocalLink))
		}
	}
	buf.WriteString("\n")

	// Save and send back text
	filename := title + ".txt"
	if err := utils.UploadToTG(ctx, chatId, buf.Bytes(), filename); err != nil {
		utils.Logger.Error("Failed to upload fileStream txt", zap.Error(err))
		_, _ = ctx.Reply(u, ext.ReplyTextString(fmt.Sprintf("Error enviando el archivo generado: %v", err)), nil)
	}

	// Delete loading msg
	if loadingMsg != nil {
		ctx.DeleteMessages(chatId, []int{loadingMsg.ID})
	}

	return nil
}
