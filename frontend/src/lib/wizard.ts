export const MAX_FILE_BYTES = 20 * 1024 * 1024;

export function validateFile(file: File): string | null {
  if (!file.name.toLowerCase().endsWith(".docx")) return "Нужен файл .docx";
  if (file.size > MAX_FILE_BYTES) return "Файл больше 20 МБ";
  return null;
}

export function stepFromQuery(step: string | null, hasInput: boolean): 1 | 2 {
  return step === "2" && hasInput ? 2 : 1;
}
