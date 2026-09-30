// Переключатели возможностей сайта. Меняются переменными окружения при сборке — без правки кода.
//
// Платный режим (NEXT_PUBLIC_PAYWALL=1) готовится заранее:
//   - закрытые поля (адрес, контакты, ссылка на источник, история цены, описание — см. GATED_FIELDS
//     в backend/torgi/export.py) рендерятся только в <LotDetails>, в каталоге показывается город;
//   - backend выгружает статику с флагом --gated, а закрытые данные отдаёт API после входа;
//   - вход — через Telegram, лимит — FREE_DETAILS_PER_DAY лотов в день, дальше подписка.
// Пока режим выключен, сайт полностью бесплатный и показывает всё.

export const FEATURES = {
  paywall: process.env.NEXT_PUBLIC_PAYWALL === "1",
  auth: process.env.NEXT_PUBLIC_AUTH === "1",
  freeDetailsPerDay: 5,
  telegramBot: process.env.NEXT_PUBLIC_TELEGRAM_BOT || null, // имя бота для входа, без @ (в @BotFather: /setdomain)
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "", // по умолчанию тот же домен: https://torgi.kz/api/...
  telegramUrl: process.env.NEXT_PUBLIC_TELEGRAM_URL || null, // ссылка на канал, например https://t.me/torgi_kz
  yandexMetrikaId: process.env.NEXT_PUBLIC_YM_ID || null,
} as const;
