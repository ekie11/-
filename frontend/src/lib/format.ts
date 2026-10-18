import type { JobMode, JobStatus } from "@/lib/api";

const dateFormat = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Europe/Moscow",
});

const statusLabels: Record<JobStatus, string> = {
  queued: "В очереди",
  running: "Обрабатывается",
  done: "Готово",
  error: "Ошибка",
  expired: "Срок хранения истёк",
};

const modeLabels: Record<JobMode, string> = {
  check: "Проверка",
  format: "Оформление",
};

export const format = {
  dateTime: (iso: string): string => dateFormat.format(new Date(iso)),
  statusLabel: (status: JobStatus): string => statusLabels[status],
  modeLabel: (mode: JobMode): string => modeLabels[mode],
};
