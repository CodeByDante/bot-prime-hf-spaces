import express from 'express';
import cors from 'cors';
import fs from 'fs';
import path from 'path';
import axios from 'axios';
import archiver from 'archiver';
import PDFDocument from 'pdfkit';
import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { initializeApp } from 'firebase/app';
import sharp from 'sharp';
import { getFirestore, collection, query, where, getDocs, orderBy } from 'firebase/firestore';

sharp.cache(false); // Disable cache to prevent memory growth during batch processing

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 7860;

app.use(cors());
app.use(express.json({ limit: '50mb' }));

// Serve static files from the dist directory
app.use(express.static(path.join(__dirname, 'dist')));

// --- Firebase Config ---
const firebaseConfig = {
  apiKey: "AIzaSyAH3jvbe0_QLzIuuv5kTMK8246HNvohvfE",
  authDomain: "twistedbrody-9d163.firebaseapp.com",
  projectId: "twistedbrody-9d163",
  storageBucket: "twistedbrody-9d163.firebasestorage.app",
  messagingSenderId: "733213514129",
  appId: "1:733213514129:web:e9694684f5c3994ed06230",
  measurementId: "G-N8TQ7MY42W"
};

const firebaseApp = initializeApp(firebaseConfig);
const db = getFirestore(firebaseApp);

// --- 1. Almacén global de progreso ---
const progresoDescargas = {};

// --- Helpers ---
const downloadsDir = path.join(__dirname, 'downloads');
if (!fs.existsSync(downloadsDir)) {
  fs.mkdirSync(downloadsDir);
}

// --- Cleanup on Startup ---
function cleanDownloadsFolder() {
  console.log(`[INIT] Limpiando carpeta de descargas: ${downloadsDir}`);
  try {
    const files = fs.readdirSync(downloadsDir);
    for (const file of files) {
      if (file === '.gitkeep') continue; // Optional preservation
      fs.unlinkSync(path.join(downloadsDir, file));
    }
    if (files.length > 0) {
      console.log(`[INIT] 🧹 Se eliminaron ${files.length} archivos temporales antiguos.`);
    } else {
      console.log(`[INIT] ✨ Carpeta de descargas limpia.`);
    }
  } catch (err) {
    console.error(`[INIT] ❌ Error limpiando descargas: ${err.message}`);
  }
}
cleanDownloadsFolder();

function sanitizeFilename(name) {
  return name.replace(/[^a-z0-9]/gi, '_');
}

async function downloadImage(url) {
  try {
    const response = await axios({
      url,
      method: 'GET',
      responseType: 'arraybuffer',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://google.com'
      }
    });

    if (response.status !== 200) throw new Error(`Status ${response.status}`);
    return response.data;
  } catch (error) {
    console.error(`[DEBUG] Download failed: ${error.message} (${url})`);
    throw error;
  }
}

// --- 2. Ruta para que el Frontend escuche el progreso (SSE) ---
app.get('/api/download/progress/:jobId', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  const { jobId } = req.params;

  // Enviamos un latido cada 500ms
  const interval = setInterval(() => {
    const p = progresoDescargas[jobId] || 0;
    res.write(`data: ${JSON.stringify({ progress: p })}\n\n`);
    if (p >= 100 || p === 'error') {
      clearInterval(interval);
      if (p >= 100) delete progresoDescargas[jobId]; // Limpiar memoria
    }
  }, 500);

  req.on('close', () => clearInterval(interval));
});

// --- Firebase Fetch Helper ---
async function getAllChapters(mangaId) {
  console.log(`[FIREBASE] Buscando capítulos para manga_id: ${mangaId} (Estrategia Bypass de Índice)`);

  // HACKER FIX: Consultamos solo por 'where' para evitar el error de "Index Required".
  // Ordenamos los datos nosotros mismos en la memoria RAM del servidor.
  const q = query(
    collection(db, "chapters"),
    where("manga_id", "==", mangaId)
  );

  const querySnapshot = await getDocs(q);

  if (querySnapshot.empty) {
    // Fallback: Try with 'mangaId' just in case the field name varies
    console.log("[FIREBASE] Intento secundario con campo 'mangaId'...");
    const q2 = query(collection(db, "chapters"), where("mangaId", "==", mangaId));
    const snapshot2 = await getDocs(q2);

    if (snapshot2.empty) {
      throw new Error('No se encontraron capítulos para este mangaId (ni por manga_id ni mangaId).');
    }
    return processSnapshot(snapshot2);
  }

  return processSnapshot(querySnapshot);
}

