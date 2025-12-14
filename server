package main

import (
	"fmt"
	"net/http"
	"os"
)

func main() {
	service := os.Getenv("SERVICE_NAME")
	if service == "" {
		service = "unknown"
	}

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintf(w, "Hello from %s service\n", service)
	})

	http.ListenAndServe(":8080", nil)
}
