const pages = [...document.querySelectorAll("main > section")];
const navLinks = [...document.querySelectorAll("nav a[data-page]")];

function showPage() {
  const requested = window.location.hash.slice(1);
  const current = pages.find((page) => page.id === requested) ?? pages[0];
  for (const page of pages) {
    page.hidden = page !== current;
  }
  for (const link of navLinks) {
    if (link.dataset.page === current.id) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  }
}

window.addEventListener("hashchange", showPage);
showPage();

const fileInput = document.querySelector("#csv-file");
const fileStatus = document.querySelector("#file-status");
const defaultFileStatus = fileStatus.textContent;
const validation = document.querySelector("#validation");
const validationSummary = document.querySelector("#validation-summary");
const rowErrors = document.querySelector("#row-errors");
const confirmRows = document.querySelector("#confirm-rows");
let selection = 0;

fileInput.addEventListener("change", async () => {
  const currentSelection = ++selection;
  const file = fileInput.files[0];
  validation.hidden = true;
  rowErrors.replaceChildren();
  confirmRows.disabled = true;
  fileStatus.textContent = defaultFileStatus;
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".csv")) {
    fileStatus.textContent = "Выберите файл с расширением .csv.";
    return;
  }

  fileStatus.textContent = "Проверяем CSV…";
  try {
    const bytes = await file.arrayBuffer();
    if (currentSelection !== selection) return;
    const source = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    const { accepted, errors } = validateCsv(source);
    fileStatus.textContent = `Проверен файл «${file.name}». После подтверждения откроется пример отчёта.`;
    validation.hidden = false;
    validationSummary.textContent = `Готовы к подтверждению: ${accepted}. Строк с ошибками: ${errors.length}.`;
    for (const error of errors) {
      const item = document.createElement("li");
      item.textContent = error;
      rowErrors.append(item);
    }
    confirmRows.disabled = accepted === 0;
  } catch (error) {
    if (currentSelection !== selection) return;
    fileStatus.textContent = error instanceof TypeError
      ? "Не удалось прочитать файл. Сохраните CSV в UTF-8."
      : error.message;
  }
});

document.querySelector("#upload-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!confirmRows.disabled) window.location.hash = "report";
});