function processSnapshot(snapshot) {
  console.log(`[FIREBASE] Encontrados ${snapshot.size} capítulos. Procesando y ordenando en memoria...`);

  const chapters = snapshot.docs.map(doc => {
    const data = doc.data();
    return {
      id: doc.id,
      number: Number(data.number) || 0, // Ensure number for sorting
      original_pages: data.original_pages || [],
      pages: data.pages || []
    };
  });

  // Ordenamiento manual (Bypass del índice compuesto)
  return chapters.sort((a, b) => a.number - b.number);
}



// --- Image Proxy & Optimization ---
app.get('/api/image-proxy', async (req, res) => {
  const { url, width, height, quality, format } = req.query;

  if (!url) {
    return res.status(400).send('URL is required');
  }

  try {
    // 1. Fetch the original image
    const response = await axios({
      url: url,
      method: 'GET',
      responseType: 'arraybuffer',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://google.com'
      }
    });

    let imageBuffer = response.data;

    // 2. Set aggressive cache headers (1 day)
    res.setHeader('Cache-Control', 'public, max-age=86400, mutable');

    // 3. Resize if requested (Sharp)
    if (width || height || (format && format !== 'original')) {
      const pipeline = sharp(imageBuffer);

      if (width || height) {
        pipeline.resize(
          width ? parseInt(width) : null,
          height ? parseInt(height) : null,
          {
            fit: 'inside',
            withoutEnlargement: true
          }
        );
      }

      // Format conversion (default to webp for performance check)
      const outFormat = format || 'webp';
      const outQuality = quality ? parseInt(quality) : 85;

      if (outFormat === 'webp') {
        pipeline.webp({ quality: outQuality });
        res.setHeader('Content-Type', 'image/webp');
      } else if (outFormat === 'jpeg' || outFormat === 'jpg') {
        pipeline.jpeg({ quality: outQuality });
        res.setHeader('Content-Type', 'image/jpeg');
      } else if (outFormat === 'png') {
        pipeline.png({ quality: outQuality });
        res.setHeader('Content-Type', 'image/png');
      }

      imageBuffer = await pipeline.toBuffer();
    } else {
      // Pass-through original content type if not converting
      res.setHeader('Content-Type', response.headers['content-type']);
    }

    res.send(imageBuffer);

  } catch (error) {
    console.error(`[PROXY ERROR] ${url}: ${error.message}`);
    // Fallback: Redirect to original URL if proxy fails
    res.redirect(url);
  }
});

// --- Routes ---

app.get('/api/progress/:jobId', (req, res) => {
  const { jobId } = req.params;
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive'
  });
  jobs[jobId] = { res, progress: 0 };
  console.log(`[SERVIDOR] Cliente conectado (Job: ${jobId})`);
  req.on('close', () => {
    if (jobs[jobId]) delete jobs[jobId];
  });
});

