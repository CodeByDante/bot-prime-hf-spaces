package commands

import (
	"fmt"
	"regexp"
	"strings"

	"github.com/celestix/gotgproto/dispatcher"
	"github.com/celestix/gotgproto/dispatcher/handlers"
	"github.com/celestix/gotgproto/ext"
	"go.uber.org/zap"
)

var (
	isAddTokenMode = false
	botTokenRegex  = regexp.MustCompile(`^\d{9,10}:[A-Za-z0-9_-]{35}$`) // Standard Telegram bot token format
)

func (c *command) AddTokenOn(d dispatcher.Dispatcher) {
	d.AddHandler(handlers.NewCommand("add_token_on", func(ctx *ext.Context, u *ext.Update) error {
		isAddTokenMode = true
		c.log.Sugar().Info("Add token mode activated")
		_, err := ctx.Reply(u, ext.ReplyTextString("✅ Modo para añadir tokens activado. Envía tokens de bot (uno por mensaje) y los guardaré en la base de datos de Firebase."), nil)
		return err
	}))
}

func (c *command) AddTokenOff(d dispatcher.Dispatcher) {
	d.AddHandler(handlers.NewCommand("add_token_off", func(ctx *ext.Context, u *ext.Update) error {
		isAddTokenMode = false
		c.log.Sugar().Info("Add token mode deactivated")
		_, err := ctx.Reply(u, ext.ReplyTextString("❌ Modo para añadir tokens desactivado."), nil)
		return err
	}))
}

func (c *command) ListTokens(d dispatcher.Dispatcher) {
	d.AddHandler(handlers.NewCommand("list", func(ctx *ext.Context, u *ext.Update) error {
		if GetWorkerListFunc == nil {
			_, err := ctx.Reply(u, ext.ReplyTextString("❌ El sistema de lista de tokens no está conectado."), nil)
			return err
		}
		listText := GetWorkerListFunc(true)
		_, err := ctx.Reply(u, ext.ReplyTextString(listText), nil)
		return err
	}))
}

func (c *command) HandleBotTokenMessage(d dispatcher.Dispatcher) {
	d.AddHandlerToGroup(
		handlers.NewMessage(nil, func(ctx *ext.Context, u *ext.Update) error {
			if !isAddTokenMode {
				return nil
			}

			if u.EffectiveMessage == nil {
				return nil
			}

			messageText := u.EffectiveMessage.Message.Message
			if messageText == "" {
				return nil
			}

			// Validate if message looks like a token
			token := strings.TrimSpace(messageText)
			if !botTokenRegex.MatchString(token) {
				// Not a token, ignore
				return nil
			}

			c.log.Sugar().Infof("Received a new bot token: %s", token)

			if SaveTokenFunc == nil || StartWorkerFunc == nil {
				_, err := ctx.Reply(u, ext.ReplyTextString("❌ El sistema de tokens dinámicos no está listo."), nil)
				return err
			}

			// 1. Save it to Firebase
			err := SaveTokenFunc(token)
			if err != nil {
				if strings.Contains(err.Error(), "ya existe") {
					_, _ = ctx.Reply(u, ext.ReplyTextString("⚠️ Este token ya está registrado en Firebase."), nil)
				} else {
					c.log.Error("Failed to save token to firebase", zap.Error(err))
					_, _ = ctx.Reply(u, ext.ReplyTextString("❌ Error al guardar el token en Firebase: "+err.Error()), nil)
				}
				return nil
			}

			// Respond immediately to stop the webhook from retrying and causing duplicates
			_, _ = ctx.Reply(u, ext.ReplyTextString("⏳ El token ha sido guardado exitosamente en Firebase. Conectando al Servidor de Telegram..."), nil)

			// 2. Add it to the dynamic worker pool in the background
			go func(t string) {
				username, startErr := StartWorkerFunc(t)
				if startErr != nil {
					c.log.Error("Failed to start worker with new token", zap.Error(startErr))
					_, _ = ctx.Reply(u, ext.ReplyTextString("⚠️ El bot se guardó, pero falló al unirse (¿Token inválido?): "+startErr.Error()), nil)
				} else {
					successText := fmt.Sprintf("@%s\n`%s`\n\nse agrego correctamente al fire base", username, t)
					_, _ = ctx.Reply(u, ext.ReplyTextString(successText), nil)
				}
			}(token)

			return nil

		}), -1) // Group -1 para que atrape los mensajes ANTES que el handler de streams del Group 0
}
