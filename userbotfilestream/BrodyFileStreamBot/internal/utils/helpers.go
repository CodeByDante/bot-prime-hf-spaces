package utils

import (
	"EverythingSuckz/fsb/config"
	"EverythingSuckz/fsb/internal/cache"
	"EverythingSuckz/fsb/internal/types"
	"context"
	"errors"
	"fmt"
	"math/rand"
	"strings"

	"github.com/celestix/gotgproto"
	"github.com/celestix/gotgproto/ext"
	"github.com/celestix/gotgproto/storage"
	"github.com/gotd/td/telegram/uploader"
	"github.com/gotd/td/tg"
	"go.uber.org/zap"
)

// https://stackoverflow.com/a/70802740/15807350
func Contains[T comparable](s []T, e T) bool {
	for _, v := range s {
		if v == e {
			return true
		}
	}
	return false
}

// IsClientDisconnectError checks if the error is due to client disconnecting
// e.g. user seeking in video, stopping playback, or network issues on client side
func IsClientDisconnectError(err error) bool {
	if err == nil {
		return false
	}
	errStr := err.Error()
	return strings.Contains(errStr, "connection was aborted") ||
		strings.Contains(errStr, "connection reset by peer") ||
		strings.Contains(errStr, "broken pipe") ||
		strings.Contains(errStr, "forcibly closed")
}

// telegram helper functions
// TODO: move these to a separate package if they grow too large

func GetTGMessage(ctx context.Context, client *gotgproto.Client, messageID int) (*tg.Message, error) {
	inputMessageID := tg.InputMessageClass(&tg.InputMessageID{ID: messageID})
	channel, err := GetLogChannelPeer(ctx, client.API(), client.PeerStorage)
	if err != nil {
		return nil, err
	}
	messageRequest := tg.ChannelsGetMessagesRequest{Channel: channel, ID: []tg.InputMessageClass{inputMessageID}}
	res, err := client.API().ChannelsGetMessages(ctx, &messageRequest)
	if err != nil {
		return nil, err
	}
	messages := res.(*tg.MessagesChannelMessages)
	message := messages.Messages[0]
	if _, ok := message.(*tg.Message); ok {
		return message.(*tg.Message), nil
	} else {
		return nil, fmt.Errorf("this file was deleted")
	}
}

func FileFromMedia(media tg.MessageMediaClass) (*types.File, error) {
	switch media := media.(type) {
	case *tg.MessageMediaDocument:
		document, ok := media.Document.AsNotEmpty()
		if !ok {
			return nil, fmt.Errorf("unexpected type %T", media)
		}
		var fileName string
		for _, attribute := range document.Attributes {
			if name, ok := attribute.(*tg.DocumentAttributeFilename); ok {
				fileName = name.FileName
				break
			}
		}
		return &types.File{
			Location: document.AsInputDocumentFileLocation(),
			FileSize: document.Size,
			FileName: fileName,
			MimeType: document.MimeType,
			ID:       document.ID,
		}, nil
	case *tg.MessageMediaPhoto:
		photo, ok := media.Photo.AsNotEmpty()
		if !ok {
			return nil, fmt.Errorf("unexpected type %T", media)
		}
		sizes := photo.Sizes
		if len(sizes) == 0 {
			return nil, errors.New("photo has no sizes")
		}
		photoSize := sizes[len(sizes)-1]
		size, ok := photoSize.AsNotEmpty()
		if !ok {
			return nil, errors.New("photo size is empty")
		}
		location := new(tg.InputPhotoFileLocation)
		location.ID = photo.GetID()
		location.AccessHash = photo.GetAccessHash()
		location.FileReference = photo.GetFileReference()
		location.ThumbSize = size.GetType()
		return &types.File{
			Location: location,
			FileSize: 0, // caller should judge if this is a photo or not
			FileName: fmt.Sprintf("photo_%d.jpg", photo.GetID()),
			MimeType: "image/jpeg",
			ID:       photo.GetID(),
		}, nil
	}
	return nil, fmt.Errorf("unexpected type %T", media)
}

func FileFromMessage(ctx context.Context, client *gotgproto.Client, messageID int) (*types.File, error) {
	key := fmt.Sprintf("file:%d:%d", messageID, client.Self.ID)
	log := Logger.Named("GetMessageMedia")
	var cachedMedia types.File
	err := cache.GetCache().Get(key, &cachedMedia)
	if err == nil {
		log.Debug("Using cached media message properties", zap.Int("messageID", messageID), zap.Int64("clientID", client.Self.ID))
		return &cachedMedia, nil
	}
	log.Debug("Fetching file properties from message ID", zap.Int("messageID", messageID), zap.Int64("clientID", client.Self.ID))
	message, err := GetTGMessage(ctx, client, messageID)
	if err != nil {
		return nil, err
	}
	file, err := FileFromMedia(message.Media)
	if err != nil {
		return nil, err
	}
	err = cache.GetCache().Set(
		key,
		file,
		3600,
	)
	if err != nil {
		return nil, err
	}
	return file, nil
}