app.post('/api/download/zip', async (req, res) => {
  console.log("[DEBUG] Body recibido ZIP:", JSON.stringify(req.body).substring(0, 500));
  const { mangaTitle, format } = req.body; // format: 'png', 'jpg', 'webp', 'original'
  const mangaId = req.body.mangaId || req.body.manga_id;

  if (!mangaId || mangaId === 'undefined') {
    console.error("[SERVIDOR] ❌ Error: MangaId indefinido");
    return res.status(400).json({ error: "ID requerido" });
  }

  console.log(`🚀 [SERVIDOR] Iniciando Stream ZIP para: ${mangaTitle} (${mangaId}) - Formato: ${format}`);

  try {
    const chapters = await getAllChapters(mangaId);

    // Set headers for download
    res.setHeader('Content-Type', 'application/zip');
    res.setHeader('Content-Disposition', `attachment; filename="${sanitizeFilename(mangaTitle)}.zip"`);

    // OPTIMIZATION: Use level 1 (Fastest) instead of 9 (Best) to avoid CPU bottleneck
    const archive = archiver('zip', { zlib: { level: 1 } });

    archive.on('error', (err) => {
      console.error('[SERVIDOR] ❌ Error ZIP:', err);
      if (!res.headersSent) res.status(500).send({ error: err.message });
    });

    archive.pipe(res);

    // Collect all pages
    let totalPagesToDownload = 0;
    const chaptersToProcess = [];
    for (const chap of chapters) {
      let pages = [];
      if (format === 'original') {
        pages = (chap.original_pages && chap.original_pages.length > 0) ? chap.original_pages : chap.pages;
      } else {
        pages = (chap.pages && chap.pages.length > 0) ? chap.pages : chap.original_pages;
      }

      if (pages && pages.length > 0) {
        chaptersToProcess.push({ number: chap.number, pages });
        totalPagesToDownload += pages.length;
      }
    }

    // Process chapters in parallel (limit parallelism to avoid memory exploded with sharp)
    let processedTotal = 0;

    // Helper for sequential processing within chapters to manage concurrency better
    for (const chap of chaptersToProcess) {
      console.log(`[STREAM] Procesando Cap ${chap.number}`);

      // OPTIMIZATION: Increased batch size from 20 to 50 for faster downloads
      const chunkSize = 50;
      for (let i = 0; i < chap.pages.length; i += chunkSize) {
        const batch = chap.pages.slice(i, i + chunkSize);

        await Promise.all(batch.map(async (pageUrl, batchIndex) => {
          const pageIndex = i + batchIndex;
          try {
            let buffer = await downloadImage(pageUrl);

            // --- CONVERSION LOGIC ---
            let ext = 'jpg';
            let finalBuffer = buffer;

            // Determine current extension from URL roughly
            if (pageUrl.toLowerCase().includes('.png')) ext = 'png';
            else if (pageUrl.toLowerCase().includes('.webp')) ext = 'webp';

            // IF format is NOT original, we convert
            if (format && format !== 'original') {
              try {
                // Format mappings for sharp
                let sharpFormat = format;
                if (format === 'jpg') sharpFormat = 'jpeg';

                // Perform conversion
                finalBuffer = await sharp(buffer)
                  .toFormat(sharpFormat, { quality: 90 })
                  .toBuffer();

                ext = format; // Update extension to requested format
              } catch (sharpErr) {
                console.warn(`[WARN] Falló conversión a ${format}, usanda original.`, sharpErr.message);
              }
            }

            const cleanChapterNum = String(chap.number).padStart(2, '0');
            const archivePath = `Capitulo_${cleanChapterNum}/pagina_${String(pageIndex + 1).padStart(3, '0')}.${ext}`;

            archive.append(finalBuffer, { name: archivePath });

            // --- UPDATE PROGRESS ---
            processedTotal++;
            const porcentaje = Math.round((processedTotal / totalPagesToDownload) * 100);
            progresoDescargas[mangaId] = porcentaje;

          } catch (e) {
            console.error(`[!] Error Cap ${chap.number} pág ${pageIndex}: ${e.message}`);
          }
        }));
      }
    }

    // Force 100% on complete
    progresoDescargas[mangaId] = 100;
    await archive.finalize();

  } catch (error) {
    console.error(`[SERVIDOR] ❌ Error Global: ${error.message}`);
    fs.writeFileSync(path.join(__dirname, 'server_error.log'), `[${new Date().toISOString()}] Error ZIP: ${error.stack}\n`, { flag: 'a' });
    progresoDescargas[mangaId] = 'error';
    if (!res.headersSent) res.status(500).json({ error: error.message });
  }
});

// const { spawn } = require('child_process'); // Removed: using import at top

