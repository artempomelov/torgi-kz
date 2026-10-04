// Пошаговая подсказка «Как купить» — по виду продажи и происхождению лота.
type Guide = { title: string; steps: string[] };

function guideFor(origin: string, saleType: string | null, source: string): Guide {
  const auction = saleType === "auction" || saleType === "auction_down";
  if (source === "adilet" || origin === "arrested") {
    return {
      title: "Как купить арестованное имущество",
      steps: [
        "Зарегистрируйтесь на etp.adilet.gov.kz с ЭЦП (физлицо или ИП/ТОО).",
        "Изучите лот: отчёт об оценке, документы, обременения. Спросите судебного исполнителя о жильцах и долгах.",
        "Внесите гарантийный взнос до окончания приёма заявок и подайте заявку на участие.",
        "Участвуйте в торгах в назначенное время. Победитель подписывает протокол и оплачивает лот в срок.",
        "Получите постановление и зарегистрируйте право собственности в ЦОН.",
      ],
    };
  }
  if (source === "sauda" || ["state", "bankrupt", "tax_debtor", "confiscated"].includes(origin)) {
    return {
      title: auction && saleType === "auction_down" ? "Как купить на аукционе на понижение (E-Qazyna)" : "Как купить на торгах E-Qazyna",
      steps: [
        "Зарегистрируйтесь на sauda.e-qazyna.kz (вход по ЭЦП).",
        "Изучите паспорт объекта и документы, при необходимости договоритесь с продавцом об осмотре.",
        "Перечислите гарантийный взнос на счёт ИУЦ и подайте заявку до окончания приёма.",
        saleType === "auction_down"
          ? "На аукционе цена снижается шагами — первый, кто подтвердит цену, выигрывает."
          : "На аукционе цена растёт шагами — побеждает последнее предложение.",
        "Подпишите протокол и договор купли-продажи, оплатите в срок и зарегистрируйте право в ЦОН.",
      ],
    };
  }
  if (auction) {
    return {
      title: "Как купить на торгах банка",
      steps: [
        "Свяжитесь с банком по телефону из карточки, уточните условия и порядок торгов.",
        "Изучите документы объекта и осмотрите его.",
        "Подайте заявку и внесите задаток, если он предусмотрен.",
        "Участвуйте в торгах; победитель заключает договор купли-продажи с банком.",
      ],
    };
  }
  return {
    title: "Как купить у банка",
    steps: [
      "Позвоните менеджеру банка из карточки: уточните цену, наличие торга и возможность ипотеки или рассрочки.",
      "Осмотрите объект и запросите документы: правоустанавливающие, техпаспорт, справку об обременениях.",
      "Согласуйте условия и подпишите договор купли-продажи — обычно у нотариуса.",
      "Оплатите и зарегистрируйте право собственности в ЦОН.",
    ],
  };
}

export function HowToBuy({ origin, saleType, source }: { origin: string; saleType: string | null; source: string }) {
  const g = guideFor(origin, saleType, source);
  return (
    <section className="rounded-xl border border-border bg-surface p-5">
      <h2 className="mb-3 text-lg font-semibold">{g.title}</h2>
      <ol className="space-y-2 text-sm">
        {g.steps.map((s, i) => (
          <li key={i} className="flex gap-3">
            <span className="flex h-6 w-6 flex-none items-center justify-center rounded-full bg-brand-ink/10 text-xs font-semibold text-brand-ink">
              {i + 1}
            </span>
            <span className="pt-0.5">{s}</span>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-xs text-muted">Порядок может отличаться — сверяйтесь с условиями торгов у источника.</p>
    </section>
  );
}
