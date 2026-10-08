package commands

import (
	"EverythingSuckz/fsb/config"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"reflect"

	"github.com/celestix/gotgproto/dispatcher"
	"go.uber.org/zap"
)

var (
	SaveTokenFunc     func(string) error
	StartWorkerFunc   func(token string) (string, error)
	LoadTokensFunc    func() ([]string, error)
	GetWorkerListFunc func(bool) string
)

type command struct {
	log *zap.Logger
}

func Load(log *zap.Logger, dispatcher dispatcher.Dispatcher) {
	log = log.Named("commands")
	defer log.Info("Initialized all command handlers")
	Type := reflect.TypeOf(&command{log})
	Value := reflect.ValueOf(&command{log})
	for i := 0; i < Type.NumMethod(); i++ {
		Type.Method(i).Func.Call([]reflect.Value{Value, reflect.ValueOf(dispatcher)})
	}
}

func RegisterCommands() error {
	type botCommand struct {
		Command     string `json:"command"`
		Description string `json:"description"`
	}

	commands := []botCommand{
		{
			Command:     "start",
			Description: "⚙️ Menú Principal",
		},
		{
			Command:     "mangaflow_on",
			Description: "✅ Activar MangaFlow",
		},
		{
			Command:     "mangaflow_off",
			Description: "❌ Desactivar MangaFlow",
		},
		{
			Command:     "file_id_stream_on",
			Description: "✅ Activar File Stream",
		},
		{
			Command:     "file_id_stream_off",
			Description: "❌ Desactivar File Stream",
		},
		{
			Command:     "add_token_on",
			Description: "📝 Añadir Token Extra",
		},
		{
			Command:     "add_token_off",
			Description: "❌ Desactivar Añadir Token",
		},
		{
			Command:     "list",
			Description: "📋 Lista de Tokens Dinámicos",
		},
	}

	cmdBytes, _ := json.Marshal(commands)
	reqUrl := fmt.Sprintf("https://api.telegram.org/bot%s/setMyCommands?commands=%s", config.ValueOf.BotToken, url.QueryEscape(string(cmdBytes)))

	resp, err := http.Get(reqUrl)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("failed to set commands: %s", string(body))
	}
	return nil
}
