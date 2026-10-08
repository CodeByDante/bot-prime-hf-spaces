package commands

import (
	"fmt"
	"strings"

	"EverythingSuckz/fsb/config"
	"EverythingSuckz/fsb/internal/utils"

	"github.com/celestix/gotgproto/dispatcher"
	"github.com/celestix/gotgproto/dispatcher/handlers"
	"github.com/celestix/gotgproto/ext"
	"github.com/celestix/gotgproto/storage"
	"github.com/celestix/gotgproto/types"
	"github.com/gotd/td/tg"
)

func (m *command) LoadStream(dispatcher dispatcher.Dispatcher) {
	log := m.log.Named("start")
	defer log.Sugar().Info("Loaded")
	dispatcher.AddHandler(
		handlers.NewMessage(nil, sendLink),
	)
}

func supportedMediaFilter(m *types.Message) (bool, error) {
	if not := m.Media == nil; not {
		return false, dispatcher.EndGroups
	}
	switch m.Media.(type) {
	case *tg.MessageMediaDocument:
		return true, nil
	case *tg.MessageMediaPhoto:
		return true, nil
	case tg.MessageMediaClass:
		return false, dispatcher.EndGroups
	default:
		return false, nil
	}
}

func sendLink(ctx *ext.Context, u *ext.Update) error {
	chatId := u.EffectiveChat().GetID()
	peerChatId := ctx.PeerStorage.GetPeerById(chatId)
	if peerChatId.Type != int(storage.TypeUser) {
		return dispatcher.EndGroups
	}
	if len(config.ValueOf.AllowedUsers) != 0 && !utils.Contains(config.ValueOf.AllowedUsers, chatId) {
		ctx.Reply(u, ext.ReplyTextString("No tienes permiso para usar este bot."), nil)
		return dispatcher.EndGroups
	}
	supported, err := supportedMediaFilter(u.EffectiveMessage)
	if err != nil {
		return err
	}
	if !supported {
		ctx.Reply(u, ext.ReplyTextString("Lo siento, este tipo de archivo no es compatible."), nil)
		return dispatcher.EndGroups
	}
	update, err := utils.ForwardMessages(ctx, chatId, config.ValueOf.LogChannelID, u.EffectiveMessage.ID)
	if err != nil {
		utils.Logger.Sugar().Error(err)
		ctx.Reply(u, ext.ReplyTextString(fmt.Sprintf("Error - %s", err.Error())), nil)
		return dispatcher.EndGroups
	}
	if len(update.Updates) < 2 {
		ctx.Reply(u, ext.ReplyTextString("Error - estructura de actualización de Telegram inesperada"), nil)
		return dispatcher.EndGroups
	}
	msgIDUpdate, ok := update.Updates[0].(*tg.UpdateMessageID)
	if !ok {
		ctx.Reply(u, ext.ReplyTextString("Error - tipo de actualización inesperado"), nil)
		return dispatcher.EndGroups
	}
	messageID := msgIDUpdate.ID
	newMsg, ok := update.Updates[1].(*tg.UpdateNewChannelMessage)
	if !ok {
		ctx.Reply(u, ext.ReplyTextString("Error - mensaje de canal inesperado"), nil)
		return dispatcher.EndGroups
	}
	msg, ok := newMsg.Message.(*tg.Message)
	if !ok {
		ctx.Reply(u, ext.ReplyTextString("Error - tipo de mensaje inesperado"), nil)
		return dispatcher.EndGroups
	}
	doc := msg.Media
	file, err := utils.FileFromMedia(doc)
	if err != nil {
		ctx.Reply(u, ext.ReplyTextString(fmt.Sprintf("Error - %s", err.Error())), nil)
		return dispatcher.EndGroups
	}
	fullHash := utils.PackFile(
		file.FileName,
		file.FileSize,
		file.MimeType,
		file.ID,
	)
	hash := utils.GetShortHash(fullHash)
	
	localLink := fmt.Sprintf("http://127.0.0.1:%d/stream/%d?hash=%s", config.ValueOf.Port, messageID, hash)
	hfLink := fmt.Sprintf("https://codebydante-brodyfilestreambot.hf.space/stream/%d?hash=%s", messageID, hash)
	
	localDownloadText := localLink + "&d=true"
	hfDownloadText := hfLink + "&d=true"

	var textLines []string
	textLines = append(textLines, "🖥 Para tu PC Local (Pruebas):")
	textLines = append(textLines, "📁 Descargar:")
	textLines = append(textLines, localDownloadText)
	textLines = append(textLines, "📁 Reproducir / Ver:")
	textLines = append(textLines, localLink)

	textLines = append(textLines, "\n🚀 Para Hugging Face (Público):")
	textLines = append(textLines, "📁 Descargar:")
	textLines = append(textLines, hfDownloadText)
	textLines = append(textLines, "📁 Reproducir / Ver:")
	textLines = append(textLines, hfLink)
	
	textPlain := strings.Join(textLines, "\n")
	
	var rows []tg.KeyboardButtonRow
	
	// Fila Local
	localRow := tg.KeyboardButtonRow{
		Buttons: []tg.KeyboardButtonClass{
			&tg.KeyboardButtonURL{
				Text: "🖥 Descargar",
				URL:  localDownloadText,
			},
			&tg.KeyboardButtonURL{
				Text: "🖥 Ver / Reproducir",
				URL:  localLink,
			},
		},
	}
	rows = append(rows, localRow)

	// Fila Hugging Face
	hfRow := tg.KeyboardButtonRow{
		Buttons: []tg.KeyboardButtonClass{
			&tg.KeyboardButtonURL{
				Text: "🚀 Descargar",
				URL:  hfDownloadText,
			},
			&tg.KeyboardButtonURL{
				Text: "🚀 Ver / Reproducir",
				URL:  hfLink,
			},
		},
	}
	rows = append(rows, hfRow)
	
	markup := &tg.ReplyInlineMarkup{
		Rows: rows,
	}
	
	_, err = ctx.Reply(u, ext.ReplyTextString(textPlain), &ext.ReplyOpts{
		Markup:           markup,
		NoWebpage:        true,
		ReplyToMessageId: u.EffectiveMessage.ID,
	})
	if err != nil {
		utils.Logger.Sugar().Error(err)
		ctx.Reply(u, ext.ReplyTextString(fmt.Sprintf("Error - %s", err.Error())), nil)
	}
	return dispatcher.EndGroups
}
