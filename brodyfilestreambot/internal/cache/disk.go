package cache

import (
	"os"
	"path/filepath"
	"time"

	"go.uber.org/zap"
)

// StartDiskCacheEviction periodically deletes files in the cache directory that are older than maxAge.
func StartDiskCacheEviction(dir string, maxAge time.Duration, log *zap.Logger) {
	log = log.Named("DiskCache")
	ticker := time.NewTicker(1 * time.Hour)
	defer ticker.Stop()

	for range ticker.C {
		log.Info("Running disk cache eviction cleanup")
		entries, err := os.ReadDir(dir)
		if err != nil {
			log.Error("Failed to read cache directory", zap.Error(err))
			continue
		}

		now := time.Now()
		var deleted int
		for _, entry := range entries {
			if entry.IsDir() {
				continue
			}
			info, err := entry.Info()
			if err != nil {
				continue
			}

			if now.Sub(info.ModTime()) > maxAge {
				err = os.Remove(filepath.Join(dir, entry.Name()))
				if err == nil {
					deleted++
				}
			}
		}
		if deleted > 0 {
			log.Sugar().Infof("Evicted %d files from disk cache", deleted)
		}
	}
}