app.post('/api/download/pdf', async (req, res) => {
  console.log("[DEBUG] Body recibido PDF:", JSON.stringify(req.body).substring(0, 500));
  const { mangaTitle, format, jobId } = req.body;
  const mangaId = req.body.mangaId || req.body.manga_id;

  if (!mangaId || mangaId === 'undefined') {
    console.error("[SERVIDOR] ❌ Error: Se recibió un mangaId indefinido para PDF");
    return res.status(400).json({ error: "El ID del manga es obligatorio" });
  }

  console.log(`\n[SERVIDOR] Solicitud PDF (Python Bridge) para: ${mangaTitle} (ID: ${mangaId})`);

  // Notify client PDF is starting (optional, but good if we kept SSE)
  // sendProgress(jobId, 10, 'starting'); // We might not be able to track detailed progress easily w/o advanced python ipc

  try {
    // 1. Fetch URLs using existing helper
    const chapters = await getAllChapters(mangaId);
    let allUrls = [];

    // Sort chapters just to be safe, though getAllChapters does it
    chapters.sort((a, b) => a.number - b.number);

    for (const chap of chapters) {
      let pages = [];
      if (format === 'original') pages = (chap.original_pages && chap.original_pages.length > 0) ? chap.original_pages : chap.pages;
      else pages = (chap.pages && chap.pages.length > 0) ? chap.pages : chap.original_pages;

      if (pages && pages.length > 0) {
        allUrls = allUrls.concat(pages);
      }
    }

    if (allUrls.length === 0) {
      throw new Error("No extracted pages found to convert.");
    }

    console.log(`[PYTHON] Delegando ${allUrls.length} páginas al script converter.py...`);

    const safeTitle = sanitizeFilename(mangaTitle);
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const pdfName = `${safeTitle}_HackerMode_${timestamp}.pdf`;
    const pdfPath = path.join(downloadsDir, pdfName); // Use full path

    // 2. Call Python Script in Unbuffered mode
    // HACKER FIX: En Docker/Linux a menudo es 'python3', en Windows 'python'
    const pythonCmd = process.env.PYTHON_CMD || (process.platform === 'win32' ? 'python' : 'python3');
    console.log(`[SERVIDOR] Usando comando Python: ${pythonCmd}`);

    const scriptPath = path.join(__dirname, 'converter.py');
    const pythonProcess = spawn(pythonCmd, ['-u', scriptPath]);

    // Send data to Python via STDIN
    pythonProcess.stdin.write(JSON.stringify({
      urls: allUrls,
      output: pdfPath
    }));
    pythonProcess.stdin.end();

    // 🚩 Logic to sync progress with SSE
    let imagenesTerminadas = 0;
    const totalPaginasTarget = allUrls.length;

    pythonProcess.stdout.on('data', (data) => {
      const lineas = data.toString().split('\n');

      lineas.forEach(line => {
        const mensaje = line.trim();
        if (mensaje.includes("PROGRESS:IMAGE_DONE")) {
          imagenesTerminadas++;
          const porcentaje = Math.round((imagenesTerminadas / totalPaginasTarget) * 100);

          // Update global store for SSE
          progresoDescargas[mangaId] = porcentaje;
          process.stdout.write(`\r[PYTHON] ⚡ Descarga Paralela: ${imagenesTerminadas}/${totalPaginasTarget} (${porcentaje}%)`);

        } else if (mensaje === "STATUS:SUCCESS") {
          console.log("\n[PYTHON] ✅ PDF Creado con éxito.");
          progresoDescargas[mangaId] = 100; // Ensure 100%
        } else if (mensaje.startsWith("DEBUG:")) {
          // console.log(`\n[PYTHON] ${mensaje}`);
        }
      });
    });

    pythonProcess.stderr.on('data', (data) => {
      console.error(`[PYTHON STDERR]: ${data}`);
    });

    pythonProcess.on('close', (code) => {
      if (code === 0) {
        console.log(`[SERVIDOR] ✅ PDF creado por Python: ${pdfPath}`);
        // 3. Send file to client
        res.download(pdfPath, (err) => {
          if (err) {
            console.error("Error sending file:", err);
            if (!res.headersSent) res.status(500).send("Error downloading file");
          }
          // Cleanup temp file after sending
          if (fs.existsSync(pdfPath)) {
            // small timeout to ensure stream closed
            setTimeout(() => fs.unlinkSync(pdfPath), 1000);
          }
        });
      } else {
        console.error(`[SERVIDOR] ❌ Python exited with code ${code}`);
        if (!res.headersSent) res.status(500).send("Error en la conversión a PDF (Python Code " + code + ")");
      }
    });

  } catch (error) {
    console.error(`[SERVIDOR] ❌ Error Global PDF: ${error.message}`);
    if (!res.headersSent) res.status(500).send({ error: error.message });
  }
});

