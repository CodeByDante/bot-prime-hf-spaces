import { GoogleGenerativeAI } from "@google/generative-ai";

// Use environment variable, or fallback to the key provided by the user for immediate fix
const apiKey = import.meta.env.VITE_GEMINI_API_KEY || "AIzaSyCVIbMfcOuhr51iZ5wKGl7y7gBfm-cm63s";

if (!apiKey) {
  console.warn("VITE_GEMINI_API_KEY is not set.");
}

const genAI = new GoogleGenerativeAI(apiKey);
// Prioritize the model that was verified to work: gemini-2.0-flash-exp
const availableModels = ["gemini-2.0-flash-exp", "gemini-1.5-flash", "gemini-pro"];

// Helper to clean response text
const cleanAIResponse = (text: string): string => {
  if (!text) return "";
  // Remove markdown code blocks (```html, ```xml, ```, etc.)
  let cleaned = text.replace(/```(?:html|xml|markdown)?\s*([\s\S]*?)```/gi, "$1");
  // Remove any remaining backticks if they are wrapping the whole content
  cleaned = cleaned.trim();
  if (cleaned.startsWith("`") && cleaned.endsWith("`")) {
    cleaned = cleaned.slice(1, -1);
  }
  return cleaned;
};

export const expandSummary = async (text: string): Promise<string> => {
  if (!text || text.length < 3) return text;

  let lastError;

  for (const modelName of availableModels) {
    try {
      const model = genAI.getGenerativeModel({ model: modelName });
      const prompt = `
      Actúa como un redactor técnico experto. 
      El usuario te dará un texto corto o un enlace. Tu trabajo es generar un resumen estructurado y detallado.
      
      Entrada del usuario: "${text}"

      Instrucciones:
      1. Explica qué es (tecnología, herramienta, concepto).
      2. Si es un enlace, infiere de qué trata por el nombre o contexto.
      3. Menciona para qué sirve y sus características principales.
      4. Usa un tono profesional pero directo.
      5. No uses markdown complejo (como headers #), usa texto plano o saltos de línea simples.
      6. Mantén la respuesta concisa pero informativa (máximo 150 palabras).
      
      Solo devuelve el texto del resumen mejorado.
    `;

      const result = await model.generateContent(prompt);
      const response = await result.response;
      return cleanAIResponse(response.text());
    } catch (error: any) {
      console.warn(`Model ${modelName} failed:`, error.message);
      lastError = error;
      // Continue to next model
    }
  }

  // If all failed
  console.error("All AI models failed:", lastError);
  const rawMessage = lastError?.message || String(lastError);

  if (rawMessage.includes("API key")) {
    throw new Error("Clave API inválida o no configurada.");
  } else if (rawMessage.includes("403")) {
    throw new Error("Acceso denegado. Revisa tu clave API.");
  } else if (rawMessage.includes("404")) {
    throw new Error("Modelos de IA no encontrados para esta clave.");
  }

  throw new Error(`Error de IA: ${rawMessage}`);
};

export const generateFromInstructions = async (
  currentContent: string,
  instructions: string,
  context?: string
): Promise<string> => {
  let lastError;

  for (const modelName of availableModels) {
    try {
      const model = genAI.getGenerativeModel({ model: modelName });

      let prompt = "";

      if (!currentContent || currentContent.trim().length === 0) {
        // Generation mode
        prompt = `
          Actúa como un asistente de redacción experto y creativo.
          
          Instrucciones del usuario: "${instructions}"
          
          Contexto adicional: ${context || "Ninguno"}
          
          Tu tarea es generar contenido nuevo basándote EXCLUSIVAMENTE en las instrucciones del usuario.
          Usa un formato HTML limpio. 
          - Para listas usa <ul>/<li>.
          - Para bloques de código usa <pre><code>...</code></pre>.
          - Para negritas <b> o <strong>.
          
          SI EL USUARIO PIDE COMPONENTES ESPECIALES, USA ESTOS FORMATOS:
          1. **Botones**: <a data-type="custom-button" href="URL" data-variant="visit|download|github" data-background-color="#COLOR">Texto</a>
          2. **Videos**: <div data-type="universal-video" data-src="URL_YOUTUBE" data-width="100%"></div>
          3. **Citas (Blockquotes)**: <blockquote style="border-left-color: #COLOR; border-left-width: 4px; background-color: transparent;">Texto</blockquote>
          
          NO uses markdown (como ** o #).
          Responde SOLO con el HTML generado, sin etiquetas <html> ni <body>.
        `;
      } else {
        // Improvement/Edit mode
        prompt = `
          Actúa como un editor experto.
          
          Contenido actual (HTML):
          """
          ${currentContent}
          """
          
          Instrucciones de modificación: "${instructions}"
          
          Tu tarea es reescribir, mejorar o modificar el contenido actual siguiendo las instrucciones.
          Mantén el estilo general pero aplica los cambios solicitados.
          Devuelve el resultado en HTML válido compatible con Tiptap.
          
          Responde SOLO con el contenido mejorado en HTML.
        `;
      }

      const result = await model.generateContent(prompt);
      const response = await result.response;
      return cleanAIResponse(response.text());
    } catch (error: any) {
      console.warn(`Model ${modelName} failed for instructions:`, error.message);
      lastError = error;
    }
  }

  throw new Error(`Fallo en IA: ${lastError?.message || "No se pudo generar contenido."}`);
};
