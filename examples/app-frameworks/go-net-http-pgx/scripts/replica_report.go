// Administrative aggregate. Counts can lag. HTTP sessions keep the primary.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/jackc/pgx/v5"
	"os"
	"time"
)

func main() {
	for _, item := range [][2]string{{"read", "DATABASE_READ_URL"}, {"write", "DATABASE_URL"}} {
		ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		c, err := pgx.Connect(ctx, os.Getenv(item[1]))
		if err != nil {
			panic("database connection failed")
		}
		var address string
		var replica bool
		var count int64
		err = c.QueryRow(ctx, "select inet_server_addr()::text, pg_is_in_recovery(), (select count(*) from records)").Scan(&address, &replica, &count)
		if err != nil {
			panic("replica aggregate failed")
		}
		b, _ := json.Marshal(map[string]any{"connection_purpose": item[0], "database_server_address": address, "is_replica": replica, "record_count": count})
		fmt.Println(string(b))
		c.Close(ctx)
		cancel()
	}
}
