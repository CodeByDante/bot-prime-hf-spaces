package main

import (
	"fmt"
	"net/http"
	"io"
	"time"
)

func main() {
	client := http.Client{Timeout: 30 * time.Second}
	resp, err := client.Get("https://codebydante-brodyfilestreambot.hf.space/")
	if err != nil {
		fmt.Println("Error fetching URL:", err)
		return
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	fmt.Println("Status:", resp.Status)
	fmt.Println("Body:", string(body))
}
