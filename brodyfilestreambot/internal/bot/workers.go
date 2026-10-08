package bot

import (
	"EverythingSuckz/fsb/config"
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	firebase "firebase.google.com/go/v4"
	"google.golang.org/api/option"

	"github.com/celestix/gotgproto"
	"github.com/celestix/gotgproto/sessionMaker"
	"github.com/glebarez/sqlite"
	"github.com/gotd/td/tg"
	"go.uber.org/zap"
)

type Worker struct {
	ID     int
	Client *gotgproto.Client
	Self   *tg.User
	Token  string
	log    *zap.Logger
}

func (w *Worker) String() string {
	return fmt.Sprintf("{Worker (%d|@%s)}", w.ID, w.Self.Username)
}

type BotWorkers struct {
	Bots     []*Worker
	starting int
	index    int
	mut      sync.Mutex
	log      *zap.Logger
}

var Workers *BotWorkers = &BotWorkers{
	log:  nil,
	Bots: make([]*Worker, 0),
}

func (w *BotWorkers) Init(log *zap.Logger) {
	w.log = log.Named("Workers")
}

func (w *BotWorkers) AddDefaultClient(client *gotgproto.Client, self *tg.User) {
	if w.Bots == nil {
		w.Bots = make([]*Worker, 0)
	}
	w.incStarting()
	w.Bots = append(w.Bots, &Worker{
		Client: client,
		ID:     w.starting,
		Self:   self,
		Token:  config.ValueOf.BotToken,
		log:    w.log,
	})
	w.log.Sugar().Info("Default bot loaded")
}

func (w *BotWorkers) incStarting() {
	w.mut.Lock()
	defer w.mut.Unlock()
	w.starting++
}

func (w *BotWorkers) Add(token string) (string, error) {
	w.mut.Lock()
	for _, b := range w.Bots {
		if b.Token == token {
			w.mut.Unlock()
			return "", fmt.Errorf("el token ya existe en la lista de workers")
		}
	}
	w.mut.Unlock()

	w.incStarting()
	var botID int = w.starting
	client, err := startWorker(w.log, token, botID)
	if err != nil {
		return "", err
	}
	w.log.Sugar().Infof("Bot @%s loaded with ID %d", client.Self.Username, botID)
	w.mut.Lock()
	w.Bots = append(w.Bots, &Worker{
		Client: client,
		ID:     botID,
		Self:   client.Self,
		Token:  token,
		log:    w.log,
	})
	
	w.mut.Unlock()
	
	return client.Self.Username, nil
}

func GetNextWorker() *Worker {
	Workers.mut.Lock()
	defer Workers.mut.Unlock()
	index := (Workers.index + 1) % len(Workers.Bots)
	Workers.index = index
	worker := Workers.Bots[index]
	Workers.log.Sugar().Debugf("Using worker %d", worker.ID)
	return worker
}

func StartWorkers(log *zap.Logger) (*BotWorkers, error) {
	Workers.Init(log)

	// Fetch dynamic tokens from Firebase
	var dynamicTokens []string
	if config.ValueOf.FirebaseJSON != "" {
		dynamicTokens, _ = Workers.LoadTokensFromFirebase()
	}

	allTokens := append(config.ValueOf.MultiTokens, dynamicTokens...)

	if len(allTokens) == 0 {
		Workers.log.Sugar().Info("No worker bot tokens provided, skipping worker initialization")
		return Workers, nil
	}
	Workers.log.Sugar().Info("Starting workers")
	if config.ValueOf.UseSessionFile {
		Workers.log.Sugar().Info("Using session file for workers")
		newpath := filepath.Join(".", "sessions")
		if err := os.MkdirAll(newpath, os.ModePerm); err != nil {
			Workers.log.Error("Failed to create sessions directory", zap.Error(err))
			return nil, err
		}
	}

	var wg sync.WaitGroup
	var successfulStarts int32
	totalBots := len(allTokens)

	for i := 0; i < totalBots; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()

			ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
			defer cancel()

			done := make(chan error, 1)
			go func() {
				_, err := Workers.Add(allTokens[i])
				done <- err
			}()

			select {
			case err := <-done:
				if err != nil {
					Workers.log.Error("Failed to start worker", zap.Int("index", i), zap.Error(err))
				} else {
					atomic.AddInt32(&successfulStarts, 1)
				}
			case <-ctx.Done():
				Workers.log.Error("Timed out starting worker", zap.Int("index", i))
			}
		}(i)
	}

	wg.Wait() // Wait for all goroutines to finish
	Workers.log.Sugar().Infof("Successfully started %d/%d bots", successfulStarts, totalBots)

	if len(dynamicTokens) > 0 {
		fmt.Println("\n🔥 [Firebase] Conectado exitosamente a Firestore.")
		fmt.Println(Workers.GetWorkerListText(true))
	}
	return Workers, nil
}

