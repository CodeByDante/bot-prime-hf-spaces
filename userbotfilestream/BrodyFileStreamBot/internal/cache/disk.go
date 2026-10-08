package cache

import (
	"os"
	"path/filepath"
	"sort"
	"time"

	"go.uber.org/zap"
)

type cacheFile struct {
	path    string
	size    int64
	modTime time.Time
}

// StartDiskCacheEviction periodically deletes files in the cache directory that are older than maxAge,
// and enforces a maximum total cache size limit of 15 GB (evicting oldest files first).
func StartDiskCacheEviction(dir string, maxAge time.Duration, log *zap.Logger) {
	log = log.Named("DiskCache")
	// Ejecutar limpieza cada 5 minutos para reaccionar rápido ante descargas grandes
	ticker := time.NewTicker(5 * time.Minute)
	defer ticker.Stop()

	const maxCacheSize int64 = 15 * 1024 * 1024 * 1024 // 15 GB

	for range ticker.C {
		log.Info("Running disk cache size and age eviction check")
		entries, err := os.ReadDir(dir)
		if err != nil {
			log.Error("Failed to read cache directory", zap.Error(err))
			continue
		}

		var files []cacheFile
		var totalSize int64
		now := time.Now()
		var deletedByAge int

		for _, entry := range entries {
			if entry.IsDir() {
				continue
			}
			info, err := entry.Info()
			if err != nil {
				continue
			}

			path := filepath.Join(dir, entry.Name())

			// 1. Eliminar de inmediato si superó la edad máxima
			if now.Sub(info.ModTime()) > maxAge {
				if err := os.Remove(path); err == nil {
					deletedByAge++
					continue
				}
			}

			files = append(files, cacheFile{
				path:    path,
				size:    info.Size(),
				modTime: info.ModTime(),
			})
			totalSize += info.Size()
		}

		if deletedByAge > 0 {
			log.Sugar().Infof("Evicted %d files due to max age (%v)", deletedByAge, maxAge)
		}

		// 2. Si el tamaño total excede los 15 GB, eliminar los más antiguos primero
		if totalSize > maxCacheSize {
			log.Sugar().Infof("Cache size (%d bytes) exceeds limit (%d bytes). Evicting oldest files...", totalSize, maxCacheSize)

			// Ordenar por ModTime ascendente (los más antiguos primero)
			sort.Slice(files, func(i, j int) bool {
				return files[i].modTime.Before(files[j].modTime)
			})

			var deletedBySize int
			for _, file := range files {
				if totalSize <= maxCacheSize {
					break
				}
				if err := os.Remove(file.path); err == nil {
					totalSize -= file.size
					deletedBySize++
				}
			}

			if deletedBySize > 0 {
				log.Sugar().Infof("Evicted %d files to free space. New total size: %d bytes", deletedBySize, totalSize)
			}
		}
	}
}
