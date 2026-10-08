package main

import (
	"context"
	"github.com/celestix/gotgproto/ext"
	"github.com/gotd/td/telegram/message"
	"github.com/gotd/td/telegram/uploader"
	"github.com/gotd/td/tg"
)

func testUpload(ctx *ext.Context, replyTo int, fileBytes []byte, fileName string) error {
	u := uploader.NewUploader(ctx.Raw)
	file, err := u.FromBytes(ctx, fileName, fileBytes)
	if err != nil {
		return err
	}
	
	sender := message.NewSender(ctx.Raw)
	media := &tg.InputMediaUploadedDocument{
		File:     file,
		MimeType: "text/plain",
		Attributes: []tg.DocumentAttributeClass{
			&tg.DocumentAttributeFilename{FileName: fileName},
		},
	}
	_, err = sender.To(ctx.EffectiveChat().AsInputPeer()).Reply(replyTo).Media(ctx, message.Media(media))
	return err
}