// --- Image Processing Endpoint ---
app.post('/api/process-image', async (req, res) => {
  const startTime = Date.now();
  const { name, index, total } = req.body; // Extraemos metadatos

  try {
    const { image } = req.body;
    if (!image) {
      return res.status(400).json({ error: 'Image data is required' });
    }

    // Log inicial del lote (solo si es la primera imagen y viene la info)
    if (index === 1 && total) {
      console.log(`\n[PROCESAMIENTO] � Iniciando lote: procesando ${total} imagenes`);
    }

    // Extract base64
    const base64Data = image.replace(/^data:image\/\w+;base64,/, "");
    const buffer = Buffer.from(base64Data, 'base64');

    // Procesamiento en Paralelo
    const [webpBuffer, thumbnailBuffer] = await Promise.all([
      sharp(buffer)
        .resize(1200, null, { fit: 'inside', withoutEnlargement: true })
        .webp({ quality: 90 })
        .toBuffer(),
      sharp(buffer)
        .resize(400, null, { fit: 'inside', withoutEnlargement: true })
        .jpeg({ quality: 80, leaflet: true })
        .toBuffer()
    ]);

    // Log de finalización estilo solicitado
    if (index && total) {
      console.log(`finalizado ${index} paginas`); // "finalizado 1 paginas", "finalizado 2 paginas"...
      if (index === total) {
        console.log(`\n[PROCESAMIENTO] ✅ Lote de ${total} imágenes completado.`);
      }
    } else {
      // Fallback para subidas individuales (portada, etc)
      const duration = Date.now() - startTime;
      console.log(`[PROCESAMIENTO] 🟢 Completado: ${name} (${duration}ms)`);
    }

    res.json({
      success: true,
      data: {
        webp: `data:image/webp;base64,${webpBuffer.toString('base64')}`,
        thumbnail: `data:image/jpeg;base64,${thumbnailBuffer.toString('base64')}`
      }
    });

  } catch (error) {
    console.error(`[PROCESAMIENTO] 🔴 Error con ${name}:`, error.message);
    res.status(500).json({ error: 'Failed to process image', details: error.message });
  }
});

// --- Health Check ---
app.get('/health', (req, res) => {
  res.status(200).send('OK');
});

// --- Catch-all to serve index.html for client-side routing (Express 5 fix) ---
app.get(/.*/, (req, res) => {
  if (req.path.startsWith('/api')) {
    return res.status(404).json({ error: 'Not Found' });
  }

  const indexPath = path.join(__dirname, 'dist', 'index.html');

  if (fs.existsSync(indexPath)) {
    res.sendFile(indexPath);
  } else {
    // Fallback si no existe el build del frontend
    res.status(200).send(`
      <html>
        <head><title>Server Running</title></head>
        <body style="font-family: monospace; background: #1a1a1a; color: #0f0; padding: 2rem;">
          <h1>✅ Server Status: ONLINE (Hacker Mode)</h1>
          <p>El servidor Backend está funcionando correctamente.</p>
          <hr style="border-color: #333;">
          <p>⚠️ <strong>Frontend no encontrado:</strong> No se encontró el archivo <code>dist/index.html</code>.</p>
          <p>Posibles causas:</p>
          <ul>
            <li>El proceso de build (<code>npm run build</code>) falló o no se ejecutó en el Dockerfile.</li>
            <li>La carpeta <code>dist</code> está en .dockerignore pero no se generó dentro de la imagen.</li>
          </ul>
          <p>Revisa los logs de "Build" en Hugging Face.</p>
        </body>
      </html>
    `);
  }
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`\n[SERVIDOR] 🚀 Listo en http://0.0.0.0:${PORT} - Integración Firebase HACKER MODE Activa`);
  console.log(`[INIT] ⚡ Sharp Concurrency: ${sharp.concurrency()} hilos activos para procesamiento de imágenes.`);
  console.log(`\n--- ENLACES DE ACCESO ---`);
  console.log(`👀 Visor (Solo Lectura): http://localhost:3000/`);
  console.log(`🔑 Admin (Control Total): http://localhost:3000/?admin=true`);
  console.log(`-------------------------\n`);
});
