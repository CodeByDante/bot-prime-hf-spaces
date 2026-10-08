import { GoogleGenAI } from "@google/genai";

const apiKey = process.env.API_KEY || '';

let ai: GoogleGenAI | null = null;

if (apiKey) {
  ai = new GoogleGenAI({ apiKey: apiKey });
}

export const generateSummary = async (content: string): Promise<string> => {
  if (!ai) {
    console.warn("API Key not found. Skipping AI generation.");
    return "Resumen IA no disponible (Falta API Key).";
  }

  try {
    const response = await ai.models.generateContent({
      model: 'gemini-2.0-flash-exp',
      contents: `Resume el siguiente contenido en un párrafo conciso y atractivo (máx 30 palabras) adecuado para una vista previa de tarjeta. Responde en ESPAÑOL. Contenido: ${content}`,
    });

    return response.text || "No se pudo generar el resumen.";
  } catch (error) {
    console.error("Gemini API Error:", error);
    throw new Error("Failed to generate summary.");
  }
};

export const suggestTags = async (content: string): Promise<string[]> => {
  if (!ai) return [];

  try {
    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: `Genera de 3 a 5 palabras clave/etiquetas cortas y relevantes para el siguiente texto. Responde SOLO con las etiquetas separadas por comas, sin texto extra. Contenido: ${content}`,
    });

    const text = response.text || "";
    return text.split(',').map(tag => tag.trim()).filter(tag => tag.length > 0);
  } catch (e) {
    return [];
  }
}