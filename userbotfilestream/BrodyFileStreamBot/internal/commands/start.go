package commands

import (
	"EverythingSuckz/fsb/config"
	"EverythingSuckz/fsb/internal/utils"

	"github.com/celestix/gotgproto/dispatcher"
	"github.com/celestix/gotgproto/dispatcher/handlers"
	"github.com/celestix/gotgproto/ext"
	"github.com/celestix/gotgproto/storage"
)

func (m *command) LoadStart(dispatcher dispatcher.Dispatcher) {
	log := m.log.Named("start")
	defer log.Sugar().Info("Loaded")
	dispatcher.AddHandler(handlers.NewCommand("start", start))
	dispatcher.AddHandler(handlers.NewCommand("twistedbrodymangaflow", ToggleMangaFlow))
	dispatcher.AddHandler(handlers.NewCommand("mangaflow_on", ToggleMangaFlow))
	dispatcher.AddHandler(handlers.NewCommand("mangaflow_off", ToggleMangaFlow))
	dispatcher.AddHandler(handlers.NewCommand("file_id_stream_on", ToggleFileStream))
	dispatcher.AddHandler(handlers.NewCommand("file_id_stream_off", ToggleFileStream))
}

func start(ctx *ext.Context, u *ext.Update) error {
	chatId := u.EffectiveChat().GetID()
	peerChatId := ctx.PeerStorage.GetPeerById(chatId)
	if peerChatId.Type != int(storage.TypeUser) {
		return dispatcher.EndGroups
	}
	if len(config.ValueOf.AllowedUsers) != 0 && !utils.Contains(config.ValueOf.AllowedUsers, chatId) {
		_, _ = ctx.Reply(u, ext.ReplyTextString("No tienes permiso para usar este bot."), nil)
		return dispatcher.EndGroups
	}

	_, _ = ctx.Reply(u, ext.ReplyTextString("Hola, envíame cualquier archivo para obtener un enlace directo a ese archivo."), nil)
	return dispatcher.EndGroups
}

func twistedbrodymangaflow(ctx *ext.Context, u *ext.Update) error {
	return ToggleMangaFlow(ctx, u)
}