func ThumbFromMessage(ctx context.Context, client *gotgproto.Client, messageID int) (*types.File, error) {
	key := fmt.Sprintf("thumb:%d:%d", messageID, client.Self.ID)
	log := Logger.Named("GetMessageThumb")
	var cachedMedia types.File
	err := cache.GetCache().Get(key, &cachedMedia)
	if err == nil {
		log.Debug("Using cached thumb properties", zap.Int("messageID", messageID), zap.Int64("clientID", client.Self.ID))
		return &cachedMedia, nil
	}
	log.Debug("Fetching thumb properties from message ID", zap.Int("messageID", messageID), zap.Int64("clientID", client.Self.ID))
	message, err := GetTGMessage(ctx, client, messageID)
	if err != nil {
		return nil, err
	}
	media := message.Media
	switch media := media.(type) {
	case *tg.MessageMediaDocument:
		doc, ok := media.Document.AsNotEmpty()
		if !ok {
			return nil, errors.New("document is empty")
		}
		if len(doc.Thumbs) == 0 {
			return nil, errors.New("no thumbs found in document")
		}
		var largestThumb tg.PhotoSizeClass
		for _, thumb := range doc.Thumbs {
			switch thumb.(type) {
			case *tg.PhotoSize:
				largestThumb = thumb
			case *tg.PhotoSizeProgressive:
				largestThumb = thumb
			}
		}
		if largestThumb == nil {
			largestThumb = doc.Thumbs[0]
		}
		size, ok := largestThumb.AsNotEmpty()
		if !ok {
			return nil, errors.New("thumb size is empty")
		}
		location := &tg.InputDocumentFileLocation{
			ID:            doc.ID,
			AccessHash:    doc.AccessHash,
			FileReference: doc.FileReference,
			ThumbSize:     size.GetType(),
		}
		file := &types.File{
			Location: location,
			FileSize: 0,
			FileName: fmt.Sprintf("thumb_%d.jpg", doc.ID),
			MimeType: "image/jpeg",
			ID:       doc.ID,
		}
		err = cache.GetCache().Set(key, file, 3600)
		if err != nil {
			return nil, err
		}
		return file, nil
	}
	return nil, errors.New("media type not supported for thumbs")
}

func SceneFromMessage(ctx context.Context, client *gotgproto.Client, videoMessageID int, sceneIndex int) (*types.File, error) {
	key := fmt.Sprintf("scene:%d:%d:%d", videoMessageID, sceneIndex, client.Self.ID)
	log := Logger.Named("GetMessageScene")
	var cachedMedia types.File
	err := cache.GetCache().Get(key, &cachedMedia)
	if err == nil {
		log.Debug("Using cached scene properties", zap.Int("videoMessageID", videoMessageID), zap.Int("sceneIndex", sceneIndex), zap.Int64("clientID", client.Self.ID))
		return &cachedMedia, nil
	}
	log.Debug("Fetching scene properties from message ID", zap.Int("videoMessageID", videoMessageID), zap.Int("sceneIndex", sceneIndex), zap.Int64("clientID", client.Self.ID))
	
	// Fetch messages preceding the video to find the album of screenshots
	channel, err := GetLogChannelPeer(ctx, client.API(), client.PeerStorage)
	if err != nil {
		return nil, err
	}
	
	res, err := client.API().MessagesGetHistory(ctx, &tg.MessagesGetHistoryRequest{
		Peer: &tg.InputPeerChannel{
			ChannelID:  channel.ChannelID,
			AccessHash: channel.AccessHash,
		},
		OffsetID: videoMessageID,
		Limit:    30, // scan up to 30 messages backwards
	})
	if err != nil {
		return nil, err
	}
	
	var msgClasses []tg.MessageClass
	switch r := res.(type) {
	case *tg.MessagesMessages:
		msgClasses = r.Messages
	case *tg.MessagesMessagesSlice:
		msgClasses = r.Messages
	case *tg.MessagesChannelMessages:
		msgClasses = r.Messages
	default:
		return nil, fmt.Errorf("unexpected response type: %T", res)
	}
	
	// Collect photo messages
	var photoMessages []*tg.Message
	for _, msgClass := range msgClasses {
		msg, ok := msgClass.(*tg.Message)
		if !ok {
			continue
		}
		if msg.Media == nil {
			continue
		}
		if _, isPhoto := msg.Media.(*tg.MessageMediaPhoto); isPhoto {
			photoMessages = append(photoMessages, msg)
		}
	}
	
	if len(photoMessages) == 0 {
		return nil, errors.New("no scene photos found preceding the video message")
	}
	
	// Sort photo messages by ID in ascending order (first uploaded photo first)
	sortPhotoMessages(photoMessages)
	
	idx := sceneIndex - 1
	if idx < 0 || idx >= len(photoMessages) {
		return nil, fmt.Errorf("scene index %d out of bounds (found %d scenes)", sceneIndex, len(photoMessages))
	}
	
	selectedMsg := photoMessages[idx]
	file, err := FileFromMedia(selectedMsg.Media)
	if err != nil {
		return nil, err
	}
	
	err = cache.GetCache().Set(key, file, 3600)
	if err != nil {
		return nil, err
	}
	return file, nil
}