func (w *BotWorkers) GetWorkerListText(onlyDynamic bool) string {
	w.mut.Lock()
	defer w.mut.Unlock()
	
	var envBots []*Worker
	var dynamicBots []*Worker

	envTokensMap := make(map[string]bool)
	for _, t := range config.ValueOf.MultiTokens {
		envTokensMap[t] = true
	}

	for _, b := range w.Bots {
		if b.Token == config.ValueOf.BotToken {
			continue
		}
		if envTokensMap[b.Token] {
			envBots = append(envBots, b)
		} else {
			dynamicBots = append(dynamicBots, b)
		}
	}

	var sb strings.Builder
	if len(envBots) > 0 {
		sb.WriteString(fmt.Sprintf("⚙️ **Lista de %d Tokens Estáticos (.env):**\n\n", len(envBots)))
		for i, b := range envBots {
			sb.WriteString(fmt.Sprintf("%d️⃣ @%s\n`%s`\n\n", i+1, b.Self.Username, b.Token))
		}
	}

	if len(dynamicBots) > 0 {
		sb.WriteString(fmt.Sprintf("📋 **Lista de %d Tokens Dinámicos (Firebase):**\n\n", len(dynamicBots)))
		for i, b := range dynamicBots {
			sb.WriteString(fmt.Sprintf("%d️⃣ @%s\n`%s`\n\n", i+1, b.Self.Username, b.Token))
		}
	} else if len(envBots) == 0 {
		return "ℹ️ No hay tokens adicionales configurados (ni dinámicos ni estáticos)."
	}
	
	return strings.TrimSpace(sb.String())
}

func startWorker(l *zap.Logger, botToken string, index int) (*gotgproto.Client, error) {
	log := l.Named("Worker").Sugar()
	log.Infof("Starting worker with index - %d", index)
	var sessionType sessionMaker.SessionConstructor
	if config.ValueOf.UseSessionFile {
		// Use the Bot ID (first part of token) as the session filename
		// This prevents sessions from shuffling if order changes, which causes wrong usernames.
		sessionID := fmt.Sprintf("%d", index)
		if parts := strings.Split(botToken, ":"); len(parts) == 2 {
			sessionID = parts[0]
		}
		sessionType = sessionMaker.SqlSession(sqlite.Open(fmt.Sprintf("sessions/worker-%s.session", sessionID)))
	} else {
		sessionType = sessionMaker.SimpleSession()
	}
	client, err := gotgproto.NewClient(
		int(config.ValueOf.ApiID),
		config.ValueOf.ApiHash,
		gotgproto.ClientTypeBot(botToken),
		&gotgproto.ClientOpts{
			Session:          sessionType,
			DisableCopyright: true,
			Middlewares:      GetFloodMiddleware(log.Desugar()),
		},
	)
	if err != nil {
		return nil, err
	}
	return client, nil
}

// SaveTokenToFirebase connects to Firestore and saves a bot token.
func (w *BotWorkers) SaveTokenToFirebase(token string) error {
	if config.ValueOf.FirebaseJSON == "" {
		return fmt.Errorf("FIREBASE_JSON env var is empty, cannot save token dynamically")
	}

	ctx := context.Background()
	opt := option.WithCredentialsJSON([]byte(config.ValueOf.FirebaseJSON))
	app, err := firebase.NewApp(ctx, nil, opt)
	if err != nil {
		return fmt.Errorf("error initializing firebase: %v", err)
	}

	client, err := app.Firestore(ctx)
	if err != nil {
		return fmt.Errorf("error connecting to firestore: %v", err)
	}
	defer client.Close()

	// Check if token already exists to avoid duplication
	iter := client.Collection("brody_tokens").Where("token", "==", token).Documents(ctx)
	docs, err := iter.GetAll()
	if err == nil && len(docs) > 0 {
		return fmt.Errorf("el token ya existe en la base de datos de Firebase")
	}

	// Use a new document ID
	docRef := client.Collection("brody_tokens").NewDoc()
	_, err = docRef.Set(ctx, map[string]interface{}{
		"token":      token,
		"created_at": time.Now(),
	})
	return err
}

// LoadTokensFromFirebase connects to Firestore and reads all saved bot tokens.
func (w *BotWorkers) LoadTokensFromFirebase() ([]string, error) {
	if config.ValueOf.FirebaseJSON == "" {
		return nil, nil
	}

	w.log.Sugar().Info("Loading tokens from Firebase Firestore...")
	ctx := context.Background()
	opt := option.WithCredentialsJSON([]byte(config.ValueOf.FirebaseJSON))
	app, err := firebase.NewApp(ctx, nil, opt)
	if err != nil {
		w.log.Sugar().Warnf("error initializing firebase to load tokens: %v", err)
		return nil, err
	}

	client, err := app.Firestore(ctx)
	if err != nil {
		w.log.Sugar().Warnf("error connecting to firestore to load tokens: %v", err)
		return nil, err
	}
	defer client.Close()

	iter := client.Collection("brody_tokens").Documents(ctx)
	docs, err := iter.GetAll()
	if err != nil {
		w.log.Sugar().Warnf("error fetching tokens from firestore: %v", err)
		return nil, err
	}

	var tokens []string
	seen := make(map[string]bool)
	for _, doc := range docs {
		if t, ok := doc.Data()["token"].(string); ok && t != "" {
			if !seen[t] {
				tokens = append(tokens, t)
				seen[t] = true
			} else {
				// Remove duplicated keys from firestore automatically
				doc.Ref.Delete(ctx)
			}
		}
	}
	w.log.Sugar().Infof("Successfully loaded %d dynamic tokens from Firebase", len(tokens))
	return tokens, nil
}