func sortPhotoMessages(msgs []*tg.Message) {
	for i := 0; i < len(msgs); i++ {
		for j := i + 1; j < len(msgs); j++ {
			if msgs[i].ID > msgs[j].ID {
				msgs[i], msgs[j] = msgs[j], msgs[i]
			}
		}
	}
}



func GetLogChannelPeer(ctx context.Context, api *tg.Client, peerStorage *storage.PeerStorage) (*tg.InputChannel, error) {
	cachedInputPeer := peerStorage.GetInputPeerById(config.ValueOf.LogChannelID)

	switch peer := cachedInputPeer.(type) {
	case *tg.InputPeerEmpty:
		break
	case *tg.InputPeerChannel:
		return &tg.InputChannel{
			ChannelID:  peer.ChannelID,
			AccessHash: peer.AccessHash,
		}, nil
	default:
		return nil, errors.New("unexpected type of input peer")
	}
	inputChannel := &tg.InputChannel{
		ChannelID: config.ValueOf.LogChannelID,
	}
	channels, err := api.ChannelsGetChannels(ctx, []tg.InputChannelClass{inputChannel})
	if err != nil {
		return nil, err
	}
	if len(channels.GetChats()) == 0 {
		return nil, errors.New("no channels found")
	}
	channel, ok := channels.GetChats()[0].(*tg.Channel)
	if !ok {
		return nil, errors.New("type assertion to *tg.Channel failed")
	}
	// Bruh, I literally have to call library internal functions at this point
	peerStorage.AddPeer(channel.GetID(), channel.AccessHash, storage.TypeChannel, "")
	return channel.AsInput(), nil
}

func ForwardMessages(ctx *ext.Context, fromChatId, toChatId int64, messageID int) (*tg.Updates, error) {
	fromPeer := ctx.PeerStorage.GetInputPeerById(fromChatId)
	if fromPeer.Zero() {
		return nil, fmt.Errorf("fromChatId: %d is not a valid peer", fromChatId)
	}
	toPeer, err := GetLogChannelPeer(ctx, ctx.Raw, ctx.PeerStorage)
	if err != nil {
		return nil, err
	}
	update, err := ctx.Raw.MessagesForwardMessages(ctx, &tg.MessagesForwardMessagesRequest{
		RandomID: []int64{rand.Int63()},
		FromPeer: fromPeer,
		ID:       []int{messageID},
		ToPeer:   &tg.InputPeerChannel{ChannelID: toPeer.ChannelID, AccessHash: toPeer.AccessHash},
	})
	if err != nil {
		return nil, err
	}
	return update.(*tg.Updates), nil
}

// UploadToTG uploads a file to Telegram using MTProto directly and returns error if any.
func UploadToTG(ctx *ext.Context, chatID int64, fileData []byte, fileName string) error {
	u := uploader.NewUploader(ctx.Raw)
	// uploader.FromBytes handles the chunking and uploading logic via MTProto
	file, err := u.FromBytes(ctx.Context, fileName, fileData)
	if err != nil {
		return fmt.Errorf("failed to upload via MTProto: %v", err)
	}

	media := &tg.InputMediaUploadedDocument{
		File:     file,
		MimeType: "text/plain",
		Attributes: []tg.DocumentAttributeClass{
			&tg.DocumentAttributeFilename{FileName: fileName},
		},
	}

	_, err = ctx.SendMedia(chatID, &tg.MessagesSendMediaRequest{
		Media: media,
	})
	if err != nil {
		return fmt.Errorf("failed to send media via MTProto: %v", err)
	}

	return nil
}
